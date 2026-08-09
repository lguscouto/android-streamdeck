from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db import Database
from app.migrations import LATEST_SCHEMA_VERSION, MigrationError, migrate
from app.repositories.profiles import (
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileRepository,
    ProfileRepositoryError,
)
from app.schemas import Profile

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def load_profile(*, profile_id: str = "default", revision: int = 1) -> Profile:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    payload["revision"] = revision
    return Profile.model_validate(payload)


def replace_button_title(profile: Profile, title: str, *, revision: int) -> Profile:
    payload = copy.deepcopy(profile.to_wire())
    payload["revision"] = revision
    payload["pages"][0]["buttons"][0]["title"] = title
    return Profile.model_validate(payload)


def test_fresh_database_bootstraps_latest_schema_and_is_idempotent(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")

    database.initialize()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == LATEST_SCHEMA_VERSION
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    database.migrate()
    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert tables == {
            "profiles",
            "pages",
            "buttons",
            "actions",
            "profile_revisions",
        }


def test_in_memory_database_stays_initialized_across_connections() -> None:
    database = Database(":memory:")
    repository = ProfileRepository(database)

    database.initialize()

    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == LATEST_SCHEMA_VERSION
        )
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert tables == {
        "profiles",
        "pages",
        "buttons",
        "actions",
        "profile_revisions",
    }

    profile = load_profile()
    assert repository.seed_profile(profile) == profile
    assert repository.get_profile("default") == profile


def test_seed_profile_requires_initial_revision_one(tmp_path: Path) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    repository.initialize()

    with pytest.raises(ProfileConflictError):
        repository.seed_profile(load_profile(revision=2))

    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0


def test_migration_rejects_version_one_without_required_tables(tmp_path: Path) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    with database.connect() as connection:
        connection.execute("PRAGMA user_version = 1")
        connection.commit()

    with database.connect() as connection:
        with pytest.raises(MigrationError, match="incomplete"):
            migrate(connection)


def test_database_initialize_closes_connection_after_migration_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TrackingConnection(sqlite3.Connection):
        closed = False

        def close(self) -> None:
            self.closed = True
            super().close()

    connection = sqlite3.connect(":memory:", factory=TrackingConnection)
    database = Database(tmp_path / "streamdeck.sqlite3")

    def fail_migration(_connection: sqlite3.Connection) -> None:
        raise MigrationError("synthetic migration failure")

    monkeypatch.setattr(database, "connect", lambda: connection)
    monkeypatch.setattr("app.db.migrate", fail_migration)

    with pytest.raises(MigrationError, match="synthetic"):
        database.initialize()

    assert connection.closed


def test_foreign_keys_and_layout_constraints_reject_orphans_and_duplicates(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    repository.initialize()
    repository.seed_profile(load_profile())

    with database.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO pages(profile_id, id, title, order_index, rows, columns)
                VALUES ('missing', 'orphan', 'Orphan', 0, 1, 1)
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO buttons(
                    profile_id, page_id, id, row_index, column_index, title, icon, color
                )
                VALUES (
                    'default', 'main', 'duplicate-position', 0, 0,
                    'Duplicate', NULL, NULL
                )
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO actions(
                    profile_id, page_id, button_id, action_type, payload_json
                )
                VALUES (
                    'default', 'main', 'missing-button', 'key',
                    '{"type":"key","key":"A"}'
                )
                """
            )


def test_seed_profile_is_idempotent_and_seeds_first_active_profile(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    profile = load_profile()
    repository.initialize()

    repository.seed_profile(profile)
    repository.seed_profile(profile)

    assert repository.get_profile("default") == profile
    assert repository.get_active_profile() == profile
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = 'default'"
            ).fetchone()[0]
            == 1
        )


def test_historical_revision_returns_exact_wire_snapshot(tmp_path: Path) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    first = load_profile()
    second = replace_button_title(first, "Atualizado", revision=2)
    repository.initialize()

    repository.seed_profile(first)
    repository.save_profile(second, expected_revision=1, reason="updated")

    assert repository.get_profile("default", revision=1) == first
    assert repository.get_profile("default", revision=2) == second
    assert repository.get_profile("default") == second

    with database.connect() as connection:
        snapshots = [
            json.loads(row[0])
            for row in connection.execute(
                """
                SELECT snapshot_json
                FROM profile_revisions
                WHERE profile_id = 'default'
                ORDER BY revision
                """
            )
        ]
    assert snapshots == [first.to_wire(), second.to_wire()]
    for snapshot in snapshots:
        assert Profile.model_validate(snapshot).to_wire() == snapshot


def test_save_profile_requires_expected_and_monotonic_revision(tmp_path: Path) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    first = load_profile()
    second = replace_button_title(first, "Atualizado", revision=2)
    third = replace_button_title(first, "Terceira", revision=3)
    repository.initialize()

    repository.seed_profile(first)

    with pytest.raises(ProfileConflictError):
        repository.save_profile(second, expected_revision=99)
    with pytest.raises(ProfileConflictError):
        repository.save_profile(third, expected_revision=1)

    assert repository.get_profile("default") == first
    with database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = 'default'"
            ).fetchone()[0]
            == 1
        )


def test_save_profile_rolls_back_all_rows_when_a_child_write_fails(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    first = load_profile()
    broken = replace_button_title(first, "explode", revision=2)
    repository.initialize()
    repository.seed_profile(first)

    with database.connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_exploding_button
            BEFORE INSERT ON buttons
            WHEN NEW.title = 'explode'
            BEGIN
                SELECT RAISE(ABORT, 'synthetic child write failure');
            END
            """
        )
        connection.commit()

    with pytest.raises(ProfileRepositoryError) as error:
        repository.save_profile(broken, expected_revision=1)

    assert "synthetic child write failure" not in str(error.value)
    assert repository.get_profile("default") == first
    with database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = 'default'"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT title FROM buttons "
                "WHERE profile_id = 'default' AND id = 'save-shortcut'"
            ).fetchone()[0]
            == "Atalho Ctrl+Shift+S"
        )


def test_active_profile_can_be_switched_and_missing_profiles_are_rejected(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    first = load_profile(profile_id="first")
    second = load_profile(profile_id="second")
    repository.initialize()
    repository.seed_profile(first)
    repository.seed_profile(second)

    repository.set_active_profile("second")

    assert repository.get_active_profile() == second
    with database.connect() as connection:
        active_count = connection.execute(
            "SELECT COUNT(*) FROM profiles WHERE is_active = 1"
        ).fetchone()[0]
        first_active = connection.execute(
            "SELECT is_active FROM profiles WHERE id = 'first'"
        ).fetchone()[0]
    assert active_count == 1
    assert first_active == 0

    with pytest.raises(ProfileNotFoundError):
        repository.set_active_profile("missing")


def test_database_path_is_configurable_without_logging_or_persisting_runtime_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured_path = tmp_path / "configured" / "streamdeck.sqlite3"
    monkeypatch.setenv("STREAMDECK_DATABASE_PATH", str(configured_path))

    database = Database()
    assert database.path == configured_path
    database.initialize()
    assert configured_path.is_file()


def test_invalid_profile_is_rejected_before_persistence(tmp_path: Path) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    repository = ProfileRepository(database)
    repository.initialize()
    invalid = {"protocol_version": 1, "id": "bad", "revision": 1}

    with pytest.raises(ValidationError):
        repository.seed_profile(invalid)  # type: ignore[arg-type]

    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
