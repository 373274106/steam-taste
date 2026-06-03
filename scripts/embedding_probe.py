"""Embedding feasibility probe for Steam Taste Lens.

Validates whether sentence-transformer content embeddings can produce
sensible game similarity, which is the project's top technical risk.

Strategy:
  - 8 manually curated "dense clusters" of 10-15 games each (~180 total)
  - Fetch Steam appdetails (description + genres) and SteamSpy tags
  - Embed each game's combined text via multilingual MiniLM
  - For each game, find top-5 nearest neighbors
  - Measure: same-cluster hit rate (target >= 70%)

Usage:
    py -m pip install sentence-transformers requests numpy
    py scripts/embedding_probe.py

The first run fetches metadata (~5-7 min) and downloads the model (~500 MB).
Cache is saved to scripts/probe_games_cache.json — subsequent runs skip fetching.
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from sentence_transformers import SentenceTransformer


HERE = Path(__file__).parent
CACHE_PATH = HERE / "probe_games_cache.json"

STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAMSPY_URL = "https://steamspy.com/api.php"
REQUEST_INTERVAL = 1.5  # be polite to both APIs
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


# 8 dense clusters. Format: (appid, expected_title, cluster_id)
# Appids may have errors — script tolerates wrong fetches gracefully.
PROBE = [
    # === Roguelite Action (15) ===
    (1145360, "Hades", "roguelite_action"),
    (1145350, "Hades II", "roguelite_action"),
    (588650,  "Dead Cells", "roguelite_action"),
    (632360,  "Risk of Rain 2", "roguelite_action"),
    (1649240, "Returnal", "roguelite_action"),
    (311690,  "Enter the Gungeon", "roguelite_action"),
    (250900,  "The Binding of Isaac: Rebirth", "roguelite_action"),
    (242680,  "Nuclear Throne", "roguelite_action"),
    (1253920, "Rogue Legacy 2", "roguelite_action"),
    (1794680, "Vampire Survivors", "roguelite_action"),
    (1942280, "Brotato", "roguelite_action"),
    (1037020, "ScourgeBringer", "roguelite_action"),
    (418530,  "Spelunky 2", "roguelite_action"),
    (330840,  "Children of Morta", "roguelite_action"),
    (1313140, "Cult of the Lamb", "roguelite_action"),

    # === Deckbuilder Roguelite (10) ===
    (646570,  "Slay the Spire", "deckbuilder_rogue"),
    (2868840, "Slay the Spire 2", "deckbuilder_rogue"),
    (1102190, "Monster Train", "deckbuilder_rogue"),
    (1092790, "Inscryption", "deckbuilder_rogue"),
    (2379780, "Balatro", "deckbuilder_rogue"),
    (1811990, "Wildfrost", "deckbuilder_rogue"),
    (1385030, "Across the Obelisk", "deckbuilder_rogue"),
    (1252690, "Roguebook", "deckbuilder_rogue"),
    (1265800, "Fights in Tight Spaces", "deckbuilder_rogue"),
    (1466860, "Banners of Ruin", "deckbuilder_rogue"),

    # === Grand Strategy / 4X (11) ===
    (289070,  "Civilization VI", "grand_strategy"),
    (236850,  "Europa Universalis IV", "grand_strategy"),
    (281990,  "Stellaris", "grand_strategy"),
    (1158310, "Crusader Kings III", "grand_strategy"),
    (1142710, "Total War: WARHAMMER III", "grand_strategy"),
    (529340,  "Victoria 3", "grand_strategy"),
    (1669000, "Age of Wonders 4", "grand_strategy"),
    (392110,  "Endless Legend", "grand_strategy"),
    (1124300, "Humankind", "grand_strategy"),
    (597180,  "Old World", "grand_strategy"),
    (8930,    "Civilization V", "grand_strategy"),

    # === Open World RPG (11) ===
    (292030,  "The Witcher 3", "open_world_rpg"),
    (1245620, "Elden Ring", "open_world_rpg"),
    (1086940, "Baldur's Gate 3", "open_world_rpg"),
    (1091500, "Cyberpunk 2077", "open_world_rpg"),
    (489830,  "Skyrim Special Edition", "open_world_rpg"),
    (377160,  "Fallout 4", "open_world_rpg"),
    (379430,  "Kingdom Come: Deliverance", "open_world_rpg"),
    (560130,  "Pillars of Eternity II", "open_world_rpg"),
    (435150,  "Divinity: Original Sin 2", "open_world_rpg"),
    (1222690, "Dragon Age: Inquisition", "open_world_rpg"),
    (1328670, "Mass Effect Legendary Edition", "open_world_rpg"),

    # === Survival Crafting (11) ===
    (892970,  "Valheim", "survival_craft"),
    (252490,  "Rust", "survival_craft"),
    (322330,  "Don't Starve Together", "survival_craft"),
    (346110,  "ARK: Survival Evolved", "survival_craft"),
    (440900,  "Conan Exiles", "survival_craft"),
    (264710,  "Subnautica", "survival_craft"),
    (242760,  "The Forest", "survival_craft"),
    (1326470, "Sons of the Forest", "survival_craft"),
    (815370,  "Green Hell", "survival_craft"),
    (108600,  "Project Zomboid", "survival_craft"),
    (648800,  "Raft", "survival_craft"),

    # === Cozy / Life Sim (10) ===
    (413150,  "Stardew Valley", "cozy_life_sim"),
    (1158850, "Coral Island", "cozy_life_sim"),
    (1432860, "Sun Haven", "cozy_life_sim"),
    (972660,  "Spiritfarer", "cozy_life_sim"),
    (433340,  "Slime Rancher", "cozy_life_sim"),
    (1055540, "A Short Hike", "cozy_life_sim"),
    (1207170, "Cozy Grove", "cozy_life_sim"),
    (1401590, "Disney Dreamlight Valley", "cozy_life_sim"),
    (1859910, "My Time at Sandrock", "cozy_life_sim"),
    (1118200, "Unpacking", "cozy_life_sim"),

    # === Soulslike (7) ===
    (374320,  "Dark Souls III", "soulslike"),
    (814380,  "Sekiro: Shadows Die Twice", "soulslike"),
    (1627720, "Lies of P", "soulslike"),
    (1325200, "Nioh 2", "soulslike"),
    (697740,  "The Surge 2", "soulslike"),
    (1110910, "Mortal Shell", "soulslike"),
    (367520,  "Hollow Knight", "soulslike"),

    # === Narrative / Walking Sim (9) ===
    (632470,  "Disco Elysium", "narrative"),
    (753640,  "Outer Wilds", "narrative"),
    (1422680, "Pentiment", "narrative"),
    (501300,  "What Remains of Edith Finch", "narrative"),
    (383870,  "Firewatch", "narrative"),
    (221910,  "The Stanley Parable", "narrative"),
    (1221250, "NORCO", "narrative"),
    (1718580, "Citizen Sleeper", "narrative"),
    (232430,  "Gone Home", "narrative"),
]


def fetch_steam_appdetails(appid: int) -> Optional[dict]:
    """Fetch Steam Store appdetails. Returns parsed dict or {'_error': ...}."""
    try:
        r = requests.get(
            STEAM_APPDETAILS_URL,
            params={"appids": appid, "cc": "us", "l": "english"},
            timeout=15,
        )
    except requests.RequestException as e:
        return {"_error": f"request: {e}"}

    if r.status_code != 200:
        return {"_error": f"http {r.status_code}"}

    try:
        body = r.json()
    except ValueError:
        return {"_error": "non-json"}

    entry = body.get(str(appid))
    if not entry or not entry.get("success") or not entry.get("data"):
        return {"_error": "not in response or success=false"}

    data = entry["data"]
    return {
        "appid": appid,
        "name": data.get("name", ""),
        "short_description": data.get("short_description", ""),
        "genres": [g.get("description", "") for g in (data.get("genres") or [])],
        "categories": [c.get("description", "") for c in (data.get("categories") or [])],
        "type": data.get("type"),
    }


def fetch_steamspy_tags(appid: int) -> list[str]:
    """Fetch user-voted tags from SteamSpy. Returns list of tag names ordered by votes."""
    try:
        r = requests.get(
            STEAMSPY_URL,
            params={"request": "appdetails", "appid": appid},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        tags = data.get("tags") or {}
        if not isinstance(tags, dict):
            return []
        # SteamSpy returns {tag_name: vote_count}; sort desc, top 15
        return [t for t, _ in sorted(tags.items(), key=lambda kv: kv[1], reverse=True)[:15]]
    except (requests.RequestException, ValueError):
        return []


def build_cache(probe: list[tuple]) -> dict:
    """Fetch missing games into cache. Persists cache on disk."""
    cache: dict[str, dict] = {}
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Loaded cache: {len(cache)} entries")

    to_fetch = [g for g in probe if str(g[0]) not in cache]
    if not to_fetch:
        print("All games cached, skipping fetch")
        return cache

    eta_min = len(to_fetch) * REQUEST_INTERVAL / 60
    print(f"Fetching {len(to_fetch)} games (~{eta_min:.1f} min)...")

    for i, (appid, expected_name, cluster) in enumerate(to_fetch, 1):
        steam_data = fetch_steam_appdetails(appid)
        tags = fetch_steamspy_tags(appid)

        cache[str(appid)] = {
            "expected_name": expected_name,
            "cluster": cluster,
            "steam": steam_data,
            "tags": tags,
        }

        if steam_data and "_error" not in steam_data:
            actual = steam_data.get("name", "?")
            tag_preview = ", ".join(tags[:3]) if tags else "no tags"
            status = "OK"
        else:
            actual = "?"
            tag_preview = ""
            status = f"ERR ({steam_data.get('_error') if steam_data else 'none'})"

        print(f"[{i:3d}/{len(to_fetch)}] {appid:>8}  {expected_name[:28]:28} -> {actual[:32]:32} | {tag_preview[:30]:30} [{status}]")

        # Persist every 20 items to survive interruption
        if i % 20 == 0:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

        time.sleep(REQUEST_INTERVAL)

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"\nCache saved: {CACHE_PATH}")
    return cache


def build_text_for_embedding(entry: dict) -> str:
    """Compose embedding input. Tags carry most signal; description fills semantic gaps."""
    steam = entry.get("steam") or {}
    tags = entry.get("tags") or []
    parts = [
        steam.get("name", ""),
        steam.get("short_description", ""),
        " ".join(steam.get("genres", [])),
        " ".join(tags),  # SteamSpy user tags
    ]
    return " ".join(p for p in parts if p)


def main() -> None:
    cache = build_cache(PROBE)

    # Filter to usable entries
    usable = []
    for appid_str, entry in cache.items():
        steam = entry.get("steam") or {}
        if "_error" in steam:
            continue
        if not steam.get("name"):
            continue
        text = build_text_for_embedding(entry)
        if len(text) < 50:
            continue
        usable.append(
            {
                "appid": int(appid_str),
                "expected_name": entry["expected_name"],
                "cluster": entry["cluster"],
                "actual_name": steam.get("name", ""),
                "text": text,
                "tags": entry.get("tags") or [],
            }
        )

    print(f"\nUsable games: {len(usable)} / {len(PROBE)}")
    if len(usable) < 50:
        print("ERROR: Not enough usable games to run probe. Check fetch errors above.")
        sys.exit(1)

    print(f"\nLoading model: {MODEL_NAME}")
    print("(first run downloads ~500 MB)")
    model = SentenceTransformer(MODEL_NAME)

    texts = [u["text"] for u in usable]
    print(f"\nEmbedding {len(texts)} games...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.asarray(embeddings)

    # Cosine similarity = dot product since L2 normalized
    sim = embeddings @ embeddings.T

    K = 5
    hits_by_cluster: dict[str, list[tuple[str, int, int]]] = defaultdict(list)

    print("\n" + "=" * 80)
    print("Per-game nearest neighbors (top 5):")
    print("=" * 80)

    for i, u in enumerate(usable):
        sim_row = sim[i].copy()
        sim_row[i] = -1.0
        top_idx = np.argsort(sim_row)[-K:][::-1]

        hits = 0
        lines = []
        for j in top_idx:
            n = usable[j]
            same = n["cluster"] == u["cluster"]
            mark = "OK" if same else "  "
            if same:
                hits += 1
            lines.append(
                f"    [{mark}] {n['actual_name'][:35]:35} ({n['cluster']:>20})  sim {sim_row[j]:.3f}"
            )

        hits_by_cluster[u["cluster"]].append((u["actual_name"], hits, K))
        print(f"\n[{i+1:3d}/{len(usable)}] {u['actual_name'][:40]}  ({u['cluster']})")
        for line in lines:
            print(line)
        print(f"  -> same-cluster hits: {hits}/{K}  ({hits/K*100:.0f}%)")

    # Cluster summary
    print("\n" + "=" * 80)
    print("Cluster summary:")
    print("=" * 80)
    total_h = 0
    total_n = 0
    for cluster in sorted(hits_by_cluster):
        results = hits_by_cluster[cluster]
        h = sum(x[1] for x in results)
        n = sum(x[2] for x in results)
        rate = h / n * 100 if n else 0
        print(f"  {cluster:>22}  {h:>3}/{n:<3}  {rate:5.1f}%  ({len(results)} games)")
        total_h += h
        total_n += n

    print("\n" + "=" * 80)
    overall = total_h / total_n * 100 if total_n else 0
    print(f"Overall cluster hit rate: {total_h}/{total_n}  {overall:.1f}%")
    print()
    if overall >= 70:
        print("  >= 70%  ->  Embedding approach is viable. Proceed to Phase 1.")
    elif overall >= 50:
        print("  50-70%  ->  Borderline. Consider tag Jaccard hybrid.")
    else:
        print("  < 50%   ->  Embedding alone insufficient. Need alternative.")


if __name__ == "__main__":
    main()
