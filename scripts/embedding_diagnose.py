"""Diagnostic re-analysis using cached probe data.

Re-runs embedding on the cached fetch results and produces:
  - Strict cluster hit rate (same as the original probe)
  - Merged cluster hit rate (treating closely related sub-genres as one)
  - Full per-game neighbor dump to scripts/diagnose_output.txt
  - Worst-performing games list (0-1 hits) for manual inspection

Run after embedding_probe.py has populated probe_games_cache.json.
Fast: reuses cache, just re-embeds (no API calls).

Usage:
    py scripts/embedding_diagnose.py
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


HERE = Path(__file__).parent
CACHE_PATH = HERE / "probe_games_cache.json"
OUTPUT_PATH = HERE / "diagnose_output.txt"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


# Cluster merges to test. Each strict cluster maps to a "loose" cluster.
# Reasoning:
#   - All roguelites share core mechanics regardless of action/deckbuilder twist
#   - Soulslike is mechanically close to action-RPG / open-world-RPG (Elden Ring lives in both)
#   - Narrative is an orthogonal axis, not a genre — keep separate to expose this
#   - Cozy is a mood spectrum, internally heterogeneous — keep separate
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


def build_text(entry: dict) -> str:
    steam = entry.get("steam") or {}
    tags = entry.get("tags") or []
    parts = [
        steam.get("name", ""),
        steam.get("short_description", ""),
        " ".join(steam.get("genres", [])),
        " ".join(tags),
    ]
    return " ".join(p for p in parts if p)


def main() -> None:
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cache = json.load(f)

    usable = []
    for appid_str, entry in cache.items():
        steam = entry.get("steam") or {}
        if "_error" in steam or not steam.get("name"):
            continue
        text = build_text(entry)
        if len(text) < 50:
            continue
        usable.append({
            "appid": int(appid_str),
            "expected_name": entry["expected_name"],
            "cluster": entry["cluster"],
            "merged": MERGE.get(entry["cluster"], entry["cluster"]),
            "actual_name": steam.get("name", ""),
            "text": text,
            "tags": entry.get("tags") or [],
        })

    print(f"Usable: {len(usable)} games")
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print("Embedding...")
    embeddings = model.encode([u["text"] for u in usable],
                              show_progress_bar=True,
                              normalize_embeddings=True)
    embeddings = np.asarray(embeddings)
    sim = embeddings @ embeddings.T

    K = 5

    strict_hits = defaultdict(list)
    merged_hits = defaultdict(list)
    detail_lines = []
    per_game_strict = []

    for i, u in enumerate(usable):
        row = sim[i].copy()
        row[i] = -1.0
        top_idx = np.argsort(row)[-K:][::-1]

        s_hits = 0
        m_hits = 0
        neighbor_records = []
        for j in top_idx:
            n = usable[j]
            same_strict = n["cluster"] == u["cluster"]
            same_merged = n["merged"] == u["merged"]
            if same_strict:
                s_hits += 1
            if same_merged:
                m_hits += 1
            neighbor_records.append({
                "name": n["actual_name"],
                "cluster": n["cluster"],
                "merged": n["merged"],
                "sim": float(row[j]),
                "same_strict": same_strict,
                "same_merged": same_merged,
            })

        strict_hits[u["cluster"]].append((u["actual_name"], s_hits, K))
        merged_hits[u["merged"]].append((u["actual_name"], m_hits, K))
        per_game_strict.append((u["actual_name"], u["cluster"], s_hits, m_hits, neighbor_records))

        # Build detailed text block
        detail_lines.append(f"\n[{i+1}/{len(usable)}] {u['actual_name']} (cluster={u['cluster']}, merged={u['merged']})")
        detail_lines.append(f"  tags: {', '.join(u['tags'][:6])}")
        for n in neighbor_records:
            strict_mark = "OK" if n["same_strict"] else "  "
            merged_mark = "OK" if n["same_merged"] else "  "
            detail_lines.append(
                f"    strict[{strict_mark}] merged[{merged_mark}]  "
                f"{n['name'][:35]:35}  ({n['cluster']:>20} / {n['merged']:>15})  sim {n['sim']:.3f}"
            )
        detail_lines.append(f"  -> strict {s_hits}/{K}, merged {m_hits}/{K}")

    # Write detail file
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(detail_lines))
        f.write("\n")

    # Print summaries
    print("\n" + "=" * 80)
    print("STRICT cluster summary (original taxonomy):")
    print("=" * 80)
    total_h = total_n = 0
    for cluster in sorted(strict_hits):
        results = strict_hits[cluster]
        h = sum(x[1] for x in results)
        n = sum(x[2] for x in results)
        rate = h / n * 100 if n else 0
        print(f"  {cluster:>22}  {h:>3}/{n:<3}  {rate:5.1f}%  ({len(results)} games)")
        total_h += h
        total_n += n
    strict_rate = total_h / total_n * 100 if total_n else 0
    print(f"\n  Overall: {total_h}/{total_n}  {strict_rate:.1f}%")

    print("\n" + "=" * 80)
    print("MERGED cluster summary (semantically related sub-genres unified):")
    print("=" * 80)
    total_h = total_n = 0
    for cluster in sorted(merged_hits):
        results = merged_hits[cluster]
        h = sum(x[1] for x in results)
        n = sum(x[2] for x in results)
        rate = h / n * 100 if n else 0
        print(f"  {cluster:>22}  {h:>3}/{n:<3}  {rate:5.1f}%  ({len(results)} games)")
        total_h += h
        total_n += n
    merged_rate = total_h / total_n * 100 if total_n else 0
    print(f"\n  Overall: {total_h}/{total_n}  {merged_rate:.1f}%")

    # Worst performers
    print("\n" + "=" * 80)
    print("Worst games (strict hits <= 1):")
    print("=" * 80)
    worst = [p for p in per_game_strict if p[2] <= 1]
    for name, cluster, s, m, neighbors in worst[:20]:
        n_summary = ", ".join(f"{n['name'][:18]}({n['cluster'][:12]})" for n in neighbors[:3])
        print(f"  {name[:30]:30}  ({cluster:>18})  s={s} m={m}  | {n_summary}")
    print(f"\n  Total worst: {len(worst)}")

    print(f"\nFull per-game detail written to: {OUTPUT_PATH}")
    print()
    print(f"Strict rate: {strict_rate:.1f}%")
    print(f"Merged rate: {merged_rate:.1f}%")


if __name__ == "__main__":
    main()
