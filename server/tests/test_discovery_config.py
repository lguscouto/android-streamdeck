from __future__ import annotations

import pytest

from app.config import DEFAULT_DISCOVERY_NAME, Settings


def test_discovery_defaults_to_disabled_with_stable_name() -> None:
    settings = Settings()

    assert settings.discovery_enabled is False
    assert settings.discovery_name == DEFAULT_DISCOVERY_NAME


@pytest.mark.parametrize("raw_value", ["1", "true", "yes", "on"])
def test_settings_reads_truthy_discovery_values(
    monkeypatch: pytest.MonkeyPatch, raw_value: str
) -> None:
    monkeypatch.setenv("STREAMDECK_HOST", "192.168.1.20")
    monkeypatch.setenv("STREAMDECK_PAIRING_CODE", "safe-test-code")
    monkeypatch.setenv("STREAMDECK_DISCOVERY_ENABLED", raw_value)

    assert Settings.from_env().discovery_enabled is True


@pytest.mark.parametrize("raw_value", ["", "0", "false", "no", "off"])
def test_settings_reads_falsy_discovery_values(
    monkeypatch: pytest.MonkeyPatch, raw_value: str
) -> None:
    monkeypatch.setenv("STREAMDECK_DISCOVERY_ENABLED", raw_value)

    assert Settings.from_env().discovery_enabled is False


def test_settings_rejects_invalid_discovery_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STREAMDECK_DISCOVERY_ENABLED", "sometimes")

    with pytest.raises(ValueError, match="STREAMDECK_DISCOVERY_ENABLED"):
        Settings.from_env()


def test_settings_reads_discovery_name_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STREAMDECK_DISCOVERY_NAME", "Office StreamDeck 01")

    assert Settings.from_env().discovery_name == "Office StreamDeck 01"


@pytest.mark.parametrize(
    "name",
    [
        "",
        " leading-space",
        "trailing-space ",
        "not/a-service",
        "name\nwith-control",
        "x" * 64,
    ],
)
def test_settings_rejects_unsafe_discovery_name(name: str) -> None:
    with pytest.raises(ValueError, match="discovery_name"):
        Settings(discovery_name=name)


def test_settings_requires_a_boolean_discovery_flag() -> None:
    with pytest.raises(ValueError, match="discovery_enabled"):
        Settings(discovery_enabled="true")  # type: ignore[arg-type]


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_discovery_is_rejected_for_loopback_bind(host: str) -> None:
    with pytest.raises(ValueError, match="discovery requires"):
        Settings(
            host=host,
            pairing_code="safe-test-code",
            require_auth=True,
            discovery_enabled=True,
        )


@pytest.mark.parametrize("host", ["0.0.0.0", "8.8.8.8", "192.0.2.10", "server.local"])
def test_discovery_requires_a_concrete_rfc1918_bind(host: str) -> None:
    with pytest.raises(ValueError, match="discovery requires"):
        Settings(
            host=host,
            pairing_code="safe-test-code",
            require_auth=True,
            discovery_enabled=True,
        )


def test_authenticated_private_interface_bind_can_use_discovery() -> None:
    settings = Settings(
        host="192.168.1.20",
        pairing_code="safe-test-code",
        require_auth=True,
        discovery_enabled=True,
        discovery_name="Office StreamDeck",
    )

    assert settings.discovery_enabled is True


def test_remote_bind_still_requires_authentication() -> None:
    with pytest.raises(ValueError, match="remote bind requires authentication"):
        Settings(host="192.168.1.20")
