from __future__ import annotations

import sqlite3
from pathlib import Path

from app.migrations import _SCHEMA_V1, _SCHEMA_V2, LATEST_SCHEMA_VERSION, migrate


def _create_v2_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    for statement in (*_SCHEMA_V1, *_SCHEMA_V2):
        connection.execute(statement)
    connection.execute("PRAGMA user_version = 2")
    connection.execute(
        """
        INSERT INTO paired_clients(
            client_id, client_version, token_hash, paired_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "android-legacy-1",
            "0.1.0",
            "a" * 64,
            "2026-08-10T06:00:00+00:00",
            "2026-08-10T06:30:00+00:00",
        ),
    )
    connection.commit()
    return connection


def test_migration_v2_to_v3_preserves_pairing_without_secret_audit(
    tmp_path: Path,
) -> None:
    connection = _create_v2_database(tmp_path / "streamdeck.sqlite3")
    try:
        migrate(connection)
        migrated = connection.execute(
            """
            SELECT
                client_id, client_version, platform, device_label, token_hash,
                credential_generation, paired_at, last_seen_at,
                revoked_at, revoked_reason
            FROM paired_clients
            """
        ).fetchone()
        audit = connection.execute(
            """
            SELECT client_id, event_type, credential_generation, actor_kind,
                   reason_code, occurred_at
            FROM paired_client_audit
            """
        ).fetchone()
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(paired_client_audit)")
        }

        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == LATEST_SCHEMA_VERSION
        )
        assert tuple(migrated) == (
            "android-legacy-1",
            "0.1.0",
            "android",
            None,
            "a" * 64,
            1,
            "2026-08-10T06:00:00+00:00",
            "2026-08-10T06:30:00+00:00",
            None,
            None,
        )
        assert tuple(audit) == (
            "android-legacy-1",
            "legacy_imported",
            1,
            "legacy",
            None,
            "2026-08-10T06:00:00+00:00",
        )
        assert "token" not in columns
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

        migrate(connection)
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == LATEST_SCHEMA_VERSION
        )
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM paired_client_audit"
        ).fetchone()[0]
        assert audit_count == 1
    finally:
        connection.close()
