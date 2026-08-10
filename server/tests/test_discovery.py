from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import Any

import pytest

from app.config import Settings
from app.discovery import (
    DISCOVERY_PROPERTIES,
    DISCOVERY_SERVICE_TYPE,
    DiscoveryError,
    DiscoveryPublisher,
    _eligible_ipv4_addresses,
)


@dataclass
class FakeZeroconf:
    registrations: list[tuple[object, dict[str, object]]]
    unregistrations: list[object]
    close_calls: int = 0
    fail_register: bool = False

    def register_service(self, service_info: object, **kwargs: object) -> None:
        if self.fail_register:
            raise RuntimeError("contains-pairing-code-do-not-leak")
        self.registrations.append((service_info, kwargs))

    def unregister_service(self, service_info: object) -> None:
        self.unregistrations.append(service_info)

    def close(self) -> None:
        self.close_calls += 1


def discovery_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "host": "192.168.1.20",
        "pairing_code": "safe-test-code",
        "require_auth": True,
        "discovery_enabled": True,
        "discovery_name": "Desk Test",
    }
    values.update(overrides)
    return Settings(**values)


def test_discovery_is_disabled_by_default() -> None:
    assert Settings().discovery_enabled is False


@pytest.mark.parametrize("raw_value", ["1", "true", "yes", "on"])
def test_settings_reads_truthy_discovery_values(
    monkeypatch: pytest.MonkeyPatch, raw_value: str
) -> None:
    monkeypatch.setenv("STREAMDECK_HOST", "192.168.100.7")
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


def test_settings_requires_a_boolean_discovery_flag() -> None:
    with pytest.raises(ValueError, match="discovery_enabled"):
        Settings(discovery_enabled="true")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "localhost",
        "::1",
        "0.0.0.0",
        "192.0.2.10",
        "8.8.8.8",
        "streamdeck.local",
    ],
)
def test_discovery_requires_a_concrete_rfc1918_bind(host: str) -> None:
    with pytest.raises(
        ValueError, match="discovery requires a concrete private IPv4 bind"
    ):
        Settings(
            host=host,
            pairing_code="safe-test-code",
            require_auth=True,
            discovery_enabled=True,
        )


@pytest.mark.parametrize("invalid_name", ["", " Desk", "Desk ", "Desk\nTest", "x" * 64])
def test_discovery_name_is_strictly_validated(invalid_name: str) -> None:
    with pytest.raises(ValueError, match="discovery_name"):
        discovery_settings(discovery_name=invalid_name)


def test_remote_bind_still_requires_authentication() -> None:
    with pytest.raises(ValueError, match="remote bind requires authentication"):
        Settings(host="192.168.1.20")


@pytest.mark.parametrize("host", ["10.1.2.3", "172.16.0.1", "192.168.1.20"])
def test_discovery_accepts_authenticated_rfc1918_bind(host: str) -> None:
    settings = Settings(
        host=host,
        pairing_code="safe-test-code",
        require_auth=True,
        discovery_enabled=True,
    )

    assert settings.discovery_enabled is True


def test_address_filter_only_returns_unique_rfc1918_ipv4_addresses() -> None:
    assert _eligible_ipv4_addresses(
        [
            "192.168.1.20",
            "192.168.1.20",
            "10.0.0.2",
            "172.16.4.8",
            "127.0.0.1",
            "169.254.1.2",
            "192.0.2.10",
            "invalid",
        ]
    ) == ("192.168.1.20", "10.0.0.2", "172.16.4.8")


def test_publisher_registers_only_safe_metadata_and_stops_idempotently() -> None:
    client = FakeZeroconf([], [])
    captured: dict[str, Any] = {}

    def service_factory(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    publisher = DiscoveryPublisher(
        discovery_settings(),
        address_provider=lambda: ["127.0.0.1", "192.168.1.44", "192.0.2.10"],
        zeroconf_factory=lambda: client,
        service_info_factory=service_factory,
    )

    publisher.start()
    publisher.start()
    publisher.stop()
    publisher.stop()

    assert captured["type_"] == DISCOVERY_SERVICE_TYPE
    assert captured["port"] == 8765
    assert captured["addresses"] == [IPv4Address("192.168.1.44").packed]
    assert captured["properties"] == DISCOVERY_PROPERTIES
    assert captured["properties"][b"transport"] == b"https"
    assert captured["properties"][b"tls"] == b"required"
    assert b"fingerprint" not in captured["properties"]
    assert b"trust_code" not in captured["properties"]
    assert "safe-test-code" not in repr(captured)
    assert client.close_calls == 1
    assert len(client.registrations) == 1
    assert len(client.unregistrations) == 1


def test_publisher_rejects_missing_private_address_without_creating_client() -> None:
    created = False

    def factory() -> FakeZeroconf:
        nonlocal created
        created = True
        return FakeZeroconf([], [])

    publisher = DiscoveryPublisher(
        discovery_settings(),
        address_provider=lambda: ["127.0.0.1"],
        zeroconf_factory=factory,
    )

    with pytest.raises(DiscoveryError, match="no eligible IPv4 address"):
        publisher.start()

    assert created is False


def test_publisher_sanitizes_registration_failure_and_closes_client() -> None:
    client = FakeZeroconf([], [], fail_register=True)
    publisher = DiscoveryPublisher(
        discovery_settings(),
        address_provider=lambda: ["192.168.1.44"],
        zeroconf_factory=lambda: client,
        service_info_factory=lambda **_kwargs: object(),
    )

    with pytest.raises(
        DiscoveryError, match="local discovery could not start"
    ) as error:
        publisher.start()

    assert "safe-test-code" not in str(error.value)
    assert client.close_calls == 1
