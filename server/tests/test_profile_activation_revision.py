from __future__ import annotations

import json
from pathlib import Path

from app.db import Database
from app.repositories.profiles import ProfileRepository
from app.schemas import Profile

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def _profile(profile_id: str) -> Profile:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    return Profile.model_validate(payload)


def test_activation_commits_next_revision_and_audits_selection_change(
    tmp_path: Path,
) -> None:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    repository.create_profile(_profile("default"))
    repository.duplicate_profile("default", "work", expected_revision=1)

    activated = repository.activate_profile("work", expected_revision=1)

    assert activated.id == "work"
    assert activated.revision == 2
    assert repository.get_active_profile() == activated
    assert [entry["revision"] for entry in repository.list_audit("work")] == [1, 2]
    assert [entry["reason"] for entry in repository.list_audit("work")] == [
        "created",
        "activated",
    ]
