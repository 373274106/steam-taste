"""Build EN -> ZH tag name map from Steam's official populartags endpoint.

Two API calls (one per language), join by tagid, drop to JSON.

Output:
    data/tag_i18n.json                  - canonical EN->ZH map (all Steam tags)
    frontend/src/locales/tag_i18n.json  - same content, vendored next to other locales

Usage:
    py scripts/build_tag_i18n.py
"""

import json
import sys
from pathlib import Path

import requests


HERE = Path(__file__).parent
ROOT = HERE.parent
VOCAB_PATH = ROOT / "data" / "tag_vocab.json"
OUT_DATA = ROOT / "data" / "tag_i18n.json"
OUT_FRONTEND = ROOT / "frontend" / "src" / "locales" / "tag_i18n.json"

URL = "https://store.steampowered.com/tagdata/populartags/{lang}"

# SteamSpy uses different spellings than Steam's official taxonomy for a few
# tags. We bridge by lookup against the Steam taxonomy under the alt name.
ALT_NAMES: dict[str, str] = {
    "Rogue-like": "Roguelike",
    "Rogue-lite": "Roguelite",
    "Base-Building": "Base Building",
    "Puzzle-Platformer": "Puzzle Platformer",
}

# Tags Steam does not localize but we want translated anyway. Hand-curated.
MANUAL_OVERRIDES: dict[str, str] = {
    "Roguevania": "类银河战士肉鸽",
}


def fetch(lang: str) -> list[dict]:
    r = requests.get(URL.format(lang=lang), timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> None:
    print(f"Fetching populartags/english + populartags/schinese ...")
    en = fetch("english")
    zh = fetch("schinese")
    print(f"  en: {len(en)} tags, zh: {len(zh)} tags")

    zh_by_id: dict[int, str] = {}
    for row in zh:
        tid = row.get("tagid")
        name = row.get("name")
        if isinstance(tid, int) and isinstance(name, str) and name:
            zh_by_id[tid] = name

    mapping: dict[str, str] = {}
    skipped = 0
    for row in en:
        tid = row.get("tagid")
        en_name = row.get("name")
        if not isinstance(tid, int) or not isinstance(en_name, str) or not en_name:
            skipped += 1
            continue
        zh_name = zh_by_id.get(tid)
        if not zh_name:
            skipped += 1
            continue
        mapping[en_name] = zh_name

    # Apply SteamSpy<->Steam name bridges: if SteamSpy name X aliases to Steam
    # name Y and Y is in the map, surface as X also.
    for spy_name, store_name in ALT_NAMES.items():
        if store_name in mapping and spy_name not in mapping:
            mapping[spy_name] = mapping[store_name]

    # Hand-curated overrides (Steam doesn't ship these in localized lists)
    for en_name, zh_name in MANUAL_OVERRIDES.items():
        if en_name not in mapping:
            mapping[en_name] = zh_name

    print(f"  built en->zh map: {len(mapping)} entries "
          f"(skipped {skipped} unmatched, +{len(ALT_NAMES)} aliases, "
          f"+{len(MANUAL_OVERRIDES)} manual)")

    # Coverage check against our actual corpus vocab
    if VOCAB_PATH.exists():
        with VOCAB_PATH.open(encoding="utf-8") as f:
            vocab = json.load(f)
        covered = [t for t in vocab if t in mapping]
        missing = [t for t in vocab if t not in mapping]
        print(f"\nCoverage vs data/tag_vocab.json ({len(vocab)} tags):")
        print(f"  covered: {len(covered)} ({len(covered) / len(vocab) * 100:.1f}%)")
        print(f"  missing: {len(missing)}")
        if missing:
            print("  missing tags (these will stay in English in zh mode):")
            for t in missing:
                print(f"    - {t}")

    # Write outputs
    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_FRONTEND.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True)
    OUT_DATA.write_text(payload, encoding="utf-8")
    OUT_FRONTEND.write_text(payload, encoding="utf-8")
    print(f"\nWrote:")
    print(f"  {OUT_DATA}")
    print(f"  {OUT_FRONTEND}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        print(f"network error: {e}", file=sys.stderr)
        sys.exit(1)
