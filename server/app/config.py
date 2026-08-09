from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "streamdeck.sqlite3"
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret runtime settings for the local server."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    database_path: str | Path = DEFAULT_DATABASE_PATH

    @classmethod
    def from_env(cls) -> "Settings":
        """Read bind and SQLite settings from environment variables."""
        host = os.getenv("STREAMDECK_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
        raw_port = os.getenv("STREAMDECK_PORT", str(DEFAULT_PORT)).strip()
        database_path = os.getenv("STREAMDECK_DATABASE_PATH", "").strip()

        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("STREAMDECK_PORT must be an integer") from exc

        if not 1 <= port <= 65535:
            raise ValueError("STREAMDECK_PORT must be between 1 and 65535")

        return cls(
            host=host,
            port=port,
            database_path=database_path or DEFAULT_DATABASE_PATH,
        )
