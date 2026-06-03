"""Configuration loader. Reads secrets from env vars; falls back to .env file.

Why env vars: secrets must NOT live in source. The .env file is gitignored,
so it can hold local dev secrets without risk of being committed.

Usage:
    from backend.config import settings
    api_key = settings.steam_api_key
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_ENV_FILE = Path(__file__).parent.parent / ".env"


def _load_dotenv() -> None:
    """Minimal .env loader (no external dep). Only loads vars not already set."""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    steam_api_key: str = os.environ.get("STEAM_API_KEY", "")
    # URLs used by the OpenID return-to / frontend-redirect. Override in prod.
    frontend_base: str = os.environ.get("FRONTEND_BASE", "http://localhost:5173")
    backend_base: str = os.environ.get("BACKEND_BASE", "http://localhost:8000")

    def require_steam(self) -> str:
        if not self.steam_api_key:
            raise RuntimeError(
                "STEAM_API_KEY not set. Set it via environment variable or .env file. "
                "Get a key at https://steamcommunity.com/dev/apikey"
            )
        return self.steam_api_key


settings = Settings()
