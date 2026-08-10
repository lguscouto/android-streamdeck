from __future__ import annotations

import socket
from collections.abc import Callable, Iterable
from ipaddress import IPv4Address, IPv4Network
from typing import Any, Protocol

from app.config import Settings

DISCOVERY_SERVICE_TYPE = "_android-streamdeck._tcp.local."
SERVICE_TYPE = DISCOVERY_SERVICE_TYPE
DISCOVERY_INSTANCE_NAME = "Android Stream Deck"
DISCOVERY_PROPERTIES = {
    b"protocol_version": b"0.1",
    b"requires_pairing": b"true",
    b"transport": b"https",
    b"tls": b"required",
}
_RFC1918_NETWORKS = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)


class DiscoveryError(RuntimeError):
    """Raised when the opt-in local service advertisement cannot start safely."""


class ZeroconfClient(Protocol):
    def register_service(self, service_info: object, **kwargs: object) -> None: ...

    def unregister_service(self, service_info: object) -> None: ...

    def close(self) -> None: ...


def _eligible_ipv4_addresses(candidates: Iterable[str]) -> tuple[str, ...]:
    addresses: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            address = IPv4Address(candidate)
        except ValueError:
            continue
        if not any(address in network for network in _RFC1918_NETWORKS):
            continue
        normalized = str(address)
        if normalized not in seen:
            seen.add(normalized)
            addresses.append(normalized)
    return tuple(addresses)


def default_ipv4_addresses() -> tuple[str, ...]:
    """Return eligible private IPv4 addresses without announcing loopback."""
    try:
        candidates = {
            result[4][0]
            for result in socket.getaddrinfo(
                socket.gethostname(),
                None,
                family=socket.AF_INET,
                type=socket.SOCK_DGRAM,
            )
        }
    except OSError:
        return ()

    return _eligible_ipv4_addresses(sorted(candidates))


def _create_zeroconf_client() -> ZeroconfClient:
    from zeroconf import Zeroconf

    return Zeroconf()


def _create_service_info(**kwargs: Any) -> object:
    from zeroconf import ServiceInfo

    return ServiceInfo(**kwargs)


class DiscoveryPublisher:
    """Publish a minimal LAN record only when discovery is explicitly enabled."""

    def __init__(
        self,
        settings: Settings,
        *,
        address_provider: Callable[[], Iterable[str]] = default_ipv4_addresses,
        zeroconf_factory: Callable[[], ZeroconfClient] = _create_zeroconf_client,
        service_info_factory: Callable[..., object] = _create_service_info,
    ) -> None:
        self._settings = settings
        self._address_provider = address_provider
        self._zeroconf_factory = zeroconf_factory
        self._service_info_factory = service_info_factory
        self._zeroconf: ZeroconfClient | None = None
        self._service_info: object | None = None

    @property
    def is_running(self) -> bool:
        return self._zeroconf is not None

    def start(self) -> None:
        """Register the service record. Calling it repeatedly is idempotent."""
        if not self._settings.discovery_enabled or self.is_running:
            return

        client: ZeroconfClient | None = None
        try:
            addresses = [
                IPv4Address(address).packed
                for address in _eligible_ipv4_addresses(self._address_provider())
            ]
            if not addresses:
                raise DiscoveryError("no eligible IPv4 address is available")
            service_info = self._service_info_factory(
                type_=DISCOVERY_SERVICE_TYPE,
                name=f"{self._settings.discovery_name}.{DISCOVERY_SERVICE_TYPE}",
                addresses=addresses,
                port=self._settings.port,
                properties=DISCOVERY_PROPERTIES,
            )
            client = self._zeroconf_factory()
            client.register_service(service_info, allow_name_change=True)
        except DiscoveryError:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            raise DiscoveryError("local discovery could not start") from exc
        else:
            self._zeroconf = client
            self._service_info = service_info

    def stop(self) -> None:
        """Unregister the service and release mDNS resources without leaking state."""
        client = self._zeroconf
        service_info = self._service_info
        self._zeroconf = None
        self._service_info = None
        if client is None:
            return
        try:
            if service_info is not None:
                client.unregister_service(service_info)
        except Exception:
            pass
        finally:
            try:
                client.close()
            except Exception:
                pass


__all__ = [
    "DISCOVERY_INSTANCE_NAME",
    "DISCOVERY_PROPERTIES",
    "DISCOVERY_SERVICE_TYPE",
    "SERVICE_TYPE",
    "DiscoveryError",
    "DiscoveryPublisher",
    "default_ipv4_addresses",
]
