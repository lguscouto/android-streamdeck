from __future__ import annotations

import pytest

from app.config import Settings
from app.discovery import DISCOVERY_SERVICE_TYPE, DiscoveryError, DiscoveryPublisher


class FakeZeroconf:
    def __init__(self, *, register_error: Exception | None = None) -> None:
        self.register_error = register_error
        self.registered: list[tuple[object, dict[str, object]]] = []
        self.unregistered: list[object] = []
        self.close_calls = 0

    def register_service(self, service_info: object, **kwargs: object) -> None:
        if self.register_error is not None:
            raise self.register_error
        self.registered.append((service_info, kwargs))

    def unregister_service(self, service_info: object) -> None:
        self.unregistered.append(service_info)

    def close(self) -> None:
        self.close_calls += 1


def remote_discovery_settings() -> Settings:
    return Settings(
        host="192.168.1.44",
        port=9876,
        pairing_code="pairing-secret",
        require_auth=True,
        discovery_enabled=True,
        discovery_name="Office StreamDeck",
    )


def test_disabled_discovery_does_not_create_mdns_resources() -> None:
    calls: list[str] = []
    publisher = DiscoveryPublisher(
        Settings(),
        address_provider=lambda: calls.append("addresses") or ["10.0.0.5"],
        zeroconf_factory=lambda: calls.append("zeroconf") or FakeZeroconf(),
    )

    publisher.start()

    assert calls == []
    assert publisher.is_running is False


def test_publisher_announces_only_private_ipv4_and_closed_metadata() -> None:
    service_kwargs: dict[str, object] = {}
    zeroconf = FakeZeroconf()

    def service_info_factory(**kwargs: object) -> object:
        service_kwargs.update(kwargs)
        return kwargs

    publisher = DiscoveryPublisher(
        remote_discovery_settings(),
        address_provider=lambda: [
            "127.0.0.1",
            "8.8.8.8",
            "10.0.0.5",
            "192.168.1.4",
            "172.16.2.3",
            "169.254.1.1",
        ],
        zeroconf_factory=lambda: zeroconf,
        service_info_factory=service_info_factory,
    )

    publisher.start()

    assert service_kwargs["type_"] == DISCOVERY_SERVICE_TYPE
    assert service_kwargs["name"] == (
        "Office StreamDeck._android-streamdeck._tcp.local."
    )
    assert service_kwargs["port"] == 9876
    assert service_kwargs["addresses"] == [
        bytes((10, 0, 0, 5)),
        bytes((192, 168, 1, 4)),
        bytes((172, 16, 2, 3)),
    ]
    assert service_kwargs["properties"] == {
        b"protocol_version": b"0.1",
        b"requires_pairing": b"true",
    }
    announcement = repr(service_kwargs)
    assert "pairing-secret" not in announcement
    assert "sqlite" not in announcement.lower()
    assert "snapshot" not in announcement.lower()
    assert zeroconf.registered == [(service_kwargs, {"allow_name_change": True})]


def test_publisher_fails_safely_without_private_address() -> None:
    zeroconf_calls: list[str] = []
    publisher = DiscoveryPublisher(
        remote_discovery_settings(),
        address_provider=lambda: ["127.0.0.1", "8.8.8.8", "169.254.1.1"],
        zeroconf_factory=lambda: zeroconf_calls.append("created") or FakeZeroconf(),
    )

    with pytest.raises(DiscoveryError, match="no eligible IPv4 address") as error:
        publisher.start()

    assert "pairing-secret" not in str(error.value)
    assert zeroconf_calls == []
    assert publisher.is_running is False


def test_start_stop_is_idempotent() -> None:
    zeroconf = FakeZeroconf()
    service_info: dict[str, object] = {}
    publisher = DiscoveryPublisher(
        remote_discovery_settings(),
        address_provider=lambda: ["10.0.0.5"],
        zeroconf_factory=lambda: zeroconf,
        service_info_factory=lambda **kwargs: (
            service_info.update(kwargs) or service_info
        ),
    )

    publisher.start()
    publisher.start()
    publisher.stop()
    publisher.stop()

    assert len(zeroconf.registered) == 1
    assert zeroconf.unregistered == [service_info]
    assert zeroconf.close_calls == 1
    assert publisher.is_running is False


def test_registration_failure_closes_zeroconf_and_sanitizes_error() -> None:
    zeroconf = FakeZeroconf(
        register_error=RuntimeError(
            "pairing-secret /runtime/streamdeck.sqlite3 snapshot-token"
        )
    )
    publisher = DiscoveryPublisher(
        remote_discovery_settings(),
        address_provider=lambda: ["10.0.0.5"],
        zeroconf_factory=lambda: zeroconf,
        service_info_factory=lambda **kwargs: kwargs,
    )

    with pytest.raises(
        DiscoveryError, match="local discovery could not start"
    ) as error:
        publisher.start()

    assert "pairing-secret" not in str(error.value)
    assert "streamdeck.sqlite3" not in str(error.value)
    assert "snapshot-token" not in str(error.value)
    assert zeroconf.close_calls == 1
    assert publisher.is_running is False
