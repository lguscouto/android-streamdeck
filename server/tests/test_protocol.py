import copy
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import (
    AckPayload,
    Button,
    ErrorPayload,
    HelloPayload,
    MessageAdapter,
    Profile,
    ProfileChangedPayload,
    UrlAction,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)
INVALID_MESSAGES_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "shared"
    / "fixtures"
    / "invalid-messages.json"
)


def load_default_profile() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def load_invalid_messages() -> list[dict[str, object]]:
    fixture = json.loads(INVALID_MESSAGES_FIXTURE_PATH.read_text(encoding="utf-8"))
    return fixture["mensagens"]


def profile_with_single_button() -> dict[str, object]:
    profile = load_default_profile()
    profile["pages"] = [
        {
            "id": "main",
            "title": "Principal",
            "order": 0,
            "rows": 1,
            "columns": 1,
            "buttons": [
                {
                    "id": "button",
                    "row": 0,
                    "column": 0,
                    "title": "Botão",
                    "action": {"type": "key", "key": "A"},
                }
            ],
        }
    ]
    return profile


def test_default_profile_fixture_is_accepted() -> None:
    profile = Profile.model_validate(load_default_profile())

    assert profile.id == "default"
    assert profile.pages[0].buttons[0].action.type == "hotkey"


def test_unknown_action_type_is_rejected() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "shell",
        "command": "not-allowed",
    }

    with pytest.raises(ValidationError):
        Profile.model_validate(profile)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("shell", "not-allowed"),
        ("command", "not-allowed"),
    ],
)
def test_action_extras_are_rejected(field: str, value: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"][field] = value

    with pytest.raises(ValidationError):
        Profile.model_validate(profile)


def test_duplicate_button_position_is_rejected() -> None:
    profile = profile_with_single_button()
    duplicate = copy.deepcopy(profile["pages"][0]["buttons"][0])
    duplicate["id"] = "second-button"
    profile["pages"][0]["buttons"].append(duplicate)

    with pytest.raises(ValidationError, match="position"):
        Profile.model_validate(profile)


def test_button_outside_grid_is_rejected() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["row"] = 1

    with pytest.raises(ValidationError, match="row"):
        Profile.model_validate(profile)


def test_active_page_id_must_exist() -> None:
    profile = profile_with_single_button()
    profile["active_page_id"] = "missing"

    with pytest.raises(ValidationError, match="active_page_id"):
        Profile.model_validate(profile)


def test_duplicate_page_ids_are_rejected() -> None:
    profile = profile_with_single_button()
    duplicate_page = copy.deepcopy(profile["pages"][0])
    duplicate_page["order"] = 1
    profile["pages"].append(duplicate_page)

    with pytest.raises(ValidationError, match="page"):
        Profile.model_validate(profile)


def test_duplicate_page_orders_are_rejected() -> None:
    profile = profile_with_single_button()
    second_page = copy.deepcopy(profile["pages"][0])
    second_page["id"] = "second"
    profile["pages"].append(second_page)

    with pytest.raises(ValidationError, match="order"):
        Profile.model_validate(profile)


def test_duplicate_button_ids_are_rejected_across_profile() -> None:
    profile = profile_with_single_button()
    second_page = copy.deepcopy(profile["pages"][0])
    second_page["id"] = "second"
    second_page["order"] = 1
    profile["pages"].append(second_page)

    with pytest.raises(ValidationError, match="button"):
        Profile.model_validate(profile)


@pytest.mark.parametrize(
    "url", ["http://example.com", "ftp://example.com", "javascript:alert(1)"]
)
def test_url_action_requires_https(url: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}

    with pytest.raises(ValidationError, match="https"):
        Profile.model_validate(profile)


def test_url_action_rejects_backslashes() -> None:
    with pytest.raises(ValidationError):
        UrlAction(type="url", url=r"https://example.com\evil")


def test_url_action_schema_matches_shared_contract() -> None:
    url_schema = UrlAction.model_json_schema()["properties"]["url"]

    assert url_schema["format"] == "uri"
    assert url_schema["pattern"] == r"^https://[^\s\\]+$"


def test_url_action_accepts_empty_port_as_allowed_by_shared_contract() -> None:
    UrlAction(type="url", url="https://example.com:")


@pytest.mark.parametrize(
    "url", ["https://example.com:bad", "https://example.com:0", "https://example.com:99999"]
)
def test_url_action_rejects_invalid_https_ports(url: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}

    with pytest.raises(ValidationError):
        Profile.model_validate(profile)


@pytest.mark.parametrize("url", ["https://example.com:1", "https://example.com:65535"])
def test_url_action_accepts_valid_https_port_boundaries(url: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}

    Profile.model_validate(profile)


def test_duplicate_hotkey_modifiers_are_rejected() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "hotkey",
        "modifiers": ["ctrl", "ctrl"],
        "key": "A",
    }

    with pytest.raises(ValidationError, match="unique"):
        Profile.model_validate(profile)


@pytest.mark.parametrize(
    ("model", "data", "field"),
    [
        (
            Button,
            {
                "id": "button",
                "row": 0,
                "column": 0,
                "title": "Botão",
                "action": {"type": "key", "key": "A"},
            },
            "icon",
        ),
        (
            Button,
            {
                "id": "button",
                "row": 0,
                "column": 0,
                "title": "Botão",
                "action": {"type": "key", "key": "A"},
            },
            "color",
        ),
        (
            HelloPayload,
            {
                "client_id": "android",
                "client_version": "1.0.0",
                "supported_protocol_versions": [1],
            },
            "requested_profile_id",
        ),
        (
            AckPayload,
            {"request_id": "req-1", "status": "accepted"},
            "message",
        ),
        (
            ErrorPayload,
            {"code": "INVALID_REQUEST", "message": "Invalid request"},
            "request_id",
        ),
        (
            ErrorPayload,
            {"code": "INVALID_REQUEST", "message": "Invalid request"},
            "retryable",
        ),
        (
            ProfileChangedPayload,
            {"profile_id": "default", "revision": 2},
            "reason",
        ),
    ],
)
def test_explicit_null_is_rejected_for_non_nullable_optional_fields(
    model: type[BaseModel], data: dict[str, object], field: str
) -> None:
    data = copy.deepcopy(data)
    data[field] = None

    with pytest.raises(ValidationError):
        model.model_validate(data)


def _assert_wire_contains_no_nulls(value: object) -> None:
    if isinstance(value, dict):
        assert all(item is not None for item in value.values())
        for item in value.values():
            _assert_wire_contains_no_nulls(item)
    elif isinstance(value, list):
        for item in value:
            _assert_wire_contains_no_nulls(item)


def test_default_profile_round_trips_through_explicit_wire_api() -> None:
    profile = Profile.model_validate(load_default_profile())

    wire = profile.to_wire()
    wire_json = profile.to_wire_json()

    assert wire == json.loads(wire_json)
    assert Profile.model_validate(wire) == profile
    assert Profile.model_validate_json(wire_json) == profile


def test_profile_wire_omits_unset_optional_fields_instead_of_nulls() -> None:
    profile = Profile.model_validate(profile_with_single_button())
    button = profile.pages[0].buttons[0]

    wire = profile.to_wire()
    wire_button = wire["pages"][0]["buttons"][0]

    assert "icon" not in button.model_fields_set
    assert "color" not in button.model_fields_set
    assert "icon" not in wire_button
    assert "color" not in wire_button
    _assert_wire_contains_no_nulls(wire)
    assert Profile.model_validate_json(profile.to_wire_json()) == profile


def wire_message_examples() -> list[dict[str, object]]:
    profile = load_default_profile()
    return [
        {
            "protocol_version": 1,
            "type": "hello",
            "payload": {
                "client_id": "android",
                "client_version": "1.0.0",
                "supported_protocol_versions": [1],
            },
        },
        {
            "protocol_version": 1,
            "type": "welcome",
            "payload": {
                "server_id": "desktop",
                "server_version": "1.0.0",
                "profile_id": "default",
                "revision": 1,
            },
        },
        {
            "protocol_version": 1,
            "type": "press",
            "payload": {
                "request_id": "req-1",
                "profile_id": "default",
                "page_id": "main",
                "button_id": "save-shortcut",
                "revision": 1,
            },
        },
        {
            "protocol_version": 1,
            "type": "ack",
            "payload": {"request_id": "req-1", "status": "accepted"},
        },
        {
            "protocol_version": 1,
            "type": "error",
            "payload": {"code": "INVALID_REQUEST", "message": "Invalid request"},
        },
        {"protocol_version": 1, "type": "ping", "payload": {"nonce": "nonce-1"}},
        {"protocol_version": 1, "type": "pong", "payload": {"nonce": "nonce-1"}},
        {
            "protocol_version": 1,
            "type": "profile_snapshot",
            "payload": {"profile": profile},
        },
        {
            "protocol_version": 1,
            "type": "profile_changed",
            "payload": {"profile_id": "default", "revision": 2},
        },
    ]


@pytest.mark.parametrize(
    "message", wire_message_examples(), ids=lambda message: str(message["type"])
)
def test_messages_round_trip_through_explicit_wire_api_without_nulls(
    message: dict[str, object],
) -> None:
    parsed = MessageAdapter.validate_python(message)

    wire = parsed.to_wire()
    wire_json = parsed.to_wire_json()

    assert wire == json.loads(wire_json)
    _assert_wire_contains_no_nulls(wire)
    assert MessageAdapter.validate_python(wire) == parsed
    assert MessageAdapter.validate_json(wire_json) == parsed


@pytest.mark.parametrize(
    "fixture", load_invalid_messages(), ids=lambda fixture: str(fixture["id"])
)
def test_invalid_message_fixtures_are_rejected(fixture: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MessageAdapter.validate_python(fixture["message"])


def test_all_message_variants_are_accepted() -> None:
    profile = load_default_profile()
    messages = [
        {
            "protocol_version": 1,
            "type": "hello",
            "payload": {
                "client_id": "android",
                "client_version": "1.0.0",
                "supported_protocol_versions": [1],
            },
        },
        {
            "protocol_version": 1,
            "type": "welcome",
            "payload": {
                "server_id": "desktop",
                "server_version": "1.0.0",
                "profile_id": "default",
                "revision": 1,
            },
        },
        {
            "protocol_version": 1,
            "type": "press",
            "payload": {
                "request_id": "req-1",
                "profile_id": "default",
                "page_id": "main",
                "button_id": "save-shortcut",
                "revision": 1,
            },
        },
        {
            "protocol_version": 1,
            "type": "ack",
            "payload": {"request_id": "req-1", "status": "accepted"},
        },
        {
            "protocol_version": 1,
            "type": "error",
            "payload": {"code": "INVALID_REQUEST", "message": "Invalid request"},
        },
        {
            "protocol_version": 1,
            "type": "ping",
            "payload": {"nonce": "nonce-1"},
        },
        {
            "protocol_version": 1,
            "type": "pong",
            "payload": {"nonce": "nonce-1"},
        },
        {
            "protocol_version": 1,
            "type": "profile_snapshot",
            "payload": {"profile": profile},
        },
        {
            "protocol_version": 1,
            "type": "profile_changed",
            "payload": {"profile_id": "default", "revision": 2, "reason": "updated"},
        },
    ]

    parsed = [MessageAdapter.validate_python(message) for message in messages]

    assert [message.type for message in parsed] == [
        "hello",
        "welcome",
        "press",
        "ack",
        "error",
        "ping",
        "pong",
        "profile_snapshot",
        "profile_changed",
    ]


def test_press_requires_button_id() -> None:
    message = {
        "protocol_version": 1,
        "type": "press",
        "payload": {
            "request_id": "req-1",
            "profile_id": "default",
            "page_id": "main",
            "revision": 1,
        },
    }

    with pytest.raises(ValidationError):
        MessageAdapter.validate_python(message)


def test_message_envelope_extras_are_rejected() -> None:
    message = {
        "protocol_version": 1,
        "type": "press",
        "shell": "not-allowed",
        "payload": {
            "request_id": "req-1",
            "profile_id": "default",
            "page_id": "main",
            "button_id": "save-shortcut",
            "revision": 1,
        },
    }

    with pytest.raises(ValidationError):
        MessageAdapter.validate_python(message)
