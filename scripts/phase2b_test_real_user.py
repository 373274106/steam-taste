"""Phase 2B test: end-to-end pipeline with a real Steam library.

Usage:
    py scripts/phase2b_test_real_user.py <steamid_or_url_or_vanity>

Examples:
    py scripts/phase2b_test_real_user.py 76561198012345678
    py scripts/phase2b_test_real_user.py https://steamcommunity.com/id/gabelogannewell
    py scripts/phase2b_test_real_user.py gabelogannewell

Pipeline:
    1. Resolve user input to SteamID64
    2. Fetch player summary (display name)
    3. Fetch owned games + playtime
    4. Compute taste vector + show profile
    5. Best Fit recommendations
    6. Hidden Gem recommendations
    7. Library Regret report
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows console defaults to cp936/gbk in zh-CN locale — can't print ™ ® etc.
# Force stdout to UTF-8 with replacement for any unrepresentable chars.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from backend.regret_detector import detect_regret, format_regret_report
from backend.steam_client import (
    SteamApiError,
    fetch_library,
    fetch_player_summary,
    resolve_steamid,
)
from backend.taste_engine import (
    TasteEngine,
    format_recommendations,
    format_taste_profile,
)


def run(user_input: str, out_stream) -> None:
    """Run the full pipeline, writing output to out_stream (text mode, UTF-8 capable)."""
    def w(s: str = "") -> None:
        out_stream.write(s + "\n")
        out_stream.flush()

    w(f"Resolving input: {user_input}")
    try:
        steamid = resolve_steamid(user_input)
    except SteamApiError as e:
        w(f"  FAILED: {e}")
        sys.exit(1)
    w(f"  -> SteamID64: {steamid}")

    summary = fetch_player_summary(steamid)
    if summary:
        w(f"  -> persona:   {summary.get('personaname', '?')}")

    w("\nFetching library...")
    try:
        entries = fetch_library(steamid)
    except SteamApiError as e:
        w(f"\nFAILED:\n{e}")
        sys.exit(1)

    if not entries:
        w("Library is empty (or filtered to zero). Nothing to analyze.")
        return

    entries.sort(key=lambda e: -e.playtime_minutes)
    w(f"  -> {len(entries)} games fetched")
    w("\nTop 10 by playtime:")
    for e in entries[:10]:
        w(f"  {e.name[:40]:40}  {e.playtime_minutes/60:>7.1f}h")
    w(f"\nTotal playtime: {sum(e.playtime_minutes for e in entries) / 60:.0f} hours")

    library = [(e.appid, e.playtime_minutes) for e in entries]

    w("\nLoading Taste Engine...")
    engine = TasteEngine()
    w(f"  corpus: {engine.corpus_size} games")

    taste, stats = engine.compute_taste_vector(library)
    w()
    w(format_taste_profile(engine, taste, stats))

    owned = {a for a, _ in library}

    best_fit = engine.recommend(taste, owned, k=8, mode="best_fit")
    w(format_recommendations(engine, best_fit, taste, library, "Best Fit Recommendations"))

    hidden = engine.recommend(taste, owned, k=5, mode="hidden_gem")
    w(format_recommendations(engine, hidden, taste, library, "Hidden Gems"))

    if stats["in_corpus"] >= 5:
        report = detect_regret(engine, library)
        w(format_regret_report(engine, report))
    else:
        w(f"\n(Library coverage {stats['in_corpus']} games — too few for regret clustering.)")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("steam_input", help="SteamID64, profile URL, or vanity name")
    ap.add_argument("--out", help="Write output to this file (UTF-8) instead of stdout. "
                                  "Recommended on Windows to avoid PowerShell encoding issues.")
    args = ap.parse_args()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            print(f"Writing output to {out_path}...")
            run(args.steam_input, f)
        print(f"Done. Open the file to view the report.")
    else:
        run(args.steam_input, sys.stdout)


if __name__ == "__main__":
    main()
