"""ITAD appid matching probe.

Validates how well Steam appids can be matched to IsThereAnyDeal game IDs.
This is the project's top technical risk — if matching rate is low, the
price module needs rethinking.

Usage:
    Set env var, then run:
        $env:ITAD_API_KEY = "your_key_here"
        py scripts\itad_match_probe.py

Get a free API key: https://isthereanydeal.com/dev/app/

Dependencies:
    py -m pip install requests
"""

import csv
import os
import sys
import time
from pathlib import Path

import requests


API_KEY = os.getenv("ITAD_API_KEY")
ITAD_LOOKUP_URL = "https://api.isthereanydeal.com/games/lookup/v1"
SLEEP_BETWEEN_REQUESTS = 0.6  # be polite to ITAD


# Curated probe set: 50 unique Steam games chosen to stress different
# matching scenarios (AAA, indie, remasters, F2P, renamed, new releases).
PROBE_GAMES = [
    # AAA / top sellers
    (1086940, "Baldur's Gate 3", "AAA RPG"),
    (1245620, "Elden Ring", "AAA Soulslike"),
    (1091500, "Cyberpunk 2077", "AAA, multiple editions"),
    (1174180, "Red Dead Redemption 2", "AAA"),
    (271590, "Grand Theft Auto V", "AAA classic"),
    (990080, "Hogwarts Legacy", "AAA 2023"),
    (2358720, "Black Myth: Wukong", "AAA 2024"),
    (1623730, "Palworld", "2024 viral"),
    (2073850, "THE FINALS", "F2P shooter"),
    (814380, "Sekiro: Shadows Die Twice", "AAA"),

    # Remasters / edge cases for ID matching
    (2050650, "Resident Evil 4", "Remake of 2005 game"),
    (570940, "Dark Souls: Remastered", "Remaster"),
    (1817070, "Marvel's Spider-Man Remastered", "Remaster"),
    (813780, "Age of Empires II: DE", "Definitive Edition"),
    (1817190, "Marvel's Spider-Man: Miles Morales", "Recent"),

    # Indie classics
    (1145360, "Hades", "Indie"),
    (588650, "Dead Cells", "Indie roguelike"),
    (646570, "Slay the Spire", "Indie deckbuilder"),
    (413150, "Stardew Valley", "Indie farming"),
    (367520, "Hollow Knight", "Indie metroidvania"),
    (105600, "Terraria", "Indie classic"),
    (294100, "RimWorld", "Indie sim"),
    (526870, "Satisfactory", "Indie factory"),
    (632360, "Risk of Rain 2", "Indie roguelike"),
    (1888160, "Cult of the Lamb", "Indie 2022"),

    # F2P / live service (renamed / merged accounts)
    (730, "Counter-Strike 2", "Renamed from CS:GO"),
    (570, "Dota 2", "F2P MOBA"),
    (578080, "PUBG: BATTLEGROUNDS", "Renamed"),
    (252490, "Rust", "Survival"),
    (359550, "Rainbow Six Siege", "AAA F2P-like"),
    (440, "Team Fortress 2", "Very old F2P"),

    # Strategy
    (289070, "Civilization VI", "Strategy"),
    (236850, "Europa Universalis IV", "Grand strategy"),
    (281990, "Stellaris", "Grand strategy"),
    (1196590, "Total War: WARHAMMER III", "Strategy"),
    (261550, "Mount & Blade II: Bannerlord", "Strategy/action"),
    (8930, "Civilization V", "Older"),

    # Mid-tier / older
    (374320, "Dark Souls III", "AAA"),
    (752590, "A Plague Tale: Innocence", "Mid-tier"),
    (1659040, "HUMANKIND", "Strategy mid-tier"),
    (275850, "No Man's Sky", "Mid-tier"),
    (1238810, "Battlefield V", "AAA shooter"),
    (1517290, "Battlefield 2042", "AAA shooter"),
    (1172380, "STAR WARS Jedi: Fallen Order", "AAA"),

    # Indie F2P / viral
    (322330, "Don't Starve Together", "Indie"),
    (945360, "Among Us", "Indie viral"),
    (304930, "Unturned", "Indie F2P"),
    (1599340, "Lost Ark", "F2P MMO"),

    # Recent obscure-ish
    (1604030, "Splitgate", "Indie F2P shooter"),
    (892970, "Valheim", "Indie survival"),
]


def lookup_appid(appid: int, key: str) -> dict:
    """Call ITAD lookup. Returns a normalized result dict."""
    try:
        r = requests.get(
            ITAD_LOOKUP_URL,
            params={"key": key, "appid": appid},
            timeout=10,
        )
    except requests.RequestException as e:
        return {"status": "request_error", "error": str(e)}

    if r.status_code != 200:
        return {
            "status": "http_error",
            "code": r.status_code,
            "body": r.text[:300],
        }

    try:
        data = r.json()
    except ValueError as e:
        return {"status": "json_error", "error": str(e), "body": r.text[:300]}

    # Defensively normalize across possible ITAD response shapes.
    found = False
    game_info = None

    if isinstance(data, dict):
        if "found" in data:
            # v2 shape: { "found": true, "game": {...} }
            found = bool(data.get("found"))
            game_info = data.get("game")
        elif str(appid) in data:
            # legacy v01 shape: { "<appid>": {...} or null }
            entry = data[str(appid)]
            found = bool(entry)
            game_info = entry if isinstance(entry, dict) else None
        elif "id" in data or "title" in data:
            # direct game object
            found = True
            game_info = data

    return {"status": "ok", "found": found, "game": game_info, "raw": data}


def main() -> None:
    if not API_KEY:
        print("ERROR: Set ITAD_API_KEY env var before running.")
        print("  PowerShell:  $env:ITAD_API_KEY = \"your_key_here\"")
        print("  Get a key:   https://isthereanydeal.com/dev/app/")
        sys.exit(1)

    # Dedupe by appid (in case the list has stray duplicates)
    seen = set()
    games = []
    for entry in PROBE_GAMES:
        if entry[0] not in seen:
            seen.add(entry[0])
            games.append(entry)

    print(f"Probing {len(games)} games against ITAD lookup endpoint")
    print(f"Endpoint: {ITAD_LOOKUP_URL}")
    print()

    results = []
    matched = 0
    not_found = 0
    errors = 0
    first_error_shown = False

    for i, (appid, title, notes) in enumerate(games, 1):
        r = lookup_appid(appid, API_KEY)
        status = r["status"]

        if status == "ok":
            if r["found"] and r["game"]:
                g = r["game"]
                itad_id = g.get("id") or g.get("plain") or ""
                itad_title = g.get("title") or ""
                results.append((appid, title, "MATCHED", itad_id, itad_title, notes))
                matched += 1
                print(f"[{i:3d}/{len(games)}] OK   {appid:>8}  {title[:32]:32} -> {itad_title[:40]}")
            else:
                results.append((appid, title, "NOT_FOUND", "", "", notes))
                not_found += 1
                print(f"[{i:3d}/{len(games)}] MISS {appid:>8}  {title[:32]:32} -> not found")
        else:
            errors += 1
            err_detail = r.get("error") or r.get("body") or r.get("code") or "?"
            results.append((appid, title, f"ERR_{status}", "", str(err_detail)[:200], notes))
            print(f"[{i:3d}/{len(games)}] ERR  {appid:>8}  {title[:32]:32} -> {status}")
            if not first_error_shown:
                print(f"          full first error: {r}")
                first_error_shown = True
                if status in ("http_error",) and r.get("code") in (401, 403):
                    print()
                    print("Auth error from ITAD. Stopping early.")
                    print("Check your API key is correct and active.")
                    break

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # Write CSV next to the script
    out_csv = Path(__file__).parent / "probe_results.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["appid", "steam_title", "status", "itad_id", "itad_title_or_error", "notes"]
        )
        for row in results:
            w.writerow(row)

    total = len(games)
    print()
    print("=" * 60)
    print(f"Total:     {total}")
    print(f"Matched:   {matched}  ({matched / total * 100:.1f}%)")
    print(f"Not found: {not_found}  ({not_found / total * 100:.1f}%)")
    print(f"Errors:    {errors}  ({errors / total * 100:.1f}%)")
    print()
    print(f"Detailed results: {out_csv}")
    print()

    usable = total - errors
    if usable > 0:
        rate = matched / usable * 100
        print(f"Match rate (excluding API errors): {rate:.1f}%")
        print()
        if rate >= 90:
            print("  >= 90% -> Proceed with current plan.")
        elif rate >= 70:
            print("  70-90% -> Add fuzzy fallback (name + release year), then proceed.")
        else:
            print("  < 70% -> Consider alternative price data source.")


if __name__ == "__main__":
    main()
