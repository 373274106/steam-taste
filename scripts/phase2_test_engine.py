"""Phase 2 Step A: end-to-end test of the taste engine on a demo user.

Hardcodes a believable Steam library (no API needed), computes taste vector,
runs recommendations + similar-game queries, and prints human-readable output.

Use this to validate engine output before plugging in real Steam library data.

Usage:
    py scripts/phase2_test_engine.py
"""

import sys
from pathlib import Path

# Allow importing backend from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from backend.taste_engine import (
    TasteEngine,
    format_recommendations,
    format_taste_profile,
)


# A believable Steam library: a player who's deeply into roguelites + grand strategy,
# with some open-world RPG and a few "bought but barely played" impulse buys.
# Format: (appid, playtime_minutes)
DEMO_LIBRARY: list[tuple[int, int]] = [
    # === Deep loves: roguelite cluster ===
    (1145360, 130 * 60),   # Hades — 130h
    (632360,   65 * 60),   # Risk of Rain 2 — 65h
    (588650,   40 * 60),   # Dead Cells — 40h
    (646570,   70 * 60),   # Slay the Spire — 70h
    (2379780,  45 * 60),   # Balatro — 45h
    (1102190,  35 * 60),   # Monster Train — 35h
    (1092790,  20 * 60),   # Inscryption — 20h
    (1794680,  18 * 60),   # Vampire Survivors — 18h
    (1313140,  12 * 60),   # Cult of the Lamb — 12h
    (367520,   25 * 60),   # Hollow Knight — 25h

    # === Deep loves: grand strategy cluster ===
    (289070,  200 * 60),   # Civilization VI — 200h
    (281990,  120 * 60),   # Stellaris — 120h
    (236850,   80 * 60),   # Europa Universalis IV — 80h
    (1158310,  60 * 60),   # Crusader Kings III — 60h
    (8930,     40 * 60),   # Civilization V — 40h

    # === Moderate engagement: open-world RPG ===
    (292030,   90 * 60),   # The Witcher 3 — 90h
    (1086940,  35 * 60),   # Baldur's Gate 3 — 35h
    (489830,   30 * 60),   # Skyrim — 30h
    (413150,   30 * 60),   # Stardew Valley — 30h

    # === Regret cluster: bought but barely played (survival craft) ===
    (264710,    1 * 60),   # Subnautica — 1h
    (892970,    2 * 60),   # Valheim — 2h
    (346110,    0.5*60),   # ARK — 30 min
    (252490,    0.3*60),   # Rust — 18 min
    (440900,    0.8*60),   # Conan Exiles — 48 min

    # === Regret cluster 2: narrative games user thought they'd like ===
    (753640,    0.5*60),   # Outer Wilds — 30 min
    (632470,    1.5*60),   # Disco Elysium — 1.5h
]


def main() -> None:
    print("Loading Taste Engine...")
    engine = TasteEngine()
    print(f"  corpus: {engine.corpus_size} games, vocab: {len(engine.vocab)} tags\n")

    library = [(a, int(p)) for a, p in DEMO_LIBRARY]
    owned = {a for a, _ in library}

    # --- Layer 3: compute taste vector ---
    taste, stats = engine.compute_taste_vector(library)
    print(format_taste_profile(engine, taste, stats))
    print()

    # --- Layer 3 query: recommendations (best_fit) ---
    best_fit = engine.recommend(taste, owned, k=8, mode="best_fit")
    print(format_recommendations(engine, best_fit, taste, library, "Best Fit Recommendations"))

    # --- Layer 3 query: hidden gem mode ---
    hidden = engine.recommend(taste, owned, k=8, mode="hidden_gem")
    print(format_recommendations(engine, hidden, taste, library, "Hidden Gems (popularity-penalized)"))

    # --- Layer 2 query: similar-to-target ---
    print("\n\n=== Similar games to 'Hades' (game-game query) ===")
    similar = engine.similar_to_game(1145360, k=8)
    for appid, score in similar:
        ref = engine.game_ref(appid)
        print(f"  [{appid:>8}] {ref.name:<40}  sim {score:.3f}  | {', '.join(ref.tags[:4])}")

    print("\n\n=== Similar games to 'Civilization VI' ===")
    similar = engine.similar_to_game(289070, k=8)
    for appid, score in similar:
        ref = engine.game_ref(appid)
        print(f"  [{appid:>8}] {ref.name:<40}  sim {score:.3f}  | {', '.join(ref.tags[:4])}")

    print("\n\n=== Similar games to 'Stardew Valley' ===")
    similar = engine.similar_to_game(413150, k=8)
    for appid, score in similar:
        ref = engine.game_ref(appid)
        print(f"  [{appid:>8}] {ref.name:<40}  sim {score:.3f}  | {', '.join(ref.tags[:4])}")


if __name__ == "__main__":
    main()
