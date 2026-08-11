from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import ipaddress
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PAIRING_PROTOCOL_VERSION = 1
PAIRING_TTL = timedelta(minutes=10)
PAIRING_PROTOCOL_PREFIX = f"streamdeck-pairing-v{PAIRING_PROTOCOL_VERSION}"
PAIRING_KEY_INFO = PAIRING_PROTOCOL_PREFIX.encode("ascii")
_PAIRING_BYTES = 16
_BASE32_PATTERN = re.compile(r"^[A-Z2-7]{26}$", re.ASCII)
_CERTIFICATE_BEGIN = "-----BEGIN CERTIFICATE-----"
_CERTIFICATE_END = "-----END CERTIFICATE-----"
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22}$", re.ASCII)
_PROOF_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$", re.ASCII)
_STABLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", re.ASCII)
_RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


class PairingSessionError(RuntimeError):
    """Base class for safe temporary-pairing failures."""


class PairingSessionExpiredError(PairingSessionError):
    """Raised when the session is absent, rotated, or expired."""


class PairingSessionUsedError(PairingSessionError):
    """Raised when a consumed one-time session is replayed."""


class PairingProofInvalidError(PairingSessionError):
    """Raised when a password-derived proof does not match."""


@dataclass(frozen=True, slots=True)
class PairingSessionPresentation:
    session_id: str
    pairing_code: str
    expires_at: str
    server_ip: str
    port: int
    qr_uri: str


@dataclass(frozen=True, slots=True)
class PairingBootstrapBundle:
    version: int
    session_id: str
    salt: str
    expires_at: str
    server_ip: str
    port: int
    ca_certificate_pem: str
    server_proof: str


@dataclass(frozen=True, slots=True)
class PairingClaim:
    session_id: str
    client_id: str
    client_version: str
    server_ip: str
    port: int
    ca_certificate_pem: str


@dataclass(slots=True)
class _PairingSession:
    session_id: str
    pairing_key: bytearray
    salt: bytearray
    expires_at: datetime
    deadline_monotonic: float
    server_ip: str
    port: int
    ca_certificate_pem: str
    consumed: bool = False


class PairingSessionManager:
    """Own one short-lived, in-memory, one-time pairing session.

    The clear pairing password is returned only in the presentation object. The
    manager keeps only the derived HKDF key while the session is active and never
    depends on the SQLite credential database.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        ttl: timedelta = PAIRING_TTL,
    ) -> None:
        if ttl != PAIRING_TTL:
            raise ValueError("pairing session TTL is fixed at 10 minutes")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._ttl = ttl
        self._session: _PairingSession | None = None
        self._retired: dict[str, str] = {}
        self._expiry_timer: threading.Timer | None = None
        self._lock = threading.RLock()

    @property
    def active_session_count(self) -> int:
        with self._lock:
            self._expire_if_needed_locked()
            return int(self._session is not None)

    def create_session(
        self,
        *,
        server_ip: str,
        port: int,
        ca_certificate_pem: str,
    ) -> PairingSessionPresentation:
        normalized_ip = _require_private_ipv4(server_ip)
        if (
            isinstance(port, bool)
            or not isinstance(port, int)
            or not 1 <= port <= 65535
        ):
            raise ValueError("pairing server port must be between 1 and 65535")
        _validate_ca_certificate_pem(ca_certificate_pem)

        now = _utc_now(self._clock()).replace(microsecond=0)
        expires_at = now + self._ttl
        pairing_code = normalize_pairing_code(
            base64.b32encode(secrets.token_bytes(_PAIRING_BYTES))
            .decode("ascii")
            .rstrip("=")
        )
        salt = secrets.token_bytes(_PAIRING_BYTES)
        session_id = derive_session_id(pairing_code)
        pairing_key = bytearray(derive_pairing_key(pairing_code, salt))
        session = _PairingSession(
            session_id=session_id,
            pairing_key=pairing_key,
            salt=bytearray(salt),
            expires_at=expires_at,
            deadline_monotonic=self._monotonic() + self._ttl.total_seconds(),
            server_ip=normalized_ip,
            port=port,
            ca_certificate_pem=ca_certificate_pem,
        )
        with self._lock:
            if self._session is not None:
                self._retired[self._session.session_id] = "rotated"
                _clear_session_material(self._session)
                self._cancel_expiry_timer_locked()
            self._session = session
            self._schedule_expiry_timer_locked(session)
            self._prune_retired_locked()
        expires_wire = _format_timestamp(expires_at)
        return PairingSessionPresentation(
            session_id=session_id,
            pairing_code=pairing_code,
            expires_at=expires_wire,
            server_ip=normalized_ip,
            port=port,
            qr_uri=(
                "streamdeck://pair/v1?"
                f"ip={normalized_ip}&port={port}&session={session_id}&secret={pairing_code}"
            ),
        )

    def bootstrap(self, session_id: str) -> PairingBootstrapBundle:
        _require_session_id(session_id)
        with self._lock:
            session = self._require_active_locked(session_id)
            return self._bootstrap_locked(session)

    def claim(
        self,
        *,
        session_id: str,
        client_id: str,
        client_version: str,
        client_proof: str,
    ) -> PairingClaim:
        if not isinstance(client_id, str) or not _STABLE_ID_PATTERN.fullmatch(
            client_id
        ):
            raise PairingProofInvalidError("client identity is invalid")
        if (
            not isinstance(client_version, str)
            or not 1 <= len(client_version) <= 64
            or any(character.isspace() for character in client_version)
        ):
            raise PairingProofInvalidError("client version is invalid")
        if not isinstance(client_proof, str) or not _PROOF_PATTERN.fullmatch(
            client_proof
        ):
            raise PairingProofInvalidError("pairing proof is invalid")
        with self._lock:
            session = self._require_active_locked(session_id)
            expected = compute_client_proof(
                session.pairing_key,
                session_id=session.session_id,
                client_id=client_id,
                client_version=client_version,
            )
            if not hmac.compare_digest(client_proof, expected):
                raise PairingProofInvalidError("pairing proof is invalid")
            claim = PairingClaim(
                session_id=session.session_id,
                client_id=client_id,
                client_version=client_version,
                server_ip=session.server_ip,
                port=session.port,
                ca_certificate_pem=session.ca_certificate_pem,
            )
            session.consumed = True
            self._retired[session.session_id] = "used"
            self._session = None
            self._cancel_expiry_timer_locked()
            _clear_session_material(session)
            self._prune_retired_locked()
            return claim

    def _bootstrap_locked(self, session: _PairingSession) -> PairingBootstrapBundle:
        expires_wire = _format_timestamp(session.expires_at)
        bundle_without_proof = {
            "version": PAIRING_PROTOCOL_VERSION,
            "session_id": session.session_id,
            "salt": _b64u(session.salt),
            "expires_at": expires_wire,
            "server_ip": session.server_ip,
            "port": session.port,
            "ca_certificate_pem": session.ca_certificate_pem,
        }
        proof = compute_server_proof(session.pairing_key, **bundle_without_proof)
        return PairingBootstrapBundle(
            **bundle_without_proof,
            server_proof=proof,
        )

    def _require_active_locked(self, session_id: str) -> _PairingSession:
        _require_session_id(session_id)
        self._expire_if_needed_locked()
        session = self._session
        if session is None or not hmac.compare_digest(session.session_id, session_id):
            if self._retired.get(session_id) == "used":
                raise PairingSessionUsedError("pairing session was already used")
            raise PairingSessionExpiredError("pairing session is unavailable")
        if session.consumed:
            raise PairingSessionUsedError("pairing session was already used")
        return session

    def _expire_if_needed_locked(self) -> None:
        session = self._session
        if session is not None and self._monotonic() >= session.deadline_monotonic:
            self._retired[session.session_id] = "expired"
            self._session = None
            self._cancel_expiry_timer_locked()
            _clear_session_material(session)
            self._prune_retired_locked()

    def _schedule_expiry_timer_locked(self, session: _PairingSession) -> None:
        timer = threading.Timer(
            self._ttl.total_seconds(),
            self._expire_from_timer,
            args=(session.session_id,),
        )
        timer.daemon = True
        self._expiry_timer = timer
        timer.start()

    def _cancel_expiry_timer_locked(self) -> None:
        if self._expiry_timer is not None:
            self._expiry_timer.cancel()
            self._expiry_timer = None

    def _expire_from_timer(self, session_id: str) -> None:
        with self._lock:
            session = self._session
            if session is None or session.session_id != session_id:
                return
            remaining = session.deadline_monotonic - self._monotonic()
            if remaining > 0:
                self._schedule_expiry_timer_locked(session)
                return
            self._retired[session.session_id] = "expired"
            self._session = None
            self._expiry_timer = None
            _clear_session_material(session)
            self._prune_retired_locked()

    def _prune_retired_locked(self) -> None:
        while len(self._retired) > 32:
            oldest_session_id = next(iter(self._retired))
            self._retired.pop(oldest_session_id, None)


def _clear_session_material(session: _PairingSession) -> None:
    """Overwrite and release derived material before dropping a session."""
    for material in (session.pairing_key, session.salt):
        material[:] = b"\x00" * len(material)
        material.clear()


def normalize_pairing_code(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("pairing password is invalid")
    normalized = "".join(value.split()).replace("-", "").upper()
    if not _BASE32_PATTERN.fullmatch(normalized):
        raise ValueError("pairing password is invalid")
    try:
        decoded = base64.b32decode(normalized + "=" * (-len(normalized) % 8))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("pairing password is invalid") from exc
    if len(decoded) != _PAIRING_BYTES:
        raise ValueError("pairing password is invalid")
    return normalized


def _require_session_id(value: str) -> str:
    if not isinstance(value, str) or not _SESSION_ID_PATTERN.fullmatch(value):
        raise PairingSessionExpiredError("pairing session is unavailable")
    return value


def _validate_ca_certificate_pem(value: str) -> None:
    if not isinstance(value, str) or len(value.encode("utf-8")) > 64 * 1024:
        raise ValueError("pairing CA certificate is invalid")
    normalized = value.strip()
    if (
        normalized.count(_CERTIFICATE_BEGIN) != 1
        or normalized.count(_CERTIFICATE_END) != 1
    ):
        raise ValueError("pairing CA certificate is invalid")
    begin = normalized.index(_CERTIFICATE_BEGIN) + len(_CERTIFICATE_BEGIN)
    end = normalized.index(_CERTIFICATE_END)
    if end <= begin:
        raise ValueError("pairing CA certificate is invalid")
    body = "".join(normalized[begin:end].split())
    try:
        decoded = base64.b64decode(body, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("pairing CA certificate is invalid") from exc
    if not decoded:
        raise ValueError("pairing CA certificate is invalid")


def derive_session_id(pairing_code: str) -> str:
    normalized = normalize_pairing_code(pairing_code)
    digest = hashlib.sha256(
        f"{PAIRING_PROTOCOL_PREFIX}|session|".encode("ascii")
        + normalized.encode("ascii")
    ).digest()[:_PAIRING_BYTES]
    return _b64u(digest)


def derive_pairing_key(pairing_code: str, salt: bytes) -> bytes:
    normalized = normalize_pairing_code(pairing_code)
    if len(salt) != _PAIRING_BYTES:
        raise ValueError("pairing salt is invalid")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=PAIRING_KEY_INFO,
    ).derive(normalized.encode("ascii"))


def compute_server_proof(
    pairing_key: bytes,
    *,
    version: int,
    session_id: str,
    salt: str,
    expires_at: str,
    server_ip: str,
    port: int,
    ca_certificate_pem: str,
) -> str:
    canonical = _canonical_bootstrap(
        version=version,
        session_id=session_id,
        salt=salt,
        expires_at=expires_at,
        server_ip=server_ip,
        port=port,
        ca_certificate_pem=ca_certificate_pem,
    )
    return _b64u(hmac.new(pairing_key, canonical, hashlib.sha256).digest())


def verify_server_proof(bundle: PairingBootstrapBundle, pairing_key: bytes) -> bool:
    expected = compute_server_proof(
        pairing_key,
        version=bundle.version,
        session_id=bundle.session_id,
        salt=bundle.salt,
        expires_at=bundle.expires_at,
        server_ip=bundle.server_ip,
        port=bundle.port,
        ca_certificate_pem=bundle.ca_certificate_pem,
    )
    return hmac.compare_digest(bundle.server_proof, expected)


def compute_client_proof(
    pairing_key: bytes,
    *,
    session_id: str,
    client_id: str,
    client_version: str,
) -> str:
    canonical = (
        f"{PAIRING_PROTOCOL_PREFIX}|claim|"
        f"session_id={session_id}|client_id={client_id}|client_version={client_version}"
    ).encode("utf-8")
    return _b64u(hmac.new(pairing_key, canonical, hashlib.sha256).digest())


def _canonical_bootstrap(
    *,
    version: int,
    session_id: str,
    salt: str,
    expires_at: str,
    server_ip: str,
    port: int,
    ca_certificate_pem: str,
) -> bytes:
    ca_digest = _b64u(hashlib.sha256(ca_certificate_pem.encode("utf-8")).digest())
    return (
        f"{PAIRING_PROTOCOL_PREFIX}|bootstrap|"
        f"version={version}|session_id={session_id}|salt={salt}|"
        f"expires_at={expires_at}|server_ip={server_ip}|port={port}|"
        f"ca_sha256={ca_digest}"
    ).encode("utf-8")


def _require_private_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError as exc:
        raise ValueError("pairing server IP must be a private IPv4 address") from exc
    if not isinstance(address, ipaddress.IPv4Address) or not any(
        address in network for network in _RFC1918_NETWORKS
    ):
        raise ValueError("pairing server IP must be a private IPv4 address")
    return str(address)


def _utc_now(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("pairing clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


__all__ = [
    "PAIRING_PROTOCOL_VERSION",
    "PairingBootstrapBundle",
    "PairingClaim",
    "PairingProofInvalidError",
    "PairingSessionError",
    "PairingSessionExpiredError",
    "PairingSessionManager",
    "PairingSessionPresentation",
    "PairingSessionUsedError",
    "compute_client_proof",
    "compute_server_proof",
    "derive_pairing_key",
    "derive_session_id",
    "normalize_pairing_code",
    "verify_server_proof",
]
