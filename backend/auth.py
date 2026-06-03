"""Steam OpenID 2.0 helpers.

Flow:
  1. Frontend → GET /api/auth/steam/login on this backend
  2. Backend builds Steam OpenID URL with return_to pointing back to /callback
  3. Steam → /api/auth/steam/callback with signed params
  4. Backend POSTs all params back to Steam with mode=check_authentication
     to verify the signature
  5. If valid, extract SteamID64 from openid.claimed_id and redirect frontend
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Optional

import requests


OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
OPENID_NS = "http://specs.openid.net/auth/2.0"
CLAIMED_ID_PATTERN = re.compile(r"openid/id/(\d{17})")
REQUEST_TIMEOUT = 15


def build_login_url(return_to: str, realm: str) -> str:
    """Construct the URL to redirect users to for Steam OpenID login."""
    params = {
        "openid.ns":          OPENID_NS,
        "openid.mode":        "checkid_setup",
        "openid.return_to":   return_to,
        "openid.realm":       realm,
        "openid.identity":    "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id":  "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{OPENID_ENDPOINT}?{urllib.parse.urlencode(params)}"


def verify_callback(query_params: dict[str, str]) -> Optional[int]:
    """Verify a Steam OpenID callback by re-POSTing to Steam for signature check.

    Returns SteamID64 on success, None on failure.
    """
    if query_params.get("openid.mode") != "id_res":
        return None

    # Build verification payload — every openid.* param, with mode swapped
    verify_payload = {
        k: v for k, v in query_params.items() if k.startswith("openid.")
    }
    verify_payload["openid.mode"] = "check_authentication"

    try:
        r = requests.post(
            OPENID_ENDPOINT,
            data=verify_payload,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "SteamTasteLens/1.0"},
        )
    except requests.RequestException:
        return None

    if r.status_code != 200:
        return None
    if "is_valid:true" not in r.text:
        return None

    claimed = query_params.get("openid.claimed_id") or ""
    m = CLAIMED_ID_PATTERN.search(claimed)
    if not m:
        return None
    return int(m.group(1))
