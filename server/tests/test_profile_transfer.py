from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from app.profile_transfer import (
    ProfileTransferError,
    export_profile,
    export_profile_json,
    import_profile,
)
from app.schemas import Profile

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "shared" / "fixtures"
PROFILE_SCHEMA_PATH = REPO_ROOT / "shared" / "protocol" / "v1-profile.schema.json"


def read_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def profile_schema_validator() -> Draft202012Validator:
    schema = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.check_schema(schema)
    return validator


def test_valid_export_fixture_is_importable_against_draft_2020_12() -> None:
    payload = read_json("profile-export-v1.json")

    profile = import_profile(payload)

    assert isinstance(profile, Profile)
    assert profile.id == "phase5-export"
    assert not list(profile_schema_validator().iter_errors(profile.to_wire()))


def test_export_is_sanitized_and_deterministic() -> None:
    payload = read_json("profile-export-v1.json")
    profile = Profile.model_validate(payload)

    first = export_profile(profile)
    second = export_profile(copy.deepcopy(payload))

    assert first == second
    assert first == export_profile_json(profile)
    assert json.loads(first) == profile.to_wire()
    assert "null" not in first
    assert "shell" not in first
    exported = json.loads(first)
    assert all(
        "command" not in action or action["type"] == "media"
        for page in exported["pages"]
        for button in page["buttons"]
        for action in [button["action"]]
    )
    assert list(exported) == sorted(exported)


def test_import_export_round_trip_preserves_only_wire_content() -> None:
    payload = read_json("profile-export-v1.json")

    exported = export_profile(import_profile(payload))

    assert json.loads(exported) == payload
    assert import_profile(exported).to_wire() == payload


@pytest.mark.parametrize(
    "case_id",
    [
        "extra-field",
        "invalid-id",
        "invalid-page-order",
        "invalid-button-position",
        "invalid-revision",
        "shell-action",
        "command-outside-media",
    ],
)
def test_invalid_profile_import_fixtures_are_rejected(case_id: str) -> None:
    catalog = read_json("invalid-profile-imports-v1.json")
    case = next(item for item in catalog["cases"] if item["id"] == case_id)

    with pytest.raises((ProfileTransferError, ValidationError)):
        import_profile(case["profile"])


def test_invalid_profile_import_fixtures_are_rejected_by_local_draft_2020_12() -> None:
    catalog = read_json("invalid-profile-imports-v1.json")
    validator = profile_schema_validator()

    for case in catalog["cases"]:
        errors = list(validator.iter_errors(case["profile"]))
        if case["id"] == "invalid-button-position":
            # Grid bounds are a relational invariant enforced by Profile, not by
            # the shared JSON Schema's independent integer bounds.
            assert not errors
        else:
            assert errors, case["id"]


def test_import_rejects_a_revision_that_does_not_match_expected_revision() -> None:
    payload = read_json("profile-export-v1.json")

    with pytest.raises(ProfileTransferError, match="revision"):
        import_profile(payload, expected_revision=payload["revision"] + 1)


def test_import_rejects_duplicate_json_members() -> None:
    payload = '{"protocol_version":1,"id":"duplicate","id":"other"}'

    with pytest.raises(ProfileTransferError, match="duplicate"):
        import_profile(payload)


def test_import_rejects_non_json_and_non_object_payloads() -> None:
    with pytest.raises(ProfileTransferError):
        import_profile("not-json")
    with pytest.raises(ProfileTransferError):
        import_profile("[]")


def test_import_does_not_use_network_for_draft_2020_12_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_network_is_used(*args: object, **kwargs: object) -> None:
        raise AssertionError("profile validation must not use the network")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_network_is_used)

    profile = import_profile(read_json("profile-export-v1.json"))

    assert profile.revision == 4


def test_migration_fixture_is_versioned_and_legacy_case_is_rejected() -> None:
    migration = read_json("profile-migration-v0-to-v1.json")
    legacy = next(item for item in migration["cases"] if item["id"] == "legacy-v0")
    target = next(item for item in migration["cases"] if item["id"] == "target-v1")

    assert migration["fixture_version"] == 1
    assert migration["source_protocol_version"] == 0
    assert migration["target_protocol_version"] == 1
    with pytest.raises((ProfileTransferError, ValidationError)):
        import_profile(legacy["profile"])
    assert import_profile(target["profile"]).protocol_version == 1


def test_import_accepts_mapping_without_mutating_it() -> None:
    payload = read_json("profile-export-v1.json")
    original = copy.deepcopy(payload)

    profile = import_profile(payload)

    assert payload == original
    assert profile.to_wire() == original
