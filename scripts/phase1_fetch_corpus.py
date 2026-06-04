"""Phase 1: Fetch top ~5000 Steam games into local SQLite corpus.

Pipeline:
  1. Fetch top N appids from SteamSpy (paginated, by ownership)
  2. For each appid:
     - Steam Store appdetails (name, description, genres, header_image)
     - SteamSpy appdetails (user tags + vote counts, ownership, reviews)
  3. Persist to SQLite (games + game_tags tables)

Resumable: every 50 games it commits + already-fetched games are skipped on rerun.

Usage:
    # First time, test with small batch:
    py scripts/phase1_fetch_corpus.py --limit 50

    # Full run (~2 hours):
    py scripts/phase1_fetch_corpus.py

    # Resume after interrupt — just re-run, already-cached entries are skipped:
    py scripts/phase1_fetch_corpus.py
"""

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


# Windows default console codec (gbk / cp936) chokes on game names with
# non-ASCII glyphs like (R) or trademark signs. Force utf-8 with a safe
# fallback so a logged name never crashes the long fetch.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
DB_PATH = DATA_DIR / "corpus.db"

STEAM_URL = "https://store.steampowered.com/api/appdetails"
STEAMSPY_URL = "https://steamspy.com/api.php"

PAGES_TO_FETCH = 5            # SteamSpy 'all' returns ~1000 per page → 5 pages ≈ 5000 games
REQUEST_INTERVAL = 1.5        # seconds between game-level fetches
PAGE_INTERVAL = 2.0           # seconds between SteamSpy 'all' page fetches
CHECKPOINT_EVERY = 50         # commit + log every N games

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    appid               INTEGER PRIMARY KEY,
    name                TEXT,
    description         TEXT,
    genres              TEXT,        -- JSON list
    categories          TEXT,        -- JSON list
    type                TEXT,
    header_image        TEXT,
    release_date        TEXT,
    owners_low          INTEGER,
    owners_high         INTEGER,
    positive_reviews    INTEGER,
    negative_reviews    INTEGER,
    fetched_at          TEXT,
    fetch_status        TEXT          -- 'ok', 'steam_err:...', etc.
);

CREATE TABLE IF NOT EXISTS game_tags (
    appid               INTEGER NOT NULL,
    tag                 TEXT    NOT NULL,
    votes               INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (appid, tag),
    FOREIGN KEY (appid) REFERENCES games(appid)
);

CREATE INDEX IF NOT EXISTS idx_tags_tag    ON game_tags(tag);
CREATE INDEX IF NOT EXISTS idx_tags_appid  ON game_tags(appid);
CREATE INDEX IF NOT EXISTS idx_games_type  ON games(type);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def fetch_top_appids(pages: int) -> list[int]:
    """Return ordered list of unique appids from SteamSpy 'all' endpoint."""
    appids: list[int] = []
    seen: set[int] = set()
    for page in range(pages):
        print(f"  page {page}: ", end="", flush=True)
        try:
            r = requests.get(STEAMSPY_URL,
                             params={"request": "all", "page": page},
                             timeout=30)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            print(f"FAILED ({e})")
            continue

        page_count = 0
        if isinstance(data, dict):
            for key, info in data.items():
                if not isinstance(info, dict):
                    continue
                try:
                    appid = int(info.get("appid", key))
                except (ValueError, TypeError):
                    continue
                if appid not in seen:
                    seen.add(appid)
                    appids.append(appid)
                    page_count += 1
        print(f"+{page_count} unique (running total {len(appids)})")
        time.sleep(PAGE_INTERVAL)
    return appids


def fetch_steam_appdetails(appid: int) -> dict:
    try:
        r = requests.get(STEAM_URL,
                         params={"appids": appid, "cc": "us", "l": "english"},
                         timeout=15)
    except requests.RequestException as e:
        return {"_error": f"request: {e}"}
    if r.status_code != 200:
        return {"_error": f"http {r.status_code}"}
    try:
        body = r.json()
    except ValueError:
        return {"_error": "non-json"}

    entry = body.get(str(appid)) if isinstance(body, dict) else None
    if not entry or not entry.get("success") or not entry.get("data"):
        return {"_error": "no data"}

    data = entry["data"]
    return {
        "name": data.get("name", "") or "",
        "description": data.get("short_description", "") or "",
        "genres": [g.get("description", "") for g in (data.get("genres") or []) if g.get("description")],
        "categories": [c.get("description", "") for c in (data.get("categories") or []) if c.get("description")],
        "type": data.get("type", "") or "",
        "header_image": data.get("header_image", "") or "",
        "release_date": (data.get("release_date") or {}).get("date", "") or "",
    }


def fetch_steamspy_appdetails(appid: int) -> dict:
    try:
        r = requests.get(STEAMSPY_URL,
                         params={"request": "appdetails", "appid": appid},
                         timeout=15)
        if r.status_code != 200:
            return {"_error": f"http {r.status_code}"}
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        return {"_error": str(e)}

    if not isinstance(data, dict) or data.get("appid") is None:
        return {"_error": "no data"}

    tags_raw = data.get("tags") or {}
    tags = {}
    if isinstance(tags_raw, dict):
        for t, v in tags_raw.items():
            try:
                tags[str(t)] = int(v)
            except (ValueError, TypeError):
                continue

    owners = data.get("owners", "0..0") or "0..0"
    try:
        low, high = [int(x.strip().replace(",", "")) for x in owners.split("..")]
    except (ValueError, AttributeError):
        low, high = 0, 0

    def as_int(v) -> int:
        try:
            return int(v or 0)
        except (ValueError, TypeError):
            return 0

    return {
        "tags": tags,
        "owners_low": low,
        "owners_high": high,
        "positive": as_int(data.get("positive")),
        "negative": as_int(data.get("negative")),
    }


def already_fetched(conn: sqlite3.Connection, appid: int) -> bool:
    cur = conn.execute("SELECT fetch_status FROM games WHERE appid = ?", (appid,))
    row = cur.fetchone()
    if not row:
        return False
    return row[0] == "ok"


def persist_game(conn: sqlite3.Connection, appid: int, steam: dict, spy: dict) -> str:
    steam_err = "_error" in steam
    spy_err = "_error" in spy

    if steam_err and spy_err:
        status = f"both_err: steam={steam.get('_error','?')[:40]} spy={spy.get('_error','?')[:40]}"
    elif steam_err:
        status = f"steam_err: {steam['_error'][:80]}"
    elif spy_err:
        status = f"spy_err: {spy['_error'][:80]}"
    else:
        status = "ok"

    conn.execute("""
        INSERT OR REPLACE INTO games
        (appid, name, description, genres, categories, type, header_image, release_date,
         owners_low, owners_high, positive_reviews, negative_reviews,
         fetched_at, fetch_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        appid,
        steam.get("name", "") if not steam_err else "",
        steam.get("description", "") if not steam_err else "",
        json.dumps(steam.get("genres", []) if not steam_err else []),
        json.dumps(steam.get("categories", []) if not steam_err else []),
        steam.get("type", "") if not steam_err else "",
        steam.get("header_image", "") if not steam_err else "",
        steam.get("release_date", "") if not steam_err else "",
        spy.get("owners_low", 0) if not spy_err else 0,
        spy.get("owners_high", 0) if not spy_err else 0,
        spy.get("positive", 0) if not spy_err else 0,
        spy.get("negative", 0) if not spy_err else 0,
        datetime.now(timezone.utc).isoformat(),
        status,
    ))

    conn.execute("DELETE FROM game_tags WHERE appid = ?", (appid,))
    if not spy_err:
        for tag, votes in spy.get("tags", {}).items():
            conn.execute(
                "INSERT OR IGNORE INTO game_tags (appid, tag, votes) VALUES (?, ?, ?)",
                (appid, tag, votes),
            )
    return status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap games to fetch (for testing). Default: all from top pages.")
    ap.add_argument("--pages", type=int, default=PAGES_TO_FETCH,
                    help=f"SteamSpy 'all' pages to scrape. Default {PAGES_TO_FETCH} (~5000 games).")
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch even if already cached as 'ok'.")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    print(f"DB: {DB_PATH}")
    print(f"Step 1: fetching top appids from SteamSpy ({args.pages} pages)...")
    appids = fetch_top_appids(args.pages)
    print(f"  -> {len(appids)} unique appids ranked by ownership")

    if args.limit:
        appids = appids[:args.limit]
        print(f"  -> limited to first {len(appids)}")

    # Count what we already have
    if not args.force:
        n_cached = sum(1 for a in appids if already_fetched(conn, a))
        print(f"  -> {n_cached} already in cache, {len(appids) - n_cached} to fetch")

    eta_min = (len(appids) * 2 * REQUEST_INTERVAL) / 60
    print(f"\nStep 2: fetching metadata + tags (~{eta_min:.0f} min max if no cache)...\n")

    fetched = 0
    skipped = 0
    errored = 0

    for i, appid in enumerate(appids, 1):
        if not args.force and already_fetched(conn, appid):
            skipped += 1
            continue

        steam = fetch_steam_appdetails(appid)
        spy = fetch_steamspy_appdetails(appid)
        status = persist_game(conn, appid, steam, spy)

        if status == "ok":
            fetched += 1
            mark = "OK"
        else:
            errored += 1
            mark = "ERR"

        name = (steam.get("name") if "_error" not in steam else "?")[:38]
        tag_n = len(spy.get("tags", {})) if "_error" not in spy else 0
        owners = spy.get("owners_low", 0) if "_error" not in spy else 0

        print(f"[{i:5d}/{len(appids)}] {appid:>8}  {name:38}  tags={tag_n:>2}  owners={owners:>10}  [{mark}]")

        if i % CHECKPOINT_EVERY == 0:
            conn.commit()
            print(f"  -- checkpoint: fetched={fetched} skipped={skipped} errored={errored}")

        time.sleep(REQUEST_INTERVAL)

    conn.commit()

    # Final stats
    cur = conn.execute("SELECT COUNT(*) FROM games WHERE fetch_status = 'ok'")
    n_ok = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM game_tags")
    n_tags = cur.fetchone()[0]
    cur = conn.execute("""
        SELECT COUNT(DISTINCT appid) FROM game_tags
    """)
    n_with_tags = cur.fetchone()[0]

    print("\n" + "=" * 70)
    print(f"Processed this run:  {len(appids)}")
    print(f"  fetched:           {fetched}")
    print(f"  skipped (cached):  {skipped}")
    print(f"  errored:           {errored}")
    print()
    print(f"Total games in DB (status='ok'): {n_ok}")
    print(f"Total tag rows: {n_tags} across {n_with_tags} games")
    print(f"Avg tags per game: {n_tags / n_with_tags:.1f}" if n_with_tags else "")
    print(f"\nDB at: {DB_PATH}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Progress is saved (last commit). Re-run to resume.")
        sys.exit(130)
