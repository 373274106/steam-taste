"""Demo user library — used when caller hits /api/demo/* or passes the demo sentinel.

This is a hand-crafted, plausible library showcasing the engine's outputs:
strong roguelite + grand strategy + open-world RPG clusters, plus a few
"bought but barely played" picks to demonstrate the Regret detector.

Avoid using positive SteamID values here so we can never collide with a real
SteamID64 (those are always 17-digit positive integers starting with 7656).
"""

DEMO_STEAMID = -1
DEMO_PERSONA = "Demo Player"
DEMO_AVATAR = ""

# (appid, playtime_minutes)
DEMO_LIBRARY: list[tuple[int, int]] = [
    # === Deep loves: roguelite cluster ===
    (1145360, 130 * 60),   # Hades
    (632360,   65 * 60),   # Risk of Rain 2
    (588650,   40 * 60),   # Dead Cells
    (646570,   70 * 60),   # Slay the Spire
    (2379780,  45 * 60),   # Balatro
    (1102190,  35 * 60),   # Monster Train
    (1092790,  20 * 60),   # Inscryption
    (1794680,  18 * 60),   # Vampire Survivors
    (1313140,  12 * 60),   # Cult of the Lamb
    (367520,   25 * 60),   # Hollow Knight

    # === Deep loves: grand strategy cluster ===
    (289070,  200 * 60),   # Civilization VI
    (281990,  120 * 60),   # Stellaris
    (236850,   80 * 60),   # Europa Universalis IV
    (1158310,  60 * 60),   # Crusader Kings III
    (8930,     40 * 60),   # Civilization V

    # === Moderate engagement: open-world RPG ===
    (292030,   90 * 60),   # The Witcher 3
    (1086940,  35 * 60),   # Baldur's Gate 3
    (489830,   30 * 60),   # Skyrim
    (413150,   30 * 60),   # Stardew Valley

    # === Regret cluster: bought but barely played (survival craft) ===
    (264710,    1 * 60),   # Subnautica
    (892970,    2 * 60),   # Valheim
    (346110,        30),   # ARK
    (252490,        18),   # Rust
    (440900,        48),   # Conan Exiles

    # === Sleeping individual games ===
    (753640,        30),   # Outer Wilds
    (632470,       90),    # Disco Elysium
]
