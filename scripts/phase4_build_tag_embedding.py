"""Phase 4: Self-trained tag co-occurrence embedding via PPMI + SVD.

Builds a dense (V, D) embedding for each tag in the vocabulary by:
  1. Counting tag-tag co-occurrence across the game corpus.
  2. Normalizing to PPMI (positive pointwise mutual information).
  3. Truncated SVD to D dimensions (classic word2vec-precursor approach).

Why:
  TF-IDF (Phase 1) treats every tag as orthogonal — "Rogue-like",
  "Roguelike", "Rogue-lite" live in 3 separate columns. Tags like
  "Cozy"/"Relaxing"/"Wholesome" don't share TF-IDF signal even though
  they mean the same thing semantically. A co-occurrence embedding
  collapses these into nearby vectors, enabling synonym merging and
  semantic extension for sparse-tagged long-tail games.

This is the "self-trained ML" layer (§6.5 of the project plan).
Pure numpy + scipy. No torch, no transformers.

Output:
  data/tag_embedding.npy        (V, D) float32, L2-normalized rows
  data/tag_embedding_meta.json  config + diagnostics

Usage:
    py scripts/phase4_build_tag_embedding.py
    py scripts/phase4_build_tag_embedding.py --dim 64 --shift 2.0
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"

DB_PATH = DATA_DIR / "corpus.db"
VOCAB_PATH = DATA_DIR / "tag_vocab.json"
EMBED_PATH = DATA_DIR / "tag_embedding.npy"
META_PATH = DATA_DIR / "tag_embedding_meta.json"


def load_game_tags(vocab_idx: dict[str, int]) -> dict[int, list[int]]:
    """appid -> [tag_col, ...]  (only tags in vocab)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT appid, tag FROM game_tags")
    out: dict[int, list[int]] = defaultdict(list)
    for appid, tag in cur.fetchall():
        col = vocab_idx.get(tag)
        if col is not None:
            out[appid].append(col)
    return out


def build_cooccurrence(
    tags_by_appid: dict[int, list[int]], V: int
) -> np.ndarray:
    """V x V symmetric co-occurrence count matrix.

    cooc[i, j] = number of games where tag_i AND tag_j both appear.
    Diagonal = tag document frequency.
    """
    cooc = np.zeros((V, V), dtype=np.float64)
    for tags in tags_by_appid.values():
        # Unique within doc — a tag is either present or not
        uniq = list(set(tags))
        for i in uniq:
            for j in uniq:
                cooc[i, j] += 1.0
    return cooc


def ppmi(cooc: np.ndarray, shift: float = 1.0) -> np.ndarray:
    """Positive PMI with optional shift (SPPMI).

    PMI(i, j) = log( P(i, j) / (P(i) P(j)) )
              = log( cooc[i,j] * N / (row_sum[i] * row_sum[j]) )

    PPMI = max(PMI - log(shift), 0)
    """
    total = cooc.sum()
    if total == 0:
        raise ValueError("Co-occurrence matrix is empty.")
    row_sum = cooc.sum(axis=1)  # = column sum (symmetric)

    # log( cooc * total / (row_sum_i * row_sum_j) )
    # Compute in two pieces to avoid huge intermediate arrays.
    with np.errstate(divide="ignore", invalid="ignore"):
        log_joint = np.log(cooc * total)
        log_marg = np.log(row_sum)
        pmi_mat = log_joint - log_marg[:, None] - log_marg[None, :]
    pmi_mat[~np.isfinite(pmi_mat)] = 0.0
    return np.maximum(pmi_mat - np.log(shift), 0.0)


def truncated_svd(ppmi_mat: np.ndarray, dim: int) -> np.ndarray:
    """Top-D singular triplets via numpy SVD (V ~ 400 so dense is fine).

    Returns U[:, :D] * sqrt(S[:D])  — standard word-embedding recipe.
    """
    # full_matrices=False keeps shapes (V, V), (V,), (V, V) at worst.
    U, S, _ = np.linalg.svd(ppmi_mat, full_matrices=False)
    emb = U[:, :dim] * np.sqrt(S[:dim])
    return emb.astype(np.float32)


def l2_normalize(M: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (M / norms).astype(np.float32)


def quick_sanity(emb: np.ndarray, vocab: list[str]) -> list[dict]:
    """Print a few nearest-neighbor probes inline so we can eyeball success."""
    tag_idx = {t: i for i, t in enumerate(vocab)}
    probes = [
        "Rogue-like", "Roguelike", "Rogue-lite",
        "Souls-like", "Difficult",
        "Cozy", "Relaxing",
        "Deckbuilding", "Card Game",
    ]
    rows = []
    for t in probes:
        i = tag_idx.get(t)
        if i is None:
            continue
        sims = emb @ emb[i]
        sims[i] = -1.0
        top = np.argsort(sims)[-3:][::-1]
        rows.append({
            "tag": t,
            "top": [(vocab[j], float(sims[j])) for j in top],
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, default=50, help="embedding dimension")
    ap.add_argument("--shift", type=float, default=1.0,
                    help="SPPMI shift (1.0 = vanilla PPMI; higher = sparser)")
    args = ap.parse_args()

    if not VOCAB_PATH.exists():
        raise SystemExit(f"{VOCAB_PATH} not found. Run phase1_build_index.py first.")

    vocab: list[str] = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    V = len(vocab)
    vocab_idx = {t: i for i, t in enumerate(vocab)}
    print(f"Vocab size: {V}")

    print("\nLoading game tags...")
    tags_by_appid = load_game_tags(vocab_idx)
    print(f"  {len(tags_by_appid)} games contribute tags")

    print("\nBuilding co-occurrence matrix...")
    cooc = build_cooccurrence(tags_by_appid, V)
    nnz_pct = (cooc > 0).sum() / (V * V) * 100
    print(f"  shape: {cooc.shape}, nnz: {(cooc > 0).sum()} ({nnz_pct:.1f}% filled)")
    print(f"  total mass: {cooc.sum():.0f}")

    print(f"\nComputing PPMI (shift={args.shift})...")
    ppmi_mat = ppmi(cooc, shift=args.shift)
    print(f"  PPMI nnz: {(ppmi_mat > 0).sum()} ({(ppmi_mat > 0).sum() / (V*V) * 100:.1f}%)")
    print(f"  PPMI max: {ppmi_mat.max():.3f}, mean(>0): {ppmi_mat[ppmi_mat > 0].mean():.3f}")

    print(f"\nTruncated SVD to {args.dim} dims...")
    emb = truncated_svd(ppmi_mat, args.dim)
    print(f"  raw shape: {emb.shape}")

    emb_norm = l2_normalize(emb)
    print(f"  L2-normalized rows ready")

    print(f"\nQuick sanity probe (top-3 neighbors):")
    probe_results = quick_sanity(emb_norm, vocab)
    for row in probe_results:
        nb_str = ", ".join(f"{t} ({s:.2f})" for t, s in row["top"])
        print(f"  {row['tag']:18}-> {nb_str}")

    np.save(EMBED_PATH, emb_norm)
    META_PATH.write_text(json.dumps({
        "dim": args.dim,
        "vocab_size": V,
        "ppmi_shift": args.shift,
        "n_games_contributing": len(tags_by_appid),
        "cooc_fill_pct": round(nnz_pct, 2),
        "probe_results": probe_results,
    }, indent=2, ensure_ascii=False))

    size_kb = EMBED_PATH.stat().st_size / 1024
    print(f"\nWrote {EMBED_PATH.name}  ({size_kb:.1f} KB)")
    print(f"Wrote {META_PATH.name}")


if __name__ == "__main__":
    main()
