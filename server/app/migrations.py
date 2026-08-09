from __future__ import annotations

import sqlite3

LATEST_SCHEMA_VERSION = 1
_REQUIRED_TABLES = frozenset(
    {"profiles", "pages", "buttons", "actions", "profile_revisions"}
)


class MigrationError(RuntimeError):
    """Raised when the local SQLite schema cannot be migrated safely."""


_SCHEMA_V1 = (
    """
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        protocol_version INTEGER NOT NULL CHECK (protocol_version = 1),
        name TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 1),
        active_page_id TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (id, active_page_id)
            REFERENCES pages(profile_id, id)
            DEFERRABLE INITIALLY DEFERRED
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pages (
        profile_id TEXT NOT NULL,
        id TEXT NOT NULL,
        title TEXT NOT NULL,
        order_index INTEGER NOT NULL CHECK (order_index >= 0),
        rows INTEGER NOT NULL CHECK (rows BETWEEN 1 AND 64),
        columns INTEGER NOT NULL CHECK (columns BETWEEN 1 AND 64),
        PRIMARY KEY (profile_id, id),
        UNIQUE (profile_id, order_index),
        FOREIGN KEY (profile_id)
            REFERENCES profiles(id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS buttons (
        profile_id TEXT NOT NULL,
        page_id TEXT NOT NULL,
        id TEXT NOT NULL,
        row_index INTEGER NOT NULL CHECK (row_index >= 0),
        column_index INTEGER NOT NULL CHECK (column_index >= 0),
        title TEXT NOT NULL,
        icon TEXT,
        color TEXT,
        PRIMARY KEY (profile_id, page_id, id),
        UNIQUE (profile_id, id),
        UNIQUE (profile_id, page_id, row_index, column_index),
        FOREIGN KEY (profile_id, page_id)
            REFERENCES pages(profile_id, id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actions (
        profile_id TEXT NOT NULL,
        page_id TEXT NOT NULL,
        button_id TEXT NOT NULL,
        action_type TEXT NOT NULL,
        payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
        PRIMARY KEY (profile_id, page_id, button_id),
        FOREIGN KEY (profile_id, page_id, button_id)
            REFERENCES buttons(profile_id, page_id, id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profile_revisions (
        profile_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 1),
        snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
        reason TEXT NOT NULL CHECK (length(reason) > 0),
        created_at TEXT NOT NULL,
        PRIMARY KEY (profile_id, revision),
        FOREIGN KEY (profile_id)
            REFERENCES profiles(id)
            ON DELETE CASCADE
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_single_active "
    "ON profiles(is_active) WHERE is_active = 1",
    "CREATE INDEX IF NOT EXISTS ix_profile_revisions_lookup "
    "ON profile_revisions(profile_id, revision)",
)


def _foreign_keys_enabled(connection: sqlite3.Connection) -> bool:
    return connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def _schema_is_complete(connection: sqlite3.Connection) -> bool:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    return _REQUIRED_TABLES.issubset(tables)


def migrate(connection: sqlite3.Connection) -> None:
    """Apply the ordered schema migrations in one transaction."""
    if connection.in_transaction:
        raise MigrationError("database migration requires an idle connection")

    if not _foreign_keys_enabled(connection):
        connection.execute("PRAGMA foreign_keys = ON")
    if not _foreign_keys_enabled(connection):
        raise MigrationError("database foreign-key enforcement is unavailable")

    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if current_version > LATEST_SCHEMA_VERSION:
        raise MigrationError("database schema version is newer than this server")
    if current_version == LATEST_SCHEMA_VERSION:
        if not _schema_is_complete(connection):
            raise MigrationError("database schema is incomplete")
        return

    try:
        connection.execute("BEGIN")
        if current_version < 1:
            for statement in _SCHEMA_V1:
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 1")
        connection.commit()
    except sqlite3.Error as exc:
        connection.rollback()
        raise MigrationError("database migration failed") from exc
