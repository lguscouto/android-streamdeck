from __future__ import annotations

import sqlite3

LATEST_SCHEMA_VERSION = 5
_REQUIRED_TABLES = frozenset(
    {
        "profiles",
        "pages",
        "buttons",
        "actions",
        "profile_revisions",
        "paired_clients",
        "paired_client_audit",
        "builtin_profile_installations",
    }
)
_REQUIRED_TABLES_V1 = _REQUIRED_TABLES - {
    "paired_clients",
    "paired_client_audit",
    "builtin_profile_installations",
}
_REQUIRED_TABLES_V2 = _REQUIRED_TABLES - {
    "paired_client_audit",
    "builtin_profile_installations",
}
_REQUIRED_COLUMNS_V2 = {
    "paired_clients": frozenset(
        {"client_id", "client_version", "token_hash", "paired_at", "last_seen_at"}
    )
}
_REQUIRED_COLUMNS_V3 = {
    "paired_clients": frozenset(
        {
            "client_id",
            "client_version",
            "platform",
            "device_label",
            "token_hash",
            "credential_generation",
            "paired_at",
            "last_seen_at",
            "revoked_at",
            "revoked_reason",
        }
    ),
    "paired_client_audit": frozenset(
        {
            "event_id",
            "client_id",
            "event_type",
            "credential_generation",
            "actor_kind",
            "reason_code",
            "occurred_at",
        }
    ),
}
_REQUIRED_COLUMNS_V5 = {
    **_REQUIRED_COLUMNS_V3,
    "builtin_profile_installations": frozenset(
        {"builtin_id", "version", "installed_at"}
    ),
}


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


_SCHEMA_V2 = (
    """
    CREATE TABLE IF NOT EXISTS paired_clients (
        client_id TEXT PRIMARY KEY,
        client_version TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        paired_at TEXT NOT NULL,
        last_seen_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_paired_clients_token_hash "
    "ON paired_clients(token_hash)",
)

_SCHEMA_V3_PAIRED_CLIENTS = """
CREATE TABLE paired_clients_v3 (
    client_id TEXT PRIMARY KEY,
    client_version TEXT NOT NULL CHECK (length(client_version) BETWEEN 1 AND 64),
    platform TEXT NOT NULL CHECK (platform = 'android'),
    device_label TEXT CHECK (
        device_label IS NULL OR length(device_label) BETWEEN 1 AND 64
    ),
    token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) = 64),
    credential_generation INTEGER NOT NULL CHECK (credential_generation >= 1),
    paired_at TEXT NOT NULL,
    last_seen_at TEXT,
    revoked_at TEXT,
    revoked_reason TEXT CHECK (
        revoked_reason IS NULL OR revoked_reason IN (
            'user_request', 'lost_device', 'security', 'replaced'
        )
    ),
    CHECK (
        (revoked_at IS NULL AND revoked_reason IS NULL)
        OR (revoked_at IS NOT NULL AND revoked_reason IS NOT NULL)
    )
)
"""

_SCHEMA_V3_PAIRED_CLIENT_AUDIT = """
CREATE TABLE paired_client_audit (
    event_id INTEGER PRIMARY KEY,
    client_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('paired', 'repaired', 'revoked', 'legacy_imported')
    ),
    credential_generation INTEGER NOT NULL CHECK (credential_generation >= 1),
    actor_kind TEXT NOT NULL CHECK (
        actor_kind IN ('pairing_code', 'local_owner', 'self', 'legacy')
    ),
    reason_code TEXT CHECK (
        reason_code IS NULL OR reason_code IN (
            'user_request', 'lost_device', 'security', 'replaced'
        )
    ),
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES paired_clients(client_id)
)
"""

_SCHEMA_V3_INDEXES = (
    "CREATE INDEX ix_paired_clients_status_last_seen "
    "ON paired_clients(revoked_at, last_seen_at DESC, client_id)",
    "CREATE INDEX ix_paired_client_audit_lookup "
    "ON paired_client_audit(client_id, occurred_at DESC, event_id DESC)",
)

_SCHEMA_V4_PAIRED_CLIENT_AUDIT = """
CREATE TABLE paired_client_audit_v4 (
    event_id INTEGER PRIMARY KEY,
    client_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('paired', 'repaired', 'revoked', 'legacy_imported')
    ),
    credential_generation INTEGER NOT NULL CHECK (credential_generation >= 1),
    actor_kind TEXT NOT NULL CHECK (
        actor_kind IN (
            'pairing_code', 'pairing_session', 'local_owner', 'self', 'legacy'
        )
    ),
    reason_code TEXT CHECK (
        reason_code IS NULL OR reason_code IN (
            'user_request', 'lost_device', 'security', 'replaced'
        )
    ),
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES paired_clients(client_id)
)
"""

_SCHEMA_V5 = (
    """
    CREATE TABLE IF NOT EXISTS builtin_profile_installations (
        builtin_id TEXT PRIMARY KEY CHECK (length(builtin_id) BETWEEN 1 AND 64),
        version INTEGER NOT NULL CHECK (version >= 1),
        installed_at TEXT NOT NULL
    )
    """,
)


def _migrate_v4(connection: sqlite3.Connection) -> None:
    connection.execute("DROP INDEX IF EXISTS ix_paired_client_audit_lookup")
    connection.execute(_SCHEMA_V4_PAIRED_CLIENT_AUDIT)
    connection.execute(
        """
        INSERT INTO paired_client_audit_v4(
            event_id, client_id, event_type, credential_generation, actor_kind,
            reason_code, occurred_at
        )
        SELECT
            event_id, client_id, event_type, credential_generation, actor_kind,
            reason_code, occurred_at
        FROM paired_client_audit
        """
    )
    connection.execute("DROP TABLE paired_client_audit")
    connection.execute(
        "ALTER TABLE paired_client_audit_v4 RENAME TO paired_client_audit"
    )
    connection.execute(
        "CREATE INDEX ix_paired_client_audit_lookup "
        "ON paired_client_audit(client_id, occurred_at DESC, event_id DESC)"
    )


def _foreign_keys_enabled(connection: sqlite3.Connection) -> bool:
    return connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def _schema_is_complete(
    connection: sqlite3.Connection,
    required_tables: frozenset[str] = _REQUIRED_TABLES,
    required_columns: dict[str, frozenset[str]] | None = None,
) -> bool:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if not required_tables.issubset(tables):
        return False
    if required_columns is None:
        return True
    return all(
        columns.issubset(
            {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table_name})")
            }
        )
        for table_name, columns in required_columns.items()
    )


def _migrate_v3(connection: sqlite3.Connection) -> None:
    connection.execute(_SCHEMA_V3_PAIRED_CLIENTS)
    connection.execute(
        """
        INSERT INTO paired_clients_v3(
            client_id, client_version, platform, device_label, token_hash,
            credential_generation, paired_at, last_seen_at, revoked_at, revoked_reason
        )
        SELECT
            client_id, client_version, 'android', NULL, token_hash,
            1, paired_at, last_seen_at, NULL, NULL
        FROM paired_clients
        """
    )
    connection.execute("DROP TABLE paired_clients")
    connection.execute("ALTER TABLE paired_clients_v3 RENAME TO paired_clients")
    connection.execute(_SCHEMA_V3_PAIRED_CLIENT_AUDIT)
    connection.execute(
        """
        INSERT INTO paired_client_audit(
            client_id, event_type, credential_generation, actor_kind,
            reason_code, occurred_at
        )
        SELECT client_id, 'legacy_imported', 1, 'legacy', NULL, paired_at
        FROM paired_clients
        """
    )
    for statement in _SCHEMA_V3_INDEXES:
        connection.execute(statement)


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
    if current_version >= 1 and not _schema_is_complete(
        connection, _REQUIRED_TABLES_V1
    ):
        raise MigrationError("database schema is incomplete")
    if current_version >= 2 and not _schema_is_complete(
        connection, _REQUIRED_TABLES_V2, _REQUIRED_COLUMNS_V2
    ):
        raise MigrationError("database schema is incomplete")
    if current_version == LATEST_SCHEMA_VERSION:
        if not _schema_is_complete(connection, _REQUIRED_TABLES, _REQUIRED_COLUMNS_V5):
            raise MigrationError("database schema is incomplete")
        return

    try:
        connection.execute("BEGIN")
        if current_version < 1:
            for statement in _SCHEMA_V1:
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 1")
        if current_version < 2:
            for statement in _SCHEMA_V2:
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 2")
        if current_version < 3:
            _migrate_v3(connection)
            connection.execute("PRAGMA user_version = 3")
        if current_version < 4:
            _migrate_v4(connection)
            connection.execute("PRAGMA user_version = 4")
        if current_version < 5:
            for statement in _SCHEMA_V5:
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 5")
        connection.commit()
    except sqlite3.Error as exc:
        connection.rollback()
        raise MigrationError("database migration failed") from exc
