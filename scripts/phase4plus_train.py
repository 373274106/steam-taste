"""Phase 4+: Self-supervised contrastive game encoder.

Replaces the PPMI + SVD baseline (Phase 4) with a trained dual encoder:
  - Architecture: MLP encoder (V -> 256 -> D) with ReLU + dropout + L2 norm
  - Loss: InfoNCE with in-batch negatives, temperature-scaled
  - Positive pairs: games sharing >= 3 high-IDF tags
  - Negatives: in-batch (no explicit sampling needed)
  - Optimizer: Adam with cosine LR schedule, early stopping on val InfoNCE

The Phase 0 probe set (180 hand-clustered games in scripts/probe_games_cache.json)
is held out from training and used as final retrieval evaluation against the
PPMI baseline. Training-pair construction is the only data leakage path —
we exclude all probe appids from positive-pair sampling.

Why this replaces PPMI + SVD:
  Levy & Goldberg (2014) showed word2vec ≈ SPPMI matrix factorization in
  theory. In practice, learned encoders unlock train/val curves, hyperparameter
  tuning, and a real ML training story for the portfolio. Effect size on this
  small corpus (~5k games) is usually modest, but the engineering story is the
  point.

Outputs:
  data/game_embedding.npy        (N, D) float32, L2-normalized
  data/game_embedding_meta.json  config + final metrics
  data/game_embedding_train_log.json  per-epoch loss curve

Usage:
    py scripts/phase4plus_train.py
    py scripts/phase4plus_train.py --dim 128 --epochs 50 --batch-size 256
    py scripts/phase4plus_train.py --quick   # fast sanity (5 epochs)
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from scipy import sparse
from torch.utils.data import DataLoader, Dataset


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"

DB_PATH = DATA_DIR / "corpus.db"
TFIDF_PATH = DATA_DIR / "tfidf.npz"
APPID_PATH = DATA_DIR / "appid_order.json"
VOCAB_PATH = DATA_DIR / "tag_vocab.json"

EMBED_PATH = DATA_DIR / "game_embedding.npy"
META_PATH = DATA_DIR / "game_embedding_meta.json"
LOG_PATH = DATA_DIR / "game_embedding_train_log.json"

PROBE_CACHE_PATH = HERE / "probe_games_cache.json"

# Auxiliary feature names — what the encoder sees beyond the 445-d TF-IDF.
# These are signals the TF-IDF baseline cannot use (it sees tags only), so
# any lift the trained encoder gets here is a real information gain rather
# than just a re-projection of the baseline's input.
AUX_FEATURE_NAMES = ["review_ratio", "review_count_log", "owners_log", "year_norm"]
AUX_DIM = len(AUX_FEATURE_NAMES)


# ============================================================
# Data
# ============================================================

def load_corpus_tag_sets() -> tuple[list[int], dict[int, set[str]], dict[str, int]]:
    """Returns (appid_order, raw_tags_by_appid, df_by_tag)."""
    appid_order: list[int] = json.loads(APPID_PATH.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT appid, tag FROM game_tags")
    by_appid: dict[int, set[str]] = defaultdict(set)
    df: dict[str, int] = defaultdict(int)
    for appid, tag in cur.fetchall():
        if tag not in by_appid[appid]:
            by_appid[appid].add(tag)
            df[tag] += 1
    return appid_order, dict(by_appid), dict(df)


def load_aux_features(appid_order: list[int]) -> np.ndarray:
    """Return an N x AUX_DIM dense float32 matrix, z-score normalized per column.

    Pulls review / owners / year signals straight from corpus.db. These exist
    for every fetch_status='ok' game; missing values get neutral defaults
    (review_ratio=0.5, log_counts=0, year=median) before z-scoring.
    """
    import re

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT appid, positive_reviews, negative_reviews, owners_low, owners_high, release_date "
        "FROM games"
    )
    by_appid: dict[int, tuple] = {}
    for appid, pos, neg, low, high, date in cur.fetchall():
        by_appid[appid] = (pos or 0, neg or 0, low or 0, high or 0, date or "")

    # Year parsing — same regex as backend/taste_engine._parse_year
    year_re = re.compile(r"\b(19|20)\d{2}\b")
    years: list[float | None] = []
    for appid in appid_order:
        _, _, _, _, date = by_appid.get(appid, (0, 0, 0, 0, ""))
        m = year_re.search(date)
        years.append(float(m.group(0)) if m else None)
    parseable = [y for y in years if y is not None]
    year_median = float(np.median(parseable)) if parseable else 2015.0

    feats = np.zeros((len(appid_order), AUX_DIM), dtype=np.float64)
    for i, appid in enumerate(appid_order):
        pos, neg, low, high, _ = by_appid.get(appid, (0, 0, 0, 0, ""))
        total = pos + neg
        feats[i, 0] = pos / total if total > 0 else 0.5
        feats[i, 1] = math.log1p(total)
        feats[i, 2] = math.log1p((low + high) / 2)
        y = years[i] if years[i] is not None else year_median
        feats[i, 3] = (y - year_median) / 10.0  # ~one-decade scale

    # Z-score per column so the encoder sees aux at similar magnitude to TF-IDF
    mean = feats.mean(axis=0)
    std = feats.std(axis=0)
    std[std < 1e-6] = 1.0
    feats = (feats - mean) / std

    return feats.astype(np.float32)


def load_probe_appids() -> set[int]:
    """Phase 0 probe games — held out from training."""
    if not PROBE_CACHE_PATH.exists():
        return set()
    cache = json.loads(PROBE_CACHE_PATH.read_text(encoding="utf-8"))
    return {int(k) for k in cache.keys()}


def build_positive_pairs(
    appid_order: list[int],
    tags_by_appid: dict[int, set[str]],
    df_by_tag: dict[str, int],
    exclude_appids: set[int],
    min_shared: int = 3,
    high_idf_quantile: float = 0.5,
    seed: int = 42,
) -> list[tuple[int, int]]:
    """For each game, find others that share >= min_shared high-IDF tags.

    High-IDF tags are those above the median IDF (suppresses noisy generic
    tags like "Indie", "Singleplayer"). Returns row-index pairs (i, j) with
    i < j for de-duplication. Probe appids are excluded entirely.
    """
    rng = random.Random(seed)
    N = len(appid_order)
    n_total = sum(df_by_tag.values())  # = total tag occurrences, only used for ordering

    # IDF per tag for high-vs-low cut
    df_arr = np.array([df_by_tag.get(t, 0) for t in df_by_tag])
    # Use median DF as the cut — tags above median DF are "common", below are "rare"
    # We want high-IDF = rare = LOW df, so we cut at quantile of df ascending
    df_cut = float(np.quantile(df_arr, high_idf_quantile))
    high_idf_tags = {t for t, c in df_by_tag.items() if c <= df_cut}

    appid_to_row = {a: i for i, a in enumerate(appid_order)}
    # Reduce each game's tag set to high-IDF only
    high_tags_by_row: list[set[str]] = []
    for a in appid_order:
        ts = tags_by_appid.get(a, set())
        high_tags_by_row.append(ts & high_idf_tags)

    # Inverted index on high-IDF tags only — for efficient candidate filtering
    inv: dict[str, list[int]] = defaultdict(list)
    for i, tags in enumerate(high_tags_by_row):
        for t in tags:
            inv[t].append(i)

    exclude_rows = {appid_to_row[a] for a in exclude_appids if a in appid_to_row}

    pairs: list[tuple[int, int]] = []
    for i in range(N):
        if i in exclude_rows:
            continue
        ti = high_tags_by_row[i]
        if len(ti) < min_shared:
            continue
        # Candidates = union of inverted-index lists for i's high-IDF tags
        cand_count: dict[int, int] = defaultdict(int)
        for t in ti:
            for j in inv[t]:
                if j > i and j not in exclude_rows:
                    cand_count[j] += 1
        for j, c in cand_count.items():
            if c >= min_shared:
                pairs.append((i, j))

    rng.shuffle(pairs)
    return pairs


class PairDataset(Dataset):
    """Yields (game_a_vec, game_b_vec) tensors.

    If aux is provided, each yielded vector is [tfidf_row | aux_row] -- the
    encoder sees auxiliary features (reviews, owners, year) the TF-IDF
    baseline cannot access.
    """

    def __init__(
        self,
        tfidf: sparse.csr_matrix,
        pairs: list[tuple[int, int]],
        aux: np.ndarray | None = None,
    ):
        self.tfidf = tfidf
        self.pairs = pairs
        self.aux = aux

    def __len__(self) -> int:
        return len(self.pairs)

    def _row(self, idx: int) -> np.ndarray:
        tf = np.asarray(self.tfidf[idx].todense(), dtype=np.float32).flatten()
        if self.aux is None:
            return tf
        return np.concatenate([tf, self.aux[idx]])

    def __getitem__(self, idx: int):
        i, j = self.pairs[idx]
        a = torch.from_numpy(self._row(i))
        b = torch.from_numpy(self._row(j))
        return a, b


# ============================================================
# Model
# ============================================================

class GameEncoder(nn.Module):
    def __init__(self, V: int, hidden: int = 256, dim: int = 128, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(V, hidden)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden, dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.fc1(x))
        h = self.dropout(h)
        z = self.fc2(h)
        return F.normalize(z, dim=-1)


def info_nce(z_a: torch.Tensor, z_b: torch.Tensor, temperature: float = 0.1) -> torch.Tensor:
    """Symmetric InfoNCE with in-batch negatives.

    z_a, z_b: (B, D) L2-normalized. Each row of z_a should match the same row
    of z_b (the positive pair). All other rows of z_b are negatives.
    """
    B = z_a.size(0)
    sim = z_a @ z_b.T / temperature           # (B, B)
    labels = torch.arange(B, device=z_a.device)
    loss_ab = F.cross_entropy(sim, labels)
    loss_ba = F.cross_entropy(sim.T, labels)
    return 0.5 * (loss_ab + loss_ba)


# ============================================================
# Evaluation on Phase 0 probe set
# ============================================================

MERGE = {
    "roguelite_action":  "roguelite",
    "deckbuilder_rogue": "roguelite",
    "open_world_rpg":    "action_rpg",
    "soulslike":         "action_rpg",
    "grand_strategy":    "grand_strategy",
    "survival_craft":    "survival_craft",
    "cozy_life_sim":     "cozy_life_sim",
    "narrative":         "narrative",
}


def load_probe_for_eval(appid_to_row: dict[int, int]) -> list[dict]:
    """Probe games that exist in our corpus + their cluster labels."""
    if not PROBE_CACHE_PATH.exists():
        return []
    cache = json.loads(PROBE_CACHE_PATH.read_text(encoding="utf-8"))
    out = []
    for appid_str, entry in cache.items():
        appid = int(appid_str)
        if appid not in appid_to_row:
            continue
        cluster = entry.get("cluster")
        if not cluster:
            continue
        out.append({
            "appid": appid,
            "row": appid_to_row[appid],
            "cluster": cluster,
            "merged": MERGE.get(cluster, cluster),
        })
    return out


def probe_hit_rate(emb: np.ndarray, probe: list[dict], k: int = 5) -> tuple[float, float]:
    """Same-cluster hit rate at top-K. Returns (strict, merged) percentages."""
    if not probe:
        return 0.0, 0.0
    rows = np.array([p["row"] for p in probe])
    P = emb[rows]  # (M, D)
    sim = P @ P.T
    np.fill_diagonal(sim, -1.0)
    s_hits = m_hits = total = 0
    for i, p in enumerate(probe):
        top = np.argsort(sim[i])[-k:][::-1]
        for j in top:
            total += 1
            if probe[j]["cluster"] == p["cluster"]:
                s_hits += 1
            if probe[j]["merged"] == p["merged"]:
                m_hits += 1
    return s_hits / total * 100, m_hits / total * 100


# ============================================================
# Training loop
# ============================================================

@torch.no_grad()
def encode_all(
    model: GameEncoder,
    tfidf: sparse.csr_matrix,
    device,
    aux: np.ndarray | None = None,
    batch_size: int = 512,
) -> np.ndarray:
    model.eval()
    N = tfidf.shape[0]
    chunks = []
    for start in range(0, N, batch_size):
        end = min(start + batch_size, N)
        x_tf = np.asarray(tfidf[start:end].todense(), dtype=np.float32)
        if aux is not None:
            x = np.concatenate([x_tf, aux[start:end]], axis=1)
        else:
            x = x_tf
        x_t = torch.from_numpy(x).to(device)
        z = model(x_t).cpu().numpy()
        chunks.append(z)
    model.train()
    return np.concatenate(chunks, axis=0)


def cosine_lr(epoch: int, total: int, base_lr: float, warmup_frac: float = 0.05) -> float:
    warmup_epochs = max(1, int(total * warmup_frac))
    if epoch < warmup_epochs:
        return base_lr * (epoch + 1) / warmup_epochs
    progress = (epoch - warmup_epochs) / max(1, total - warmup_epochs)
    return base_lr * 0.5 * (1.0 + math.cos(math.pi * progress))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--min-shared", type=int, default=3,
                    help="positive pairs must share >= this many high-IDF tags")
    ap.add_argument("--quantile", type=float, default=0.5,
                    help="tag DF quantile cut; lower = stricter 'high IDF'")
    ap.add_argument("--val-frac", type=float, default=0.1,
                    help="fraction of pairs held out for val InfoNCE")
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--early-stop-metric", choices=("val_loss", "probe_merged"),
                    default="val_loss",
                    help="metric to monitor for early stopping and best checkpoint")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--quick", action="store_true",
                    help="5 epochs for fast sanity check")
    ap.add_argument("--no-aux", action="store_true",
                    help="disable aux features (pure TF-IDF input; baseline-comparable ablation)")
    args = ap.parse_args()

    if args.quick:
        args.epochs = 5

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # ----- Load data -----
    print("\nLoading corpus...")
    appid_order, tags_by_appid, df_by_tag = load_corpus_tag_sets()
    tfidf = sparse.load_npz(TFIDF_PATH).astype(np.float32)
    V = tfidf.shape[1]
    N = tfidf.shape[0]
    print(f"  corpus: {N} games x {V} tags")

    if args.no_aux:
        aux = None
        input_dim = V
        print("  aux features: DISABLED (--no-aux)")
    else:
        aux = load_aux_features(appid_order)
        input_dim = V + AUX_DIM
        print(f"  aux features: {AUX_DIM}-d ({', '.join(AUX_FEATURE_NAMES)})")

    probe_appids = load_probe_appids()
    print(f"  probe set (held out): {len(probe_appids)} games")

    print("\nBuilding positive pairs...")
    t0 = time.time()
    all_pairs = build_positive_pairs(
        appid_order, tags_by_appid, df_by_tag,
        exclude_appids=probe_appids,
        min_shared=args.min_shared,
        high_idf_quantile=args.quantile,
        seed=args.seed,
    )
    print(f"  built {len(all_pairs)} positive pairs in {time.time()-t0:.1f}s")
    if len(all_pairs) < 1000:
        raise SystemExit("Too few positive pairs. Lower --min-shared or raise --quantile.")

    # Split pairs into train / val
    n_val = int(len(all_pairs) * args.val_frac)
    val_pairs = all_pairs[:n_val]
    train_pairs = all_pairs[n_val:]
    print(f"  train: {len(train_pairs)}  val: {len(val_pairs)}")

    train_ds = PairDataset(tfidf, train_pairs, aux=aux)
    val_ds = PairDataset(tfidf, val_pairs, aux=aux)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=0, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=0, drop_last=False)

    # ----- Model -----
    model = GameEncoder(V=input_dim, hidden=args.hidden, dim=args.dim, dropout=args.dropout).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: {input_dim} -> {args.hidden} -> {args.dim}  ({n_params:,} params)")

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    # Probe evaluation rows (computed once)
    appid_to_row = {a: i for i, a in enumerate(appid_order)}
    probe_eval = load_probe_for_eval(appid_to_row)
    print(f"Probe games in corpus for eval: {len(probe_eval)}")

    # ----- Baselines -----
    # TF-IDF cosine baseline on probe
    tfidf_dense = np.asarray(tfidf.todense())
    s_base, m_base = probe_hit_rate(tfidf_dense, probe_eval, k=5)
    print(f"\nBaseline TF-IDF cosine on probe:  strict {s_base:.1f}%  merged {m_base:.1f}%")

    # ----- Train -----
    log = []
    # Track both metrics; "best" is whichever we monitor.
    # For val_loss: lower is better. For probe_merged: higher is better.
    best_score = float("inf") if args.early_stop_metric == "val_loss" else -float("inf")
    best_epoch = -1
    best_emb = None
    patience_left = args.patience
    print(f"Early-stop monitor: {args.early_stop_metric}")
    if args.early_stop_metric == "probe_merged":
        print("  NOTE: stopping on probe metrics is dev-set tuning; report honestly")
    print()

    for epoch in range(args.epochs):
        # LR schedule
        lr = cosine_lr(epoch, args.epochs, args.lr)
        for g in optimizer.param_groups:
            g["lr"] = lr

        # Train epoch
        model.train()
        train_loss_sum = 0.0
        n_batches = 0
        t_start = time.time()
        for a, b in train_loader:
            a = a.to(device)
            b = b.to(device)
            z_a = model(a)
            z_b = model(b)
            loss = info_nce(z_a, z_b, temperature=args.temperature)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss_sum += loss.item()
            n_batches += 1
        train_loss = train_loss_sum / max(1, n_batches)

        # Val epoch
        model.eval()
        val_loss_sum = 0.0
        n_val_batches = 0
        with torch.no_grad():
            for a, b in val_loader:
                a = a.to(device)
                b = b.to(device)
                z_a = model(a)
                z_b = model(b)
                loss = info_nce(z_a, z_b, temperature=args.temperature)
                val_loss_sum += loss.item()
                n_val_batches += 1
        val_loss = val_loss_sum / max(1, n_val_batches)

        # Probe metrics (cheap — 180 games)
        full_emb = encode_all(model, tfidf, device, aux=aux)
        s_probe, m_probe = probe_hit_rate(full_emb, probe_eval, k=5)

        elapsed = time.time() - t_start
        print(f"epoch {epoch+1:2d}/{args.epochs}  lr {lr:.2e}  "
              f"train {train_loss:.4f}  val {val_loss:.4f}  "
              f"probe strict {s_probe:.1f}%  merged {m_probe:.1f}%  "
              f"({elapsed:.1f}s)")

        log.append({
            "epoch": epoch + 1,
            "lr": lr,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "probe_strict_pct": s_probe,
            "probe_merged_pct": m_probe,
            "elapsed_s": elapsed,
        })

        # Early stopping based on chosen metric
        if args.early_stop_metric == "val_loss":
            improved = val_loss < best_score - 1e-4
            score_to_track = val_loss
        else:  # probe_merged
            improved = m_probe > best_score + 1e-4
            score_to_track = m_probe

        if improved:
            best_score = score_to_track
            best_epoch = epoch + 1
            best_emb = full_emb.copy()
            patience_left = args.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"\nEarly stop at epoch {epoch+1} (best epoch was {best_epoch})")
                break

    if best_emb is None:
        best_emb = encode_all(model, tfidf, device, aux=aux)
        best_epoch = args.epochs

    # ----- Final eval -----
    s_final, m_final = probe_hit_rate(best_emb, probe_eval, k=5)
    print(f"\n=== Final (best epoch {best_epoch}) ===")
    print(f"  baseline TF-IDF probe:   strict {s_base:.1f}%  merged {m_base:.1f}%")
    print(f"  trained encoder probe:   strict {s_final:.1f}%  merged {m_final:.1f}%")
    delta_s = s_final - s_base
    delta_m = m_final - m_base
    sign = "+" if delta_m >= 0 else ""
    print(f"  delta:                   strict {sign}{delta_s:.1f}pp  merged {sign}{delta_m:.1f}pp")

    # ----- Persist -----
    np.save(EMBED_PATH, best_emb.astype(np.float32))
    META_PATH.write_text(json.dumps({
        "model": {
            "input_dim": input_dim,
            "tag_dim": V,
            "aux_dim": 0 if args.no_aux else AUX_DIM,
            "aux_features": [] if args.no_aux else AUX_FEATURE_NAMES,
            "hidden": args.hidden,
            "output_dim": args.dim,
            "dropout": args.dropout,
        },
        "training": {
            "loss": "InfoNCE (symmetric, in-batch negatives)",
            "temperature": args.temperature,
            "optimizer": "Adam",
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "batch_size": args.batch_size,
            "epochs_run": len(log),
            "best_epoch": best_epoch,
            "early_stop_metric": args.early_stop_metric,
            "best_score": best_score,
            "patience": args.patience,
        },
        "data": {
            "corpus_games": N,
            "vocab_size": V,
            "positive_pairs_total": len(all_pairs),
            "train_pairs": len(train_pairs),
            "val_pairs": len(val_pairs),
            "min_shared_high_idf_tags": args.min_shared,
            "high_idf_quantile": args.quantile,
            "probe_excluded": len(probe_appids),
        },
        "eval_probe_top5": {
            "baseline_tfidf_strict_pct": s_base,
            "baseline_tfidf_merged_pct": m_base,
            "trained_strict_pct": s_final,
            "trained_merged_pct": m_final,
            "delta_strict_pp": delta_s,
            "delta_merged_pp": delta_m,
        },
    }, indent=2))
    LOG_PATH.write_text(json.dumps(log, indent=2))

    size_kb = EMBED_PATH.stat().st_size / 1024
    print(f"\nWrote {EMBED_PATH.name}  shape {best_emb.shape}  ({size_kb:.1f} KB)")
    print(f"Wrote {META_PATH.name}")
    print(f"Wrote {LOG_PATH.name}")


if __name__ == "__main__":
    main()
