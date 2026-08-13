import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError
from referencing import Registry, Resource

from app.schemas import (
    HTTPS_URL_PATTERN,
    AckPayload,
    Button,
    ErrorPayload,
    HelloPayload,
    HotkeyAction,
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
PROFILE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "shared"
    / "protocol"
    / "v1-profile.schema.json"
)
MESSAGE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "shared"
    / "protocol"
    / "v1-message.schema.json"
)


def load_default_profile() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def load_invalid_messages() -> list[dict[str, object]]:
    fixture = json.loads(INVALID_MESSAGES_FIXTURE_PATH.read_text(encoding="utf-8"))
    return fixture["mensagens"]


def load_schema(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def local_schema_registry() -> Registry:
    profile_schema = load_schema(PROFILE_SCHEMA_PATH)
    message_schema = load_schema(MESSAGE_SCHEMA_PATH)
    return Registry().with_resources(
        [
            (
                profile_schema["$id"],
                Resource.from_contents(profile_schema),
            ),
            (
                message_schema["$id"],
                Resource.from_contents(message_schema),
            ),
        ]
    )


def profile_schema_validator() -> Draft202012Validator:
    schema = load_schema(PROFILE_SCHEMA_PATH)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
        registry=local_schema_registry(),
    )
    validator.check_schema(schema)
    return validator


def message_schema_validator() -> Draft202012Validator:
    schema = load_schema(MESSAGE_SCHEMA_PATH)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
        registry=local_schema_registry(),
    )
    validator.check_schema(schema)
    return validator


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


def test_system_info_action_is_accepted_by_runtime_and_shared_schema() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "system_info",
        "target": "cpu",
    }

    parsed = Profile.model_validate(profile)

    assert parsed.pages[0].buttons[0].action.type == "system_info"
    assert parsed.pages[0].buttons[0].action.target == "cpu"
    assert not list(profile_schema_validator().iter_errors(profile))


def test_system_info_gpu_target_is_accepted_by_runtime_and_shared_schema() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "system_info",
        "target": "gpu",
    }

    parsed = Profile.model_validate(profile)

    assert parsed.pages[0].buttons[0].action.type == "system_info"
    assert parsed.pages[0].buttons[0].action.target == "gpu"
    assert not list(profile_schema_validator().iter_errors(profile))


def test_system_info_action_rejects_unknown_target() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "system_info",
        "target": "disk",
    }

    with pytest.raises(ValidationError):
        Profile.model_validate(profile)
    assert list(profile_schema_validator().iter_errors(profile))


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


@pytest.mark.parametrize("control", ["\x01", "\x7f", "\x80", "\x9f"])
def test_url_action_rejects_c0_and_c1_control_characters(control: str) -> None:
    with pytest.raises(ValidationError):
        UrlAction(type="url", url=f"https://example.com{control}x")


@pytest.mark.parametrize(
    "url", ["https://user:pass@example.com", "https://example.com:443@evil.com"]
)
def test_url_action_rejects_userinfo(url: str) -> None:
    with pytest.raises(ValidationError):
        UrlAction(type="url", url=url)


@pytest.mark.parametrize(
    "host",
    ["a..b", "a-.com", "-a.com", "[1:2:3]", "[::1]"],
)
def test_url_action_rejects_v1_invalid_hosts(host: str) -> None:
    with pytest.raises(ValidationError):
        UrlAction(type="url", url=f"https://{host}")


@pytest.mark.parametrize(
    "host", ["localhost", "example.com", "sub-domain.example.com", "192.168.1.10"]
)
def test_url_action_accepts_v1_hosts(host: str) -> None:
    UrlAction(type="url", url=f"https://{host}")


def test_url_action_schema_matches_shared_contract() -> None:
    url_schema = UrlAction.model_json_schema()["properties"]["url"]
    shared_url_schema = load_schema(PROFILE_SCHEMA_PATH)["$defs"]["urlAction"][
        "properties"
    ]["url"]

    assert url_schema["format"] == "uri"
    assert url_schema["pattern"] == HTTPS_URL_PATTERN
    assert shared_url_schema["pattern"] == url_schema["pattern"]


@pytest.mark.parametrize("suffix", ["\n", "\r\n"])
def test_url_action_rejects_trailing_newlines_in_runtime_and_shared_schema(
    suffix: str,
) -> None:
    url = f"https://example.com{suffix}"

    with pytest.raises(ValidationError):
        UrlAction(type="url", url=url)

    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}
    assert list(profile_schema_validator().iter_errors(profile))


def test_generated_schema_declares_unique_items_for_unique_lists() -> None:
    hotkey_schema = HotkeyAction.model_json_schema()["properties"]["modifiers"]
    hello_schema = HelloPayload.model_json_schema()["properties"][
        "supported_protocol_versions"
    ]

    assert hotkey_schema["uniqueItems"] is True
    assert hello_schema["uniqueItems"] is True


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com\\evil",
        "https://example.com\x01x",
        "https://example.com\x80x",
        "https://user:pass@example.com",
        "https://example.com:443@evil.com",
        "https://example.com:",
        "https://example.com:bad",
        "https://example.com:0",
        "https://example.com:65536",
        "https://example.com:99999",
    ],
)
def test_shared_profile_schema_rejects_url_security_probes(url: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}

    assert list(profile_schema_validator().iter_errors(profile))


@pytest.mark.parametrize(
    "host",
    ["a..b", "a-.com", "-a.com", "[1:2:3]", "[::1]"],
)
def test_shared_profile_schema_rejects_v1_invalid_hosts(host: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "url",
        "url": f"https://{host}",
    }

    assert list(profile_schema_validator().iter_errors(profile))


@pytest.mark.parametrize(
    "host", ["localhost", "example.com", "sub-domain.example.com", "192.168.1.10"]
)
def test_shared_profile_schema_accepts_v1_hosts(host: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {
        "type": "url",
        "url": f"https://{host}",
    }

    assert not list(profile_schema_validator().iter_errors(profile))


def test_url_action_rejects_empty_port() -> None:
    with pytest.raises(ValidationError):
        UrlAction(type="url", url="https://example.com:")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:bad",
        "https://example.com:0",
        "https://example.com:65536",
        "https://example.com:99999",
    ],
)
def test_url_action_rejects_invalid_https_ports(url: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}

    with pytest.raises(ValidationError):
        Profile.model_validate(profile)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:01",
        "https://example.com:00080",
        "https://example.com:065535",
    ],
)
def test_url_action_rejects_noncanonical_https_ports_in_runtime_and_schema(
    url: str,
) -> None:
    with pytest.raises(ValidationError):
        UrlAction(type="url", url=url)

    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}
    assert list(profile_schema_validator().iter_errors(profile))


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "https://example.com:1",
        "https://example.com:80",
        "https://example.com:65535",
    ],
)
def test_url_action_accepts_valid_https_port_boundaries(url: str) -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0]["action"] = {"type": "url", "url": url}

    Profile.model_validate(profile)
    assert not list(profile_schema_validator().iter_errors(profile))


def test_url_action_enforces_dns_label_and_hostname_length_limits() -> None:
    valid_hostname = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 61])
    invalid_hostname = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 62])
    too_long_label = f"{'a' * 64}.com"

    for hostname in [valid_hostname]:
        UrlAction(type="url", url=f"https://{hostname}")
        profile = profile_with_single_button()
        profile["pages"][0]["buttons"][0]["action"] = {
            "type": "url",
            "url": f"https://{hostname}",
        }
        assert not list(profile_schema_validator().iter_errors(profile))

    for hostname in [invalid_hostname, too_long_label]:
        with pytest.raises(ValidationError):
            UrlAction(type="url", url=f"https://{hostname}")
        profile = profile_with_single_button()
        profile["pages"][0]["buttons"][0]["action"] = {
            "type": "url",
            "url": f"https://{hostname}",
        }
        assert list(profile_schema_validator().iter_errors(profile))


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


def test_profile_wire_omits_none_after_nested_model_copy_update() -> None:
    profile = Profile.model_validate(profile_with_single_button())
    button = profile.pages[0].buttons[0].model_copy(update={"color": None})
    page = profile.pages[0].model_copy(update={"buttons": [button]})
    profile = profile.model_copy(update={"pages": [page]})

    assert "color" in button.model_fields_set
    assert button.color is None

    with pytest.raises(ValidationError):
        profile.to_wire()
    with pytest.raises(ValidationError):
        profile.to_wire_json()


def test_direct_invalid_assignment_is_rejected_before_wire_serialization() -> None:
    profile = Profile.model_validate(profile_with_single_button())
    button = profile.pages[0].buttons[0]

    with pytest.raises(ValidationError):
        button.color = "not-a-color"


def test_wire_revalidation_rejects_model_copy_updated_shell_action() -> None:
    profile = Profile.model_validate(profile_with_single_button())
    button = (
        profile.pages[0]
        .buttons[0]
        .model_copy(update={"action": {"type": "shell", "command": "not-allowed"}})
    )
    page = profile.pages[0].model_copy(update={"buttons": [button]})
    profile = profile.model_copy(update={"pages": [page]})

    with pytest.raises(ValidationError):
        profile.to_wire()
    with pytest.raises(ValidationError):
        profile.to_wire_json()


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


def test_all_optional_fields_round_trip_through_explicit_wire_api() -> None:
    profile = profile_with_single_button()
    profile["pages"][0]["buttons"][0].update({"icon": "save", "color": "#12345678"})

    messages = [
        {
            "protocol_version": 1,
            "type": "hello",
            "payload": {
                "client_id": "android",
                "client_version": "1.0.0",
                "supported_protocol_versions": [1],
                "requested_profile_id": "default",
            },
        },
        {
            "protocol_version": 1,
            "type": "ack",
            "payload": {
                "request_id": "req-1",
                "status": "completed",
                "message": "Saved",
            },
        },
        {
            "protocol_version": 1,
            "type": "error",
            "payload": {
                "request_id": "req-1",
                "code": "TEMPORARY_FAILURE",
                "message": "Try again",
                "retryable": True,
            },
        },
        {
            "protocol_version": 1,
            "type": "profile_snapshot",
            "payload": {"profile": profile},
        },
        {
            "protocol_version": 1,
            "type": "profile_changed",
            "payload": {
                "profile_id": "default",
                "revision": 2,
                "reason": "updated",
            },
        },
    ]

    for message in messages:
        parsed = MessageAdapter.validate_python(message)
        wire = parsed.to_wire()
        wire_json = parsed.to_wire_json()

        assert wire == json.loads(wire_json)
        assert MessageAdapter.validate_python(wire) == parsed
        assert MessageAdapter.validate_json(wire_json) == parsed


@pytest.mark.parametrize(
    "fixture", load_invalid_messages(), ids=lambda fixture: str(fixture["id"])
)
def test_invalid_message_fixtures_are_rejected(fixture: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MessageAdapter.validate_python(fixture["message"])


def test_invalid_message_fixture_catalog_has_expected_count_and_ids() -> None:
    fixtures = load_invalid_messages()

    assert len(fixtures) == 6
    assert [fixture["id"] for fixture in fixtures] == [
        "unknown-type",
        "press-without-button-id",
        "unknown-action-type",
        "shell-at-envelope",
        "command-in-application",
        "arbitrary-media-command",
    ]


@pytest.mark.parametrize(
    "fixture", load_invalid_messages(), ids=lambda fixture: str(fixture["id"])
)
def test_invalid_message_fixtures_are_rejected_by_local_draft_2020_12_schema(
    fixture: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_network_is_used(*args: object, **kwargs: object) -> None:
        raise AssertionError("JSON Schema resolution must not use the network")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_network_is_used)

    errors = list(message_schema_validator().iter_errors(fixture["message"]))

    assert errors, fixture["id"]


def test_local_draft_2020_12_registry_validates_profile_reference_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_network_is_used(*args: object, **kwargs: object) -> None:
        raise AssertionError("JSON Schema resolution must not use the network")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_network_is_used)

    profile = load_default_profile()
    profile_errors = list(profile_schema_validator().iter_errors(profile))
    message = {
        "protocol_version": 1,
        "type": "profile_snapshot",
        "payload": {"profile": profile},
    }
    message_errors = list(message_schema_validator().iter_errors(message))

    assert not profile_errors
    assert not message_errors


def test_draft_2020_12_accepts_text_and_application_actions() -> None:
    profile = profile_with_single_button()
    page = profile["pages"][0]
    page["columns"] = 2
    page["buttons"] = [
        {
            "id": "text-button",
            "row": 0,
            "column": 0,
            "title": "Texto",
            "action": {"type": "text", "text": "Olá"},
        },
        {
            "id": "application-button",
            "row": 0,
            "column": 1,
            "title": "Aplicativo",
            "action": {"type": "application", "app_id": "calculator"},
        },
    ]

    assert not list(profile_schema_validator().iter_errors(profile))


@pytest.mark.parametrize(
    "message", wire_message_examples(), ids=lambda message: str(message["type"])
)
def test_all_wire_messages_are_accepted_by_local_draft_2020_12_schema(
    message: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_network_is_used(*args: object, **kwargs: object) -> None:
        raise AssertionError("JSON Schema resolution must not use the network")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_network_is_used)

    errors = list(message_schema_validator().iter_errors(message))

    assert not errors


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
