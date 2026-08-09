from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.migrations import migrate

DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "streamdeck.sqlite3"
)


def resolve_database_path(path: str | Path | None = None) -> str | Path:
    """Resolve a database path without emitting or storing runtime secrets."""
    if path is not None:
        if str(path) == ":memory:":
            return ":memory:"
        return Path(path).expanduser()

    configured = os.getenv("STREAMDECK_DATABASE_PATH", "").strip()
    if not configured:
        return DEFAULT_DATABASE_PATH
    if configured == ":memory:":
        return ":memory:"
    return Path(configured).expanduser()


class Database:
    """Small SQLite connection manager for the local Stream Deck server."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = resolve_database_path(path)

    def connect(self) -> sqlite3.Connection:
        """Open a connection with row access and foreign-key enforcement."""
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(str(self.path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Apply all migrations to the configured database."""
        with self.connect() as connection:
            migrate(connection)

    migrate = initialize

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection in an all-or-nothing write transaction."""
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
