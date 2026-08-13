from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.builtin_profiles import (
    BUILTIN_PROFILE_ID,
    BUILTIN_PROFILE_VERSION,
    install_builtin_profiles,
    load_essential_controls_profile,
    load_essential_controls_profile_v1,
    load_essential_controls_profile_v2,
)
from app.config import Settings
from app.db import Database
from app.main import create_app
from app.repositories.profiles import ProfileNotFoundError, ProfileRepository
from app.schemas import Profile

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def make_repository(tmp_path: Path) -> ProfileRepository:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    return repository


def custom_profile(profile_id: str = "custom") -> Profile:
    payload = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    payload["name"] = "Meu painel"
    return Profile.model_validate(payload)


def test_builtin_fixture_v2_expands_essential_controls_without_changing_v1() -> None:
    previous = load_essential_controls_profile_v1()
    current = load_essential_controls_profile()

    assert BUILTIN_PROFILE_VERSION == 3
    assert (previous.pages[0].rows, previous.pages[0].columns) == (3, 3)
    assert [button.id for button in previous.pages[0].buttons] == [
        "media-play-pause",
        "media-next",
        "media-mute",
        "spotify-play-pause",
        "open-chrome",
        "volume-up",
        "volume-down",
        "print-screen",
    ]
    assert (current.pages[0].rows, current.pages[0].columns) == (3, 4)
    assert current.pages[0].buttons[-2].action.to_wire() == {
        "type": "system_info",
        "target": "cpu",
    }
    assert current.pages[0].buttons[-1].action.to_wire() == {
        "type": "system_info",
        "target": "memory",
    }


def test_builtin_fixture_v3_adds_gpu_without_changing_v2() -> None:
    previous = load_essential_controls_profile_v2()
    current = load_essential_controls_profile()

    assert BUILTIN_PROFILE_VERSION == 3
    assert [button.id for button in previous.pages[0].buttons[-2:]] == [
        "system-cpu",
        "system-memory",
    ]
    gpu = next(
        button for button in current.pages[0].buttons if button.id == "system-gpu"
    )
    assert gpu.row == 1
    assert gpu.column == 3
    assert gpu.action.to_wire() == {
        "type": "system_info",
        "target": "gpu",
    }


def test_builtin_v2_revision_two_upgrades_to_v3(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    previous = repository.seed_profile(load_essential_controls_profile_v2())
    repository.save_profile(
        previous.model_copy(update={"revision": 2}),
        expected_revision=1,
    )
    with repository.database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO builtin_profile_installations(builtin_id, version, installed_at)
            VALUES (?, ?, ?)
            """,
            (BUILTIN_PROFILE_ID, 2, "2026-08-13T00:00:00+00:00"),
        )

    upgraded = install_builtin_profiles(repository)

    assert upgraded is not None
    assert upgraded.revision == 3
    assert any(button.id == "system-gpu" for button in upgraded.pages[0].buttons)


def test_builtin_v1_installation_upgrades_unchanged_profile_once(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    previous = load_essential_controls_profile_v1()
    repository.seed_profile(previous)
    with repository.database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO builtin_profile_installations(builtin_id, version, installed_at)
            VALUES (?, ?, ?)
            """,
            (BUILTIN_PROFILE_ID, 1, "2026-08-12T00:00:00+00:00"),
        )

    upgraded = install_builtin_profiles(repository)
    repeated = install_builtin_profiles(repository)

    assert upgraded is not None
    assert upgraded.revision == 2
    assert (upgraded.pages[0].rows, upgraded.pages[0].columns) == (3, 4)
    assert [button.id for button in upgraded.pages[0].buttons[-2:]] == [
        "system-cpu",
        "system-memory",
    ]
    assert repeated == upgraded
    assert repository.get_profile(BUILTIN_PROFILE_ID, revision=1) == previous
    assert repository.get_profile(BUILTIN_PROFILE_ID) == upgraded
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT version FROM builtin_profile_installations "
                "WHERE builtin_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == BUILTIN_PROFILE_VERSION
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 2
        )


def test_builtin_v1_upgrade_rolls_back_profile_and_marker_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = make_repository(tmp_path)
    previous = load_essential_controls_profile_v1()
    repository.seed_profile(previous)
    with repository.database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO builtin_profile_installations(builtin_id, version, installed_at)
            VALUES (?, ?, ?)
            """,
            (BUILTIN_PROFILE_ID, 1, "2026-08-12T00:00:00+00:00"),
        )

    import app.builtin_profiles as builtin_profiles

    def fail_replace(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic upgrade failure")

    monkeypatch.setattr(builtin_profiles, "_replace_profile", fail_replace)

    with pytest.raises(RuntimeError, match="synthetic upgrade failure"):
        install_builtin_profiles(repository)

    assert repository.get_profile(BUILTIN_PROFILE_ID) == previous
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT version FROM builtin_profile_installations "
                "WHERE builtin_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 1
        )


def test_builtin_v1_installation_preserves_user_edited_profile(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    edited_payload = load_essential_controls_profile_v1().to_wire()
    edited_payload["name"] = "Meu painel essencial"
    edited = Profile.model_validate(edited_payload)
    repository.seed_profile(edited)
    with repository.database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO builtin_profile_installations(builtin_id, version, installed_at)
            VALUES (?, ?, ?)
            """,
            (BUILTIN_PROFILE_ID, 1, "2026-08-12T00:00:00+00:00"),
        )

    result = install_builtin_profiles(repository)

    assert result == edited
    assert repository.get_profile(BUILTIN_PROFILE_ID) == edited
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT version FROM builtin_profile_installations "
                "WHERE builtin_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == BUILTIN_PROFILE_VERSION
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 1
        )


def test_fresh_database_installs_essential_profile_as_active_once(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)

    installed = install_builtin_profiles(repository)
    repeated = install_builtin_profiles(repository)

    assert installed is not None
    assert installed.id == BUILTIN_PROFILE_ID
    assert installed.name == "Controles essenciais"
    assert repeated == installed
    assert repository.get_active_profile() == installed
    with repository.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profile_revisions WHERE profile_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT version FROM builtin_profile_installations "
                "WHERE builtin_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == BUILTIN_PROFILE_VERSION
        )


def test_existing_active_custom_profile_is_preserved_and_builtin_is_inactive(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    custom = custom_profile()
    repository.seed_profile(custom)

    installed = install_builtin_profiles(repository)

    assert installed is not None
    assert repository.get_active_profile() == custom
    assert repository.get_profile(BUILTIN_PROFILE_ID) == installed
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT is_active FROM profiles WHERE id = ?", (BUILTIN_PROFILE_ID,)
            ).fetchone()[0]
            == 0
        )


def test_existing_profile_id_is_never_overwritten_and_install_is_marked(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    collision_payload = load_essential_controls_profile().to_wire()
    collision_payload["name"] = "Painel personalizado"
    collision = Profile.model_validate(collision_payload)
    repository.seed_profile(collision)

    result = install_builtin_profiles(repository)

    assert result is None
    assert repository.get_profile(BUILTIN_PROFILE_ID) == collision
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM builtin_profile_installations "
                "WHERE builtin_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 1
        )


def test_removed_builtin_is_not_recreated_after_one_shot_marker(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    repository.seed_profile(custom_profile())
    install_builtin_profiles(repository)
    repository.set_active_profile("custom")
    repository.delete_profile(
        BUILTIN_PROFILE_ID,
        expected_revision=1,
        replacement_profile_id="custom",
    )

    assert install_builtin_profiles(repository) is None
    with pytest.raises(ProfileNotFoundError):
        repository.get_profile(BUILTIN_PROFILE_ID)
    with repository.database.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM builtin_profile_installations "
                "WHERE builtin_id = ?",
                (BUILTIN_PROFILE_ID,),
            ).fetchone()[0]
            == 1
        )


def test_builtin_installation_rolls_back_profile_and_marker_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = make_repository(tmp_path)
    import app.builtin_profiles as builtin_profiles

    def fail_insert(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic insert failure")

    monkeypatch.setattr(builtin_profiles, "_insert_profile", fail_insert)

    with pytest.raises(RuntimeError, match="synthetic insert failure"):
        install_builtin_profiles(repository)

    with repository.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM builtin_profile_installations"
            ).fetchone()[0]
            == 0
        )


def test_create_app_installs_essential_profile_in_a_new_database(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))

    active = app.state.profile_repository.get_active_profile()

    assert active is not None
    assert active.id == BUILTIN_PROFILE_ID
    assert active.name == "Controles essenciais"
