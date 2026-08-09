from __future__ import annotations

import os
import sqlite3
import threading
import uuid
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
        self._is_memory = self.path == ":memory:"
        self._connect_target = (
            f"file:streamdeck-{uuid.uuid4().hex}?mode=memory&cache=shared"
            if self._is_memory
            else str(self.path)
        )
        self._memory_keepalive: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

    def connect(self) -> sqlite3.Connection:
        """Open a connection with row access and foreign-key enforcement."""
        if not self._is_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            if self._is_memory and self._memory_keepalive is None:
                keepalive = sqlite3.connect(
                    self._connect_target,
                    timeout=30.0,
                    uri=True,
                    check_same_thread=False,
                )
                self._configure_connection(keepalive)
                self._memory_keepalive = keepalive

            connection = sqlite3.connect(
                self._connect_target,
                timeout=30.0,
                uri=self._is_memory,
            )
            self._configure_connection(connection)
            return connection

    def close(self) -> None:
        """Release the private keep-alive connection for an in-memory database."""
        with self._lock:
            if self._memory_keepalive is not None:
                self._memory_keepalive.close()
                self._memory_keepalive = None

    release = close

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
