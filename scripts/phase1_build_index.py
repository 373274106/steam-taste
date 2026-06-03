"""Phase 1 step 2: Build TF-IDF tag index from corpus SQLite.

Reads from data/corpus.db (populated by phase1_fetch_corpus.py) and writes:
  data/tag_vocab.json       — list of all tags, ordered (index = column position)
  data/appid_order.json     — list of appids in matrix row order
  data/tfidf.npz            — scipy sparse CSR matrix (N games × V tags), L2 normalized
  data/inverted_index.json  — { tag: [appid, ...] } for fast candidate filtering

This is the core data artifact the Taste Engine queries against.
Pure compute, no API calls — fast (<10s for 5000 games).

Usage:
    py scripts/phase1_build_index.py
"""

import json
import sqlite3
from collections import defaultdict
from math import log
from pathlib import Path

import numpy as np
from scipy import sparse


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
DB_PATH = DATA_DIR / "corpus.db"

VOCAB_PATH = DATA_DIR / "tag_vocab.json"
APPID_PATH = DATA_DIR / "appid_order.json"
TFIDF_PATH = DATA_DIR / "tfidf.npz"
INVIDX_PATH = DATA_DIR / "inverted_index.json"


def load_corpus(conn: sqlite3.Connection):
    """Returns (appids ordered, tags_by_appid)."""
    cur = conn.execute("""
        SELECT appid, name FROM games
        WHERE fetch_status = 'ok'
        ORDER BY owners_low DESC, appid ASC
    """)
    appids: list[int] = []
    names: dict[int, str] = {}
    for appid, name in cur.fetchall():
        appids.append(appid)
        names[appid] = name

    tags_by_appid: dict[int, list[tuple[str, int]]] = defaultdict(list)
    cur = conn.execute("SELECT appid, tag, votes FROM game_tags")
    for appid, tag, votes in cur.fetchall():
        tags_by_appid[appid].append((tag, votes))
    return appids, names, tags_by_appid


def build_vocab(tags_by_appid: dict[int, list[tuple[str, int]]]) -> tuple[list[str], dict[str, int]]:
    """Tag vocabulary = all tags appearing in at least 2 games."""
    df: dict[str, int] = defaultdict(int)
    for appid, tags in tags_by_appid.items():
        for tag, _ in tags:
            df[tag] += 1
    vocab_list = sorted([t for t, c in df.items() if c >= 2])
    vocab_index = {t: i for i, t in enumerate(vocab_list)}
    return vocab_list, vocab_index


def build_tfidf(
    appids: list[int],
    tags_by_appid: dict[int, list[tuple[str, int]]],
    vocab_list: list[str],
    vocab_index: dict[str, int],
) -> sparse.csr_matrix:
    """TF-IDF matrix N × V, L2 normalized per row.

    TF: vote count for the tag on that game (capped, log-scaled to avoid runaway tags).
    IDF: smoothed log inverse document frequency.
    """
    N = len(appids)
    V = len(vocab_list)

    # Document frequency
    df = np.zeros(V, dtype=np.float64)
    for tags in tags_by_appid.values():
        seen = set()
        for tag, _ in tags:
            if tag in vocab_index and tag not in seen:
                df[vocab_index[tag]] += 1
                seen.add(tag)

    # Smoothed IDF
    idf = np.log((N + 1) / (df + 1)) + 1.0

    rows, cols, vals = [], [], []
    for row_idx, appid in enumerate(appids):
        for tag, votes in tags_by_appid.get(appid, []):
            if tag not in vocab_index:
                continue
            col = vocab_index[tag]
            # Log-scale vote count, +1 to keep small votes positive.
            tf = log(1 + max(0, votes))
            rows.append(row_idx)
            cols.append(col)
            vals.append(tf * idf[col])

    M = sparse.csr_matrix((vals, (rows, cols)), shape=(N, V), dtype=np.float32)

    # L2 normalize per row so dot-product = cosine similarity later.
    row_norms = np.sqrt(np.asarray(M.multiply(M).sum(axis=1)).flatten())
    row_norms[row_norms == 0] = 1.0
    inv = sparse.diags(1.0 / row_norms)
    M_norm = inv @ M
    return M_norm.tocsr().astype(np.float32)


def build_inverted_index(
    appids: list[int],
    tags_by_appid: dict[int, list[tuple[str, int]]],
    vocab_index: dict[str, int],
) -> dict[str, list[int]]:
    inv: dict[str, list[int]] = defaultdict(list)
    for appid in appids:
        for tag, _ in tags_by_appid.get(appid, []):
            if tag in vocab_index:
                inv[tag].append(appid)
    return dict(inv)


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"corpus.db not found at {DB_PATH}. Run phase1_fetch_corpus.py first.")

    conn = sqlite3.connect(DB_PATH)
    print(f"Reading corpus from: {DB_PATH}")
    appids, names, tags_by_appid = load_corpus(conn)
    n_with_tags = sum(1 for a in appids if tags_by_appid.get(a))
    print(f"  {len(appids)} games with status=ok")
    print(f"  {n_with_tags} games have tags ({n_with_tags/len(appids)*100:.1f}%)")

    if not appids:
        raise SystemExit("No usable games in corpus.")

    print("\nBuilding tag vocabulary (df >= 2)...")
    vocab_list, vocab_index = build_vocab(tags_by_appid)
    print(f"  vocab size: {len(vocab_list)} tags")

    print("\nBuilding TF-IDF matrix...")
    M = build_tfidf(appids, tags_by_appid, vocab_list, vocab_index)
    print(f"  shape: {M.shape}")
    print(f"  nnz:   {M.nnz} ({M.nnz / (M.shape[0] * M.shape[1]) * 100:.4f}% dense)")
    print(f"  size:  {(M.data.nbytes + M.indices.nbytes + M.indptr.nbytes) / 1024 / 1024:.2f} MB")

    print("\nBuilding inverted index (tag -> [appid, ...])...")
    inv = build_inverted_index(appids, tags_by_appid, vocab_index)
    print(f"  {len(inv)} tags indexed")

    # Persist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(VOCAB_PATH, "w", encoding="utf-8") as f:
        json.dump(vocab_list, f, ensure_ascii=False, indent=2)
    with open(APPID_PATH, "w", encoding="utf-8") as f:
        json.dump(appids, f)
    sparse.save_npz(TFIDF_PATH, M)
    with open(INVIDX_PATH, "w", encoding="utf-8") as f:
        json.dump(inv, f)

    print("\nArtifacts written:")
    for p in [VOCAB_PATH, APPID_PATH, TFIDF_PATH, INVIDX_PATH]:
        size_kb = p.stat().st_size / 1024
        print(f"  {p.name:25}  {size_kb:>10.1f} KB")


if __name__ == "__main__":
    main()
