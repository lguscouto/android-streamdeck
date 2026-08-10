from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db import Database
from app.repositories.profiles import (
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileRepository,
)
from app.schemas import Page, Profile

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def load_profile(*, profile_id: str = "default", revision: int = 1) -> Profile:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    payload["revision"] = revision
    return Profile.model_validate(payload)


def make_repository(tmp_path: Path) -> ProfileRepository:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    return repository


def page(*, page_id: str = "secondary", order: int = 1) -> Page:
    return Page.model_validate(
        {
            "id": page_id,
            "title": "Secundária",
            "order": order,
            "rows": 1,
            "columns": 1,
            "buttons": [
                {
                    "id": f"{page_id}-button",
                    "row": 0,
                    "column": 0,
                    "title": "Ação",
                    "action": {"type": "key", "key": "A"},
                }
            ],
        }
    )


def test_profile_crud_uses_explicit_revision_and_protects_last_profile(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    first = load_profile()
    repository.create_profile(first)

    renamed = repository.rename_profile("default", "Renomeado", expected_revision=1)
    assert renamed.name == "Renomeado"
    assert renamed.revision == 2

    duplicate = repository.duplicate_profile(
        "default", "copy", expected_revision=2, name="Cópia"
    )
    assert duplicate.id == "copy"
    assert duplicate.name == "Cópia"
    assert duplicate.revision == 1
    assert repository.get_active_profile() == renamed

    activated = repository.activate_profile("copy", expected_revision=1)
    assert activated.revision == 2
    assert repository.get_active_profile() == activated

    with pytest.raises(ProfileConflictError):
        repository.rename_profile("copy", "Stale", expected_revision=0)

    with pytest.raises(ProfileConflictError):
        repository.delete_profile("copy", expected_revision=1)
    assert repository.get_profile("copy").name == "Cópia"

    deleted = repository.delete_profile(
        "copy", expected_revision=2, replacement_profile_id="default"
    )
    assert deleted == "copy"
    replacement = repository.get_active_profile()
    assert replacement is not None
    assert replacement.id == "default"
    assert replacement.revision == 3
    assert replacement.name == renamed.name
    with pytest.raises(ProfileNotFoundError):
        repository.get_profile("copy")


def test_profile_duplicate_rejects_source_conflict_and_id_collision(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    repository.create_profile(load_profile())

    with pytest.raises(ProfileConflictError):
        repository.duplicate_profile("default", "copy", expected_revision=99)

    repository.duplicate_profile("default", "copy", expected_revision=1)
    with pytest.raises(ProfileConflictError):
        repository.duplicate_profile("default", "copy", expected_revision=1)


def test_page_crud_revisions_orders_and_active_page_protection(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_profile(load_profile())

    created = repository.create_page("default", page(), expected_revision=1)
    assert created.revision == 2
    assert [item.id for item in created.pages] == ["main", "secondary"]

    renamed = repository.rename_page(
        "default", "secondary", "Secundária renomeada", expected_revision=2
    )
    assert renamed.revision == 3
    assert renamed.pages[1].title == "Secundária renomeada"

    reordered = repository.reorder_page("default", "secondary", 0, expected_revision=3)
    assert reordered.revision == 4
    assert [(item.id, item.order) for item in reordered.pages] == [
        ("secondary", 0),
        ("main", 1),
    ]

    with pytest.raises(ProfileConflictError):
        repository.delete_page("default", "secondary", expected_revision=3)

    with pytest.raises(ProfileConflictError):
        repository.delete_page("default", "main", expected_revision=4)

    deleted = repository.delete_page(
        "default", "main", expected_revision=4, replacement_page_id="secondary"
    )
    assert deleted.revision == 5
    assert deleted.active_page_id == "secondary"
    assert [item.id for item in deleted.pages] == ["secondary"]


def test_page_operations_reject_duplicate_ids_orders_and_positions(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    repository.create_profile(load_profile())

    with pytest.raises(ValidationError):
        repository.create_page("default", page(page_id="main"), expected_revision=1)

    invalid = copy.deepcopy(load_profile().to_wire())
    invalid["pages"][0]["buttons"].append(
        {
            "id": "another",
            "row": 0,
            "column": 0,
            "title": "Posição repetida",
            "action": {"type": "key", "key": "B"},
        }
    )
    with pytest.raises(ValidationError):
        repository.save_profile(Profile.model_validate(invalid), expected_revision=1)

    with pytest.raises(ProfileConflictError):
        repository.reorder_page("default", "main", 1, expected_revision=99)

    with pytest.raises(ProfileNotFoundError):
        repository.rename_page("default", "missing", "x", expected_revision=1)
