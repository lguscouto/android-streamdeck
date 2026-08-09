from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "streamdeck.sqlite3"
)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_PAIRING_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,63}$", re.ASCII)


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret runtime settings for the local server."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    database_path: str | Path = DEFAULT_DATABASE_PATH
    pairing_code: str | None = None
    require_auth: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        code = self.pairing_code
        if code is not None and not _PAIRING_CODE_PATTERN.fullmatch(code):
            raise ValueError(
                "pairing_code must contain 6-64 ASCII letters, digits, '.', '_' or '-'"
            )
        if self.require_auth and code is None:
            raise ValueError("authentication requires a pairing code")
        if self.host.strip().lower() not in _LOOPBACK_HOSTS and not self.require_auth:
            raise ValueError("remote bind requires authentication")

    @classmethod
    def from_env(cls) -> "Settings":
        """Read bind, SQLite, and pairing settings from environment variables."""
        host = os.getenv("STREAMDECK_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
        raw_port = os.getenv("STREAMDECK_PORT", str(DEFAULT_PORT)).strip()
        database_path = os.getenv("STREAMDECK_DATABASE_PATH", "").strip()
        pairing_code = os.getenv("STREAMDECK_PAIRING_CODE", "").strip() or None
        raw_require_auth = os.getenv("STREAMDECK_REQUIRE_AUTH", "").strip().lower()

        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("STREAMDECK_PORT must be an integer") from exc

        if raw_require_auth in {"", "auto"}:
            require_auth = pairing_code is not None
        elif raw_require_auth in {"1", "true", "yes", "on"}:
            require_auth = True
        elif raw_require_auth in {"0", "false", "no", "off"}:
            require_auth = False
        else:
            raise ValueError("STREAMDECK_REQUIRE_AUTH must be a boolean")

        return cls(
            host=host,
            port=port,
            database_path=database_path or DEFAULT_DATABASE_PATH,
            pairing_code=pairing_code,
            require_auth=require_auth,
        )
