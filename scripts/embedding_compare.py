"""Compare 6 game-similarity methods on the cached probe data.

Reuses probe_games_cache.json. Filters out bad-appid entries by fuzzy
name matching (drops games where fetched name diverges from expected).

Methods compared:
  A: full text embedding (name + description + genres + tags) — current
  B: tags-only embedding
  C: tags x3 + name + genres embedding (tag weight boost)
  D: tag Jaccard (set overlap, no embedding)
  E: TF-IDF weighted tag cosine (penalizes common noise tags)
  F: B + D hybrid (50/50 average of similarity matrices)

Outputs strict + merged hit rates for each, plus a sorted summary.

Usage:
    py scripts/embedding_compare.py
"""

import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from math import log
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


HERE = Path(__file__).parent
CACHE_PATH = HERE / "probe_games_cache.json"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
K = 5

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


def name_matches(expected: str, actual: str) -> bool:
    """True if expected and actual names are similar enough to trust the fetch."""
    if not actual:
        return False
    e, a = expected.lower().strip(), actual.lower().strip()
    if not e or not a:
        return False
    if e in a or a in e:
        return True
    # Normalize trademark/copyright marks and edition suffixes
    for noise in ("™", "®", ":", "-", "definitive edition", "remastered", "goty"):
        a = a.replace(noise, " ")
        e = e.replace(noise, " ")
    a = " ".join(a.split())
    e = " ".join(e.split())
    if e in a or a in e:
        return True
    return SequenceMatcher(None, e, a).ratio() >= 0.55


def load_games(cache: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    games = []
    dropped = []
    for appid_str, entry in cache.items():
        steam = entry.get("steam") or {}
        if "_error" in steam or not steam.get("name"):
            continue
        actual = steam["name"]
        expected = entry["expected_name"]
        if not name_matches(expected, actual):
            dropped.append((expected, actual))
            continue
        games.append({
            "appid": int(appid_str),
            "expected_name": expected,
            "cluster": entry["cluster"],
            "merged": MERGE.get(entry["cluster"], entry["cluster"]),
            "name": actual,
            "description": steam.get("short_description", "") or "",
            "genres": steam.get("genres", []) or [],
            "tags": entry.get("tags") or [],
        })
    return games, dropped


# === Text composition variants for embedding methods ===

def text_full(g: dict) -> str:
    return " ".join([
        g["name"],
        g["description"],
        " ".join(g["genres"]),
        " ".join(g["tags"]),
    ])


def text_tags_only(g: dict) -> str:
    if g["tags"]:
        return " ".join(g["tags"])
    # Fallback for games without tags so they don't get empty text
    return g["name"] + " " + " ".join(g["genres"])


def text_tags_weighted(g: dict) -> str:
    parts = [g["name"]] + list(g["genres"]) + (list(g["tags"]) * 3)
    return " ".join(parts)


# === Non-embedding similarity methods ===

def jaccard_matrix(games: list[dict]) -> np.ndarray:
    n = len(games)
    tag_sets = [set(g["tags"]) for g in games]
    sim = np.zeros((n, n))
    for i in range(n):
        si = tag_sets[i]
        if not si:
            continue
        for j in range(i + 1, n):
            sj = tag_sets[j]
            if not sj:
                continue
            inter = len(si & sj)
            union = len(si | sj)
            v = inter / union if union else 0
            sim[i, j] = v
            sim[j, i] = v
    return sim


def tfidf_tag_matrix(games: list[dict]) -> np.ndarray:
    n = len(games)
    df: Counter = Counter()
    for g in games:
        for t in set(g["tags"]):
            df[t] += 1
    if not df:
        return np.zeros((n, n))
    vocab = {t: i for i, t in enumerate(df)}
    V = len(vocab)
    M = np.zeros((n, V), dtype=np.float32)
    for i, g in enumerate(games):
        tag_counts: Counter = Counter(g["tags"])
        for t, c in tag_counts.items():
            if t in vocab:
                idf = log((n + 1) / (df[t] + 1)) + 1  # smoothed idf
                M[i, vocab[t]] = c * idf
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    M = M / norms
    return M @ M.T


# === Embedding helper ===

def embed_matrix(model: SentenceTransformer, games: list[dict], text_fn) -> np.ndarray:
    texts = [text_fn(g) for g in games]
    emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    emb = np.asarray(emb)
    return emb @ emb.T


# === Evaluation ===

def hit_rates(games: list[dict], sim: np.ndarray, k: int = K) -> tuple[float, float, dict, dict]:
    n = len(games)
    s_h = s_n = m_h = m_n = 0
    by_cluster_strict: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_cluster_merged: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for i in range(n):
        row = sim[i].copy()
        row[i] = -1.0
        top_idx = np.argsort(row)[-k:][::-1]
        for j in top_idx:
            s_n += 1
            m_n += 1
            by_cluster_strict[games[i]["cluster"]][1] += 1
            by_cluster_merged[games[i]["merged"]][1] += 1
            if games[j]["cluster"] == games[i]["cluster"]:
                s_h += 1
                by_cluster_strict[games[i]["cluster"]][0] += 1
            if games[j]["merged"] == games[i]["merged"]:
                m_h += 1
                by_cluster_merged[games[i]["merged"]][0] += 1
    return s_h / s_n * 100, m_h / m_n * 100, dict(by_cluster_strict), dict(by_cluster_merged)


def main() -> None:
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)

    games, dropped = load_games(cache)
    print(f"Loaded {len(cache)} cache entries")
    print(f"After name-mismatch filter: {len(games)} games (dropped {len(dropped)})")
    if dropped:
        print("\nDropped (expected -> got):")
        for e, a in dropped:
            print(f"  {e[:30]:30} -> {a[:40]:40}")

    print(f"\nLoading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Precompute sim matrices
    print("\nComputing similarity matrices...")
    sim_A = embed_matrix(model, games, text_full)
    sim_B = embed_matrix(model, games, text_tags_only)
    sim_C = embed_matrix(model, games, text_tags_weighted)
    sim_D = jaccard_matrix(games)
    sim_E = tfidf_tag_matrix(games)
    sim_F = 0.5 * sim_B + 0.5 * sim_D

    methods = [
        ("A: full text emb", sim_A),
        ("B: tags-only emb", sim_B),
        ("C: tags3x emb",    sim_C),
        ("D: tag Jaccard",   sim_D),
        ("E: TF-IDF tags",   sim_E),
        ("F: B+D hybrid",    sim_F),
    ]

    # Per-method overall
    print("\n" + "=" * 70)
    print(f"{'Method':<22}  {'Strict':>10}  {'Merged':>10}")
    print("=" * 70)
    results = []
    for name, sim in methods:
        s, m, _, _ = hit_rates(games, sim)
        results.append((name, s, m, sim))
        print(f"{name:<22}  {s:>9.1f}%  {m:>9.1f}%")

    # Best method's per-cluster breakdown
    best_name, best_s, best_m, best_sim = max(results, key=lambda x: x[2])
    print(f"\n{'=' * 70}\nBest method (by merged): {best_name}\n{'=' * 70}")
    _, _, by_s, by_m = hit_rates(games, best_sim)
    print(f"\nStrict per-cluster:")
    for c in sorted(by_s):
        h, n = by_s[c]
        print(f"  {c:>22}  {h:>3}/{n:<3}  {h/n*100:5.1f}%")
    print(f"\nMerged per-cluster:")
    for c in sorted(by_m):
        h, n = by_m[c]
        print(f"  {c:>22}  {h:>3}/{n:<3}  {h/n*100:5.1f}%")

    # Ranked summary
    print(f"\n{'=' * 70}\nRanked by merged hit rate:\n{'=' * 70}")
    for name, s, m, _ in sorted(results, key=lambda x: -x[2]):
        verdict = "PASS" if m >= 70 else ("OK  " if m >= 60 else "LOW ")
        print(f"  [{verdict}]  {name:<22}  strict {s:5.1f}%  merged {m:5.1f}%")


if __name__ == "__main__":
    main()
