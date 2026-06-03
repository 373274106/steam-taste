"""Steam Web API client.

Resolves user input (SteamID64, profile URL, vanity URL, vanity name) to a
canonical SteamID64, then fetches the user's owned games library with playtime.

Steam Web API docs: https://partner.steamgames.com/doc/webapi/IPlayerService

Privacy note: the user must have their Steam profile + game details set to
"Public" for GetOwnedGames to return data. We surface this in error messages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from .config import settings


STEAM_API_BASE = "https://api.steampowered.com"
REQUEST_TIMEOUT = 20

# SteamID64 = 17 digits, starts with 7656 for individual community accounts
_STEAMID64_RE = re.compile(r"^7656119\d{10}$")
_PROFILE_URL_RE = re.compile(r"steamcommunity\.com/profiles/(\d{17})", re.I)
_VANITY_URL_RE = re.compile(r"steamcommunity\.com/id/([\w\-]+)", re.I)
_VANITY_NAME_RE = re.compile(r"^[\w\-]{2,32}$")


class SteamApiError(Exception):
    """Raised when Steam API returns an error or unexpected response."""


@dataclass
class LibraryEntry:
    appid: int
    name: str
    playtime_minutes: int                  # all-time
    playtime_2weeks_minutes: int = 0       # recent
    icon_url: str = ""


def resolve_steamid(user_input: str) -> int:
    """Accept user input in any of these forms and return SteamID64:

      - 17-digit SteamID64:        76561198012345678
      - profile URL:               https://steamcommunity.com/profiles/76561198012345678
      - vanity URL:                https://steamcommunity.com/id/gaben
      - bare vanity name:          gaben

    Raises SteamApiError if input is unrecognizable or vanity doesn't resolve.
    """
    s = user_input.strip()
    if not s:
        raise SteamApiError("Empty input")

    if _STEAMID64_RE.match(s):
        return int(s)

    m = _PROFILE_URL_RE.search(s)
    if m:
        return int(m.group(1))

    m = _VANITY_URL_RE.search(s)
    if m:
        return _resolve_vanity(m.group(1))

    if _VANITY_NAME_RE.match(s):
        return _resolve_vanity(s)

    raise SteamApiError(
        f"Cannot interpret {user_input!r}. "
        f"Use a SteamID64, profile URL, vanity URL, or vanity name."
    )


def _resolve_vanity(vanity: str) -> int:
    key = settings.require_steam()
    try:
        r = requests.get(
            f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/",
            params={"key": key, "vanityurl": vanity},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise SteamApiError(f"Network error resolving vanity: {e}") from e

    if r.status_code != 200:
        raise SteamApiError(f"Vanity resolve HTTP {r.status_code}")

    try:
        body = r.json()
    except ValueError as e:
        raise SteamApiError(f"Vanity resolve returned non-JSON: {e}") from e

    payload = body.get("response", {}) or {}
    if payload.get("success") != 1:
        msg = payload.get("message") or "vanity URL not found"
        raise SteamApiError(f"Vanity '{vanity}' resolve failed: {msg}")

    return int(payload["steamid"])


def fetch_library(steamid: int) -> list[LibraryEntry]:
    """Fetch all owned games for a SteamID64.

    Returns empty list if the profile is private OR truly has no games —
    Steam Web API doesn't distinguish these cases.
    """
    key = settings.require_steam()
    try:
        r = requests.get(
            f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": key,
                "steamid": steamid,
                "include_appinfo": 1,
                "include_played_free_games": 1,
                "format": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise SteamApiError(f"Network error fetching library: {e}") from e

    if r.status_code != 200:
        raise SteamApiError(f"Library fetch HTTP {r.status_code}: {r.text[:200]}")

    try:
        body = r.json()
    except ValueError as e:
        raise SteamApiError(f"Library fetch returned non-JSON: {e}") from e

    payload = body.get("response", {}) or {}
    games = payload.get("games")

    if games is None:
        # Empty response — typically means private profile, but could be
        # a brand-new account with zero games. We surface both possibilities.
        raise SteamApiError(
            f"No library data for SteamID {steamid}. "
            f"Likely causes:\n"
            f"  1. Profile privacy set to Private or Friends Only\n"
            f"  2. Game details set to Private (separate setting)\n"
            f"  3. Account genuinely has no games\n"
            f"Fix: https://steamcommunity.com/my/edit/settings — "
            f"set both Profile and Game Details to Public."
        )

    if not isinstance(games, list):
        raise SteamApiError(f"Unexpected 'games' field type: {type(games)}")

    out = []
    for g in games:
        try:
            appid = int(g["appid"])
        except (KeyError, ValueError, TypeError):
            continue
        out.append(LibraryEntry(
            appid=appid,
            name=g.get("name", "") or "",
            playtime_minutes=int(g.get("playtime_forever", 0) or 0),
            playtime_2weeks_minutes=int(g.get("playtime_2weeks", 0) or 0),
            icon_url=g.get("img_icon_url", "") or "",
        ))
    return out


def fetch_player_summary(steamid: int) -> dict:
    """Optional: fetch profile name / avatar for display.

    Returns dict with keys: personaname, avatarfull, profileurl, etc.
    Returns empty dict if not retrievable.
    """
    key = settings.require_steam()
    try:
        r = requests.get(
            f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": key, "steamids": steamid},
            timeout=REQUEST_TIMEOUT,
        )
        body = r.json()
    except (requests.RequestException, ValueError):
        return {}

    players = (body.get("response") or {}).get("players") or []
    return players[0] if players else {}
