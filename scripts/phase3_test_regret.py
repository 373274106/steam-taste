"""Phase 3 test: run Regret detector on the demo user library.

Uses the same DEMO_LIBRARY as phase2_test_engine.py — should identify:
  - Roguelite cluster (high playtime, NOT regret)
  - Grand strategy cluster (high playtime, NOT regret)
  - Survival craft cluster (low playtime, REGRET)
  - Narrative cluster (low playtime, REGRET — though small)

Usage:
    py scripts/phase3_test_regret.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from backend.regret_detector import detect_regret, format_regret_report
from backend.taste_engine import TasteEngine
from scripts.phase2_test_engine import DEMO_LIBRARY


def main() -> None:
    print("Loading Taste Engine...")
    engine = TasteEngine()
    print(f"  corpus: {engine.corpus_size} games\n")

    library = [(a, int(p)) for a, p in DEMO_LIBRARY]

    print("Running HDBSCAN clustering + regret detection...")
    report = detect_regret(engine, library)
    print(format_regret_report(engine, report))


if __name__ == "__main__":
    main()
