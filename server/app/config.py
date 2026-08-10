from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from ipaddress import AddressValueError, IPv4Address, IPv4Network
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_DISCOVERY_ENABLED = False
DEFAULT_DISCOVERY_NAME = "Android Stream Deck"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_PAIRING_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,63}$", re.ASCII)
_DISCOVERY_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9 ._-]{0,61}[A-Za-z0-9])?$", re.ASCII
)
_RFC1918_NETWORKS = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)


def default_database_path() -> Path:
    """Keep frozen-bundle data in the user's local application-data directory."""
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        root = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / "AppData" / "Local"
        )
        return root / "AndroidStreamDeck" / "streamdeck.sqlite3"
    return Path(__file__).resolve().parents[1] / "data" / "streamdeck.sqlite3"


DEFAULT_DATABASE_PATH = default_database_path()


def _is_rfc1918_ipv4_host(host: str) -> bool:
    try:
        address = IPv4Address(host.strip())
    except AddressValueError:
        return False
    return any(address in network for network in _RFC1918_NETWORKS)


@dataclass(frozen=True, slots=True)
class Settings:
    """Non-secret runtime settings for the local server."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    database_path: str | Path = DEFAULT_DATABASE_PATH
    pairing_code: str | None = None
    require_auth: bool = False
    discovery_enabled: bool = DEFAULT_DISCOVERY_ENABLED
    discovery_name: str = DEFAULT_DISCOVERY_NAME

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        code = self.pairing_code
        if code is not None and not _PAIRING_CODE_PATTERN.fullmatch(code):
            raise ValueError(
                "pairing_code must contain 6-64 ASCII letters, digits, '.', '_' or '-'"
            )
        if self.require_auth and code is None:
            raise ValueError("authentication requires a pairing code")
        if not isinstance(self.discovery_enabled, bool):
            raise ValueError("discovery_enabled must be a boolean")
        if not _DISCOVERY_NAME_PATTERN.fullmatch(self.discovery_name):
            raise ValueError(
                "discovery_name must be 1-63 ASCII letters, digits, spaces, '.', '_' "
                "or '-'"
            )
        normalized_host = self.host.strip().lower()
        if normalized_host not in _LOOPBACK_HOSTS and not self.require_auth:
            raise ValueError("remote bind requires authentication")
        if self.discovery_enabled and not _is_rfc1918_ipv4_host(self.host):
            raise ValueError("discovery requires a concrete private IPv4 bind")

    @classmethod
    def from_env(cls) -> "Settings":
        """Read bind, SQLite, pairing, and optional discovery from environment."""
        host = os.getenv("STREAMDECK_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
        raw_port = os.getenv("STREAMDECK_PORT", str(DEFAULT_PORT)).strip()
        database_path = os.getenv("STREAMDECK_DATABASE_PATH", "").strip()
        pairing_code = os.getenv("STREAMDECK_PAIRING_CODE", "").strip() or None
        raw_require_auth = os.getenv("STREAMDECK_REQUIRE_AUTH", "").strip().lower()
        raw_discovery_enabled = (
            os.getenv("STREAMDECK_DISCOVERY_ENABLED", "").strip().lower()
        )
        discovery_name = (
            os.getenv("STREAMDECK_DISCOVERY_NAME", DEFAULT_DISCOVERY_NAME).strip()
            or DEFAULT_DISCOVERY_NAME
        )

        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("STREAMDECK_PORT must be an integer") from exc

        if raw_require_auth in {"", "auto"}:
            require_auth = pairing_code is not None
        elif raw_require_auth in {"1", "true", "yes", "on"}:
            require_auth = True
        elif raw_require_auth in {"0", "false", "no", "off"}:
            require_auth = False
        else:
            raise ValueError("STREAMDECK_REQUIRE_AUTH must be a boolean")

        if raw_discovery_enabled in {"", "0", "false", "no", "off"}:
            discovery_enabled = False
        elif raw_discovery_enabled in {"1", "true", "yes", "on"}:
            discovery_enabled = True
        else:
            raise ValueError("STREAMDECK_DISCOVERY_ENABLED must be a boolean")

        return cls(
            host=host,
            port=port,
            database_path=database_path or DEFAULT_DATABASE_PATH,
            pairing_code=pairing_code,
            require_auth=require_auth,
            discovery_enabled=discovery_enabled,
            discovery_name=discovery_name,
        )
