from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.builtin_profiles import (
    BUILTIN_PROFILE_ID,
    install_builtin_profiles,
    load_essential_controls_profile,
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
            == 1
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
