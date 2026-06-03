"""Phase 1 step 3: Health check on the TF-IDF index.

Loads the artifacts written by phase1_build_index.py, picks ~20 well-known
games, and prints their top-5 nearest neighbors. Lets us eyeball whether
the index produces sensible similarities at corpus scale.

Usage:
    py scripts/phase1_health_check.py

    # Pick specific games:
    py scripts/phase1_health_check.py --appids 1145360,646570,289070
"""

import argparse
import json
import random
import sqlite3
from pathlib import Path

import numpy as np
from scipy import sparse


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
DB_PATH = DATA_DIR / "corpus.db"

VOCAB_PATH = DATA_DIR / "tag_vocab.json"
APPID_PATH = DATA_DIR / "appid_order.json"
TFIDF_PATH = DATA_DIR / "tfidf.npz"


# Hand-picked recognizable games for sanity check. If any are absent from
# corpus, we just skip them.
DEFAULT_PROBES = [
    1145360,   # Hades
    646570,    # Slay the Spire
    289070,    # Civilization VI
    1245620,   # Elden Ring
    413150,    # Stardew Valley
    374320,    # Dark Souls III
    632470,    # Disco Elysium
    892970,    # Valheim
    367520,    # Hollow Knight
    1086940,   # Baldur's Gate 3
]


def load_names(appids: list[int]) -> dict[int, str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        f"SELECT appid, name FROM games WHERE appid IN ({','.join('?' * len(appids))})",
        appids,
    )
    return {a: n for a, n in cur.fetchall()}


def load_tags(appid: int, top_n: int = 8) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT tag, votes FROM game_tags WHERE appid = ? ORDER BY votes DESC LIMIT ?",
        (appid, top_n),
    )
    return [t for t, _ in cur.fetchall()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--appids", type=str, default=None,
                    help="comma-separated appids to probe; default: built-in list")
    ap.add_argument("--k", type=int, default=5, help="number of neighbors")
    ap.add_argument("--random", type=int, default=0,
                    help="additionally probe N random games from corpus")
    args = ap.parse_args()

    appids_order: list[int] = json.loads(APPID_PATH.read_text(encoding="utf-8"))
    appid_to_row = {a: i for i, a in enumerate(appids_order)}
    M = sparse.load_npz(TFIDF_PATH)
    print(f"Corpus loaded: {M.shape[0]} games, {M.shape[1]} tags")

    if args.appids:
        probes = [int(x) for x in args.appids.split(",") if x.strip()]
    else:
        probes = list(DEFAULT_PROBES)

    if args.random:
        random.seed(42)
        random_picks = random.sample(appids_order, min(args.random, len(appids_order)))
        probes.extend(random_picks)

    # Filter to those present in corpus
    present = [p for p in probes if p in appid_to_row]
    missing = [p for p in probes if p not in appid_to_row]
    if missing:
        print(f"WARN: {len(missing)} probe appids not in corpus: {missing}")
    if not present:
        raise SystemExit("No probes in corpus. Try --random 10.")

    names = load_names(appids_order)

    print(f"\nRunning nearest-neighbor probe on {len(present)} games (k={args.k}):\n")

    for appid in present:
        row_idx = appid_to_row[appid]
        target_vec = M[row_idx]
        # Cosine similarity = dot product since rows are L2 normalized
        sims = np.asarray(M @ target_vec.T.todense()).flatten()
        sims[row_idx] = -1.0  # exclude self
        top_idx = np.argsort(sims)[-args.k:][::-1]

        target_name = names.get(appid, "?")
        target_tags = load_tags(appid, 6)
        print(f"[{appid}] {target_name}")
        print(f"  tags: {', '.join(target_tags) if target_tags else '(no tags)'}")
        for j in top_idx:
            nb_appid = appids_order[j]
            nb_name = names.get(nb_appid, "?")
            nb_tags = load_tags(nb_appid, 4)
            print(f"  -> sim {sims[j]:.3f}  [{nb_appid:>8}]  {nb_name[:38]:38}  | {', '.join(nb_tags)}")
        print()


if __name__ == "__main__":
    main()
