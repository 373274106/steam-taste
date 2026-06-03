"""Phase 4 health check: scenario-based probes for the tag embedding.

Goes deeper than the inline sanity in phase4_build_tag_embedding.py:
  - Synonym pairs: should be top-1 of each other
  - Semantic clusters: top-5 neighbors should stay in-cluster
  - Cross-genre opposition: opposing tags should NOT be neighbors
  - Anomaly scan: tags whose top neighbor sim is < 0.3 (weak signal)

Pass criteria (eyeball + score):
  - Synonyms: avg sim >= 0.85
  - Clusters: >= 60% of top-5 stay in declared cluster
  - Opposition: avg sim <= 0.4 between opposing groups
  - Anomaly count: < 10% of vocab has top-1 sim below 0.3

Usage:
    py scripts/phase4_health_check.py
    py scripts/phase4_health_check.py --tag "Soulslike" --k 8
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"

VOCAB_PATH = DATA_DIR / "tag_vocab.json"
EMBED_PATH = DATA_DIR / "tag_embedding.npy"


SYNONYM_PAIRS = [
    ("Rogue-like", "Rogue-lite"),
    ("Cozy", "Wholesome"),
    ("Deckbuilding", "Card Game"),
    ("Co-op", "Online Co-Op"),
    ("Multiplayer", "Online Co-Op"),
    ("RPG", "Role-Playing"),       # may not both exist; skipped if missing
    ("Singleplayer", "Single Player"),  # same
    ("Anime", "Manga"),
]


SEMANTIC_CLUSTERS = {
    "soulslike_cluster": [
        "Souls-like", "Difficult", "Dark Fantasy", "Action RPG",
        "Hack and Slash", "Boss Battles",
    ],
    "cozy_cluster": [
        "Cozy", "Wholesome", "Relaxing", "Casual", "Cute", "Colorful",
    ],
    "strategy_4x_cluster": [
        "Strategy", "Grand Strategy", "Turn-Based Strategy",
        "4X", "Real Time Tactics",
    ],
    "deckbuilder_cluster": [
        "Deckbuilding", "Card Game", "Card Battler",
        "Roguelike Deckbuilder",
    ],
    "horror_cluster": [
        "Horror", "Survival Horror", "Psychological Horror", "Atmospheric",
        "Dark", "Gore",
    ],
    "narrative_cluster": [
        "Story Rich", "Narrative", "Choices Matter", "Visual Novel",
        "Interactive Fiction",
    ],
}


OPPOSITION_PAIRS = [
    # Calm vs intense
    (["Cozy", "Relaxing", "Wholesome"], ["Gore", "Violent", "Difficult"]),
    # Casual vs hardcore
    (["Casual", "Family Friendly"], ["Souls-like", "Bullet Hell"]),
    # Solo vs multiplayer
    (["Singleplayer"], ["PvP", "MMORPG"]),
]


def neighbors(emb: np.ndarray, vocab: list[str], tag: str, k: int = 5
              ) -> list[tuple[str, float]] | None:
    idx = {t: i for i, t in enumerate(vocab)}
    i = idx.get(tag)
    if i is None:
        return None
    sims = emb @ emb[i]
    sims[i] = -1.0
    top = np.argsort(sims)[-k:][::-1]
    return [(vocab[j], float(sims[j])) for j in top]


def test_synonyms(emb: np.ndarray, vocab: list[str]) -> dict:
    idx = {t: i for i, t in enumerate(vocab)}
    results = []
    sims = []
    for a, b in SYNONYM_PAIRS:
        if a not in idx or b not in idx:
            results.append((a, b, None, "missing"))
            continue
        s = float(emb[idx[a]] @ emb[idx[b]])
        sims.append(s)
        results.append((a, b, s, "ok"))
    avg = float(np.mean(sims)) if sims else 0.0
    return {"avg_sim": avg, "pairs": results, "n": len(sims)}


def test_clusters(emb: np.ndarray, vocab: list[str], k: int = 5) -> dict:
    idx = {t: i for i, t in enumerate(vocab)}
    out = {}
    for name, tags in SEMANTIC_CLUSTERS.items():
        present = [t for t in tags if t in idx]
        if len(present) < 2:
            out[name] = {"status": "skipped", "reason": "not enough tags in vocab"}
            continue
        in_cluster_set = set(present)
        per_tag = []
        in_hits = 0
        total_neighbors = 0
        for t in present:
            nbs = neighbors(emb, vocab, t, k)
            hits = sum(1 for nb, _ in nbs if nb in in_cluster_set)
            in_hits += hits
            total_neighbors += len(nbs)
            per_tag.append((t, nbs, hits))
        hit_rate = in_hits / total_neighbors if total_neighbors else 0.0
        out[name] = {
            "hit_rate": hit_rate,
            "tags_tested": len(present),
            "per_tag": per_tag,
        }
    return out


def test_opposition(emb: np.ndarray, vocab: list[str]) -> dict:
    idx = {t: i for i, t in enumerate(vocab)}
    results = []
    for group_a, group_b in OPPOSITION_PAIRS:
        a_present = [t for t in group_a if t in idx]
        b_present = [t for t in group_b if t in idx]
        if not a_present or not b_present:
            results.append({"a": group_a, "b": group_b, "avg_sim": None, "status": "missing"})
            continue
        sims = []
        for ta in a_present:
            for tb in b_present:
                sims.append(float(emb[idx[ta]] @ emb[idx[tb]]))
        results.append({
            "a": a_present,
            "b": b_present,
            "avg_sim": float(np.mean(sims)),
            "status": "ok",
        })
    return results


def scan_weak_tags(emb: np.ndarray, vocab: list[str], threshold: float = 0.3
                   ) -> list[tuple[str, float, str]]:
    """Tags whose top-1 neighbor similarity is below `threshold`."""
    weak = []
    for i, tag in enumerate(vocab):
        sims = emb @ emb[i]
        sims[i] = -1.0
        top_idx = int(np.argmax(sims))
        top_sim = float(sims[top_idx])
        if top_sim < threshold:
            weak.append((tag, top_sim, vocab[top_idx]))
    return weak


def fmt_neighbors(nbs: list[tuple[str, float]]) -> str:
    return ", ".join(f"{t} ({s:.2f})" for t, s in nbs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", type=str, default=None,
                    help="probe a specific tag and exit")
    ap.add_argument("--k", type=int, default=5, help="neighbors per probe")
    ap.add_argument("--weak-threshold", type=float, default=0.3)
    args = ap.parse_args()

    if not EMBED_PATH.exists():
        raise SystemExit(f"{EMBED_PATH} missing. Run phase4_build_tag_embedding.py first.")

    vocab: list[str] = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    emb = np.load(EMBED_PATH)
    print(f"Loaded embedding: {emb.shape} ({emb.dtype})")
    print(f"Vocab: {len(vocab)} tags\n")

    # Single-tag probe shortcut
    if args.tag:
        nbs = neighbors(emb, vocab, args.tag, args.k)
        if nbs is None:
            print(f"Tag {args.tag!r} not in vocab.")
            return
        print(f"Top-{args.k} neighbors for {args.tag!r}:")
        for t, s in nbs:
            print(f"  {t:30}  {s:.3f}")
        return

    # ============================================================
    # 1. Synonym test
    # ============================================================
    print("=" * 60)
    print("1. SYNONYM PAIRS (target sim >= 0.85)")
    print("=" * 60)
    syn = test_synonyms(emb, vocab)
    for a, b, s, status in syn["pairs"]:
        if status == "missing":
            print(f"  {a:24} <> {b:24}  [skipped: not in vocab]")
        else:
            mark = "OK " if s >= 0.85 else "?? " if s >= 0.7 else "!! "
            print(f"  {mark}{a:22} <> {b:22}  sim={s:.3f}")
    print(f"\n  avg sim across {syn['n']} pairs: {syn['avg_sim']:.3f}  "
          f"({'PASS' if syn['avg_sim'] >= 0.85 else 'WEAK'})")

    # ============================================================
    # 2. Semantic clusters
    # ============================================================
    print("\n" + "=" * 60)
    print(f"2. SEMANTIC CLUSTERS (top-{args.k} hit rate target >= 60%)")
    print("=" * 60)
    clusters = test_clusters(emb, vocab, k=args.k)
    cluster_hit_rates = []
    for name, info in clusters.items():
        if info.get("status") == "skipped":
            print(f"\n[{name}] SKIPPED ({info['reason']})")
            continue
        rate = info["hit_rate"]
        cluster_hit_rates.append(rate)
        verdict = "PASS" if rate >= 0.6 else "WEAK"
        print(f"\n[{name}]  hit_rate={rate*100:.0f}%  {verdict}")
        for tag, nbs, hits in info["per_tag"]:
            print(f"  {tag:30} ({hits}/{args.k} in-cluster)")
            for nb, s in nbs:
                in_mark = "*" if nb in {t for t, _, _ in info["per_tag"]} else " "
                print(f"    {in_mark} {nb:28}  {s:.3f}")
    if cluster_hit_rates:
        avg_rate = float(np.mean(cluster_hit_rates))
        print(f"\n  avg cluster hit rate: {avg_rate*100:.0f}%  "
              f"({'PASS' if avg_rate >= 0.6 else 'WEAK'})")

    # ============================================================
    # 3. Opposition (lower sim is better)
    # ============================================================
    print("\n" + "=" * 60)
    print("3. OPPOSING GROUPS (target sim <= 0.4)")
    print("=" * 60)
    opp = test_opposition(emb, vocab)
    opp_sims = []
    for r in opp:
        if r["status"] == "missing":
            print(f"  {r['a']} <-/-> {r['b']}  [skipped]")
            continue
        opp_sims.append(r["avg_sim"])
        verdict = "OK " if r["avg_sim"] <= 0.4 else "?? "
        print(f"  {verdict}{r['a']} <-/-> {r['b']}  avg_sim={r['avg_sim']:.3f}")
    if opp_sims:
        avg = float(np.mean(opp_sims))
        print(f"\n  avg opposition sim: {avg:.3f}  "
              f"({'PASS' if avg <= 0.4 else 'WEAK'})")

    # ============================================================
    # 4. Weak-tag scan
    # ============================================================
    print("\n" + "=" * 60)
    print(f"4. WEAK TAGS (top-1 sim < {args.weak_threshold})")
    print("=" * 60)
    weak = scan_weak_tags(emb, vocab, args.weak_threshold)
    pct = len(weak) / len(vocab) * 100
    verdict = "PASS" if pct < 10 else "WEAK"
    print(f"  {len(weak)} / {len(vocab)} tags weak ({pct:.1f}%)  {verdict}")
    for tag, sim, nb in weak[:20]:
        print(f"    {tag:30}  top: {nb:25}  ({sim:.2f})")
    if len(weak) > 20:
        print(f"    ... and {len(weak) - 20} more")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
