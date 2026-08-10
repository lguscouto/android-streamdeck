from __future__ import annotations

import base64
import csv
import ctypes
import hashlib
import ipaddress
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_CA_CERTIFICATE_NAME = "ca-cert.pem"
_CA_PRIVATE_KEY_NAME = "ca-key.pem"
_CERTIFICATE_NAME = "leaf-chain.pem"
_PRIVATE_KEY_NAME = "leaf-key.pem"
_CA_VALIDITY = timedelta(days=3650)
_LEAF_VALIDITY = timedelta(days=90)
_LEAF_RENEWAL_MARGIN = timedelta(days=30)
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class TlsMaterialError(RuntimeError):
    """Raised when local TLS material is absent, incomplete, or invalid."""


@dataclass(frozen=True, slots=True)
class TlsMaterial:
    ca_certificate_path: Path
    certificate_path: Path
    private_key_path: Path
    trust_code: str


class TlsMaterialStore:
    """Own private-CA TLS material stored outside the source tree and bundle."""

    def __init__(
        self,
        state_dir: Path,
        identities: Iterable[str],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_dir = Path(state_dir)
        self._identities = normalize_tls_identities(identities)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def ensure(self) -> TlsMaterial:
        now = _utc_now(self._clock())
        self._state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        _restrict_private_directory(self._state_dir)
        with _material_lock(self._state_dir):
            return self._ensure_locked(now)

    def _ensure_locked(self, now: datetime) -> TlsMaterial:
        ca_certificate_path = self._state_dir / _CA_CERTIFICATE_NAME
        ca_private_key_path = self._state_dir / _CA_PRIVATE_KEY_NAME
        certificate_path = self._state_dir / _CERTIFICATE_NAME
        private_key_path = self._state_dir / _PRIVATE_KEY_NAME
        paths = (
            ca_certificate_path,
            ca_private_key_path,
            certificate_path,
            private_key_path,
        )
        present_count = sum(path.is_file() for path in paths)
        if present_count == 0:
            ca_certificate, ca_key = _create_ca(now)
            _write_ca(ca_certificate_path, ca_private_key_path, ca_certificate, ca_key)
            _write_leaf(
                certificate_path,
                private_key_path,
                ca_certificate,
                ca_key,
                self._identities,
                now,
            )
        elif present_count != len(paths):
            raise TlsMaterialError("TLS material is incomplete")
        else:
            ca_certificate, ca_key, leaf_certificate = _load_and_validate_material(
                ca_certificate_path,
                ca_private_key_path,
                certificate_path,
                private_key_path,
                self._identities,
                now,
            )
            if _leaf_needs_renewal(leaf_certificate, now):
                _write_leaf(
                    certificate_path,
                    private_key_path,
                    ca_certificate,
                    ca_key,
                    self._identities,
                    now,
                )

        return TlsMaterial(
            ca_certificate_path=ca_certificate_path,
            certificate_path=certificate_path,
            private_key_path=private_key_path,
            trust_code=_trust_code(ca_certificate_path),
        )


def normalize_tls_identities(identities: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw_identity in identities:
        identity = raw_identity.strip()
        if not identity:
            raise ValueError("TLS identity must not be empty")
        try:
            normalized_identity = str(ipaddress.ip_address(identity))
        except ValueError:
            normalized_identity = _normalize_dns_identity(identity)
        if normalized_identity not in normalized:
            normalized.append(normalized_identity)
    if not normalized:
        raise ValueError("TLS requires at least one server identity")
    return tuple(normalized)


def _normalize_dns_identity(identity: str) -> str:
    if (
        ":" in identity
        or "/" in identity
        or "*" in identity
        or any(character.isspace() or ord(character) < 32 for character in identity)
    ):
        raise ValueError("TLS identity must be an IP literal or canonical DNS name")
    try:
        ascii_identity = identity.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError(
            "TLS identity must be an IP literal or canonical DNS name"
        ) from exc
    if len(ascii_identity) > 253 or ascii_identity.endswith("."):
        raise ValueError("TLS identity must be an IP literal or canonical DNS name")
    labels = ascii_identity.split(".")
    if not all(_DNS_LABEL.fullmatch(label) for label in labels):
        raise ValueError("TLS identity must be an IP literal or canonical DNS name")
    return ascii_identity


def _utc_now(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("TLS clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _create_ca(now: datetime) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Android Stream Deck Local CA")]
    )
    ca_certificate = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + _CA_VALIDITY)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return ca_certificate, ca_key


def _write_ca(
    certificate_path: Path,
    private_key_path: Path,
    certificate: x509.Certificate,
    private_key: ec.EllipticCurvePrivateKey,
) -> None:
    _atomic_write(
        certificate_path,
        certificate.public_bytes(serialization.Encoding.PEM),
        private=False,
    )
    _atomic_write(private_key_path, _private_key_pem(private_key), private=True)


def _write_leaf(
    certificate_path: Path,
    private_key_path: Path,
    ca_certificate: x509.Certificate,
    ca_key: ec.EllipticCurvePrivateKey,
    identities: tuple[str, ...],
    now: datetime,
) -> None:
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_certificate = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, identities[0])])
        )
        .issuer_name(ca_certificate.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + _LEAF_VALIDITY)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName(_subject_alternative_names(identities)),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    _atomic_write(
        certificate_path,
        leaf_certificate.public_bytes(serialization.Encoding.PEM)
        + ca_certificate.public_bytes(serialization.Encoding.PEM),
        private=False,
    )
    _atomic_write(private_key_path, _private_key_pem(leaf_key), private=True)


def _private_key_pem(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _load_and_validate_material(
    ca_certificate_path: Path,
    ca_private_key_path: Path,
    certificate_path: Path,
    private_key_path: Path,
    identities: tuple[str, ...],
    now: datetime,
) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey, x509.Certificate]:
    ca_certificate = _load_certificate(ca_certificate_path, "CA certificate")
    ca_key = _load_private_key(ca_private_key_path, "CA private key")
    _validate_ca(ca_certificate, ca_key, now)
    leaf_certificate, chain_ca_certificate = _load_chain(certificate_path)
    leaf_key = _load_private_key(private_key_path, "leaf private key")
    _validate_leaf(
        leaf_certificate,
        chain_ca_certificate,
        leaf_key,
        ca_certificate,
        identities,
        now,
    )
    return ca_certificate, ca_key, leaf_certificate


def _load_certificate(path: Path, label: str) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise TlsMaterialError(f"TLS {label} is invalid") from exc


def _load_private_key(path: Path, label: str) -> ec.EllipticCurvePrivateKey:
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, TypeError, ValueError) as exc:
        raise TlsMaterialError(f"TLS {label} is invalid") from exc
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
        key.curve, ec.SECP256R1
    ):
        raise TlsMaterialError(f"TLS {label} is invalid")
    return key


def _load_chain(path: Path) -> tuple[x509.Certificate, x509.Certificate]:
    try:
        certificates = x509.load_pem_x509_certificates(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise TlsMaterialError("TLS leaf certificate chain is invalid") from exc
    if len(certificates) != 2:
        raise TlsMaterialError("TLS leaf certificate chain is invalid")
    return certificates[0], certificates[1]


def _validate_ca(
    certificate: x509.Certificate,
    private_key: ec.EllipticCurvePrivateKey,
    now: datetime,
) -> None:
    if not _public_keys_match(certificate.public_key(), private_key.public_key()):
        raise TlsMaterialError("TLS CA private key does not match certificate")
    if certificate.subject != certificate.issuer:
        raise TlsMaterialError("TLS CA certificate is invalid")
    _verify_signature(certificate, certificate.public_key(), "CA certificate")
    _require_current_validity(certificate, now, "CA certificate")
    try:
        constraints = certificate.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
        usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        subject_key_identifier = certificate.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier
        ).value
    except x509.ExtensionNotFound as exc:
        raise TlsMaterialError("TLS CA certificate is invalid") from exc
    if not constraints.ca or constraints.path_length != 0 or not usage.key_cert_sign:
        raise TlsMaterialError("TLS CA certificate is invalid")
    if subject_key_identifier.digest != _subject_key_identifier(certificate):
        raise TlsMaterialError("TLS CA certificate is invalid")


def _validate_leaf(
    certificate: x509.Certificate,
    chain_ca_certificate: x509.Certificate,
    private_key: ec.EllipticCurvePrivateKey,
    ca_certificate: x509.Certificate,
    identities: tuple[str, ...],
    now: datetime,
) -> None:
    if chain_ca_certificate.fingerprint(hashes.SHA256()) != ca_certificate.fingerprint(
        hashes.SHA256()
    ):
        raise TlsMaterialError("TLS leaf certificate chain is invalid")
    if not _public_keys_match(certificate.public_key(), private_key.public_key()):
        raise TlsMaterialError("TLS leaf private key does not match certificate")
    if certificate.issuer != ca_certificate.subject:
        raise TlsMaterialError("TLS leaf certificate is invalid")
    _verify_signature(certificate, ca_certificate.public_key(), "leaf certificate")
    if _not_valid_before(certificate) > now:
        raise TlsMaterialError("TLS leaf certificate is not yet valid")
    try:
        constraints = certificate.extensions.get_extension_for_class(
            x509.BasicConstraints
        ).value
        usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        extended_usage = certificate.extensions.get_extension_for_class(
            x509.ExtendedKeyUsage
        ).value
        subject_alternative_names = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        subject_key_identifier = certificate.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier
        ).value
        authority_key_identifier = certificate.extensions.get_extension_for_class(
            x509.AuthorityKeyIdentifier
        ).value
        ca_subject_key_identifier = ca_certificate.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier
        ).value
    except x509.ExtensionNotFound as exc:
        raise TlsMaterialError("TLS leaf certificate is invalid") from exc
    common_names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if len(common_names) != 1 or common_names[0].value != identities[0]:
        raise TlsMaterialError("TLS leaf certificate is invalid")
    if constraints.ca or usage.key_cert_sign or not usage.digital_signature:
        raise TlsMaterialError("TLS leaf certificate is invalid")
    if ExtendedKeyUsageOID.SERVER_AUTH not in extended_usage:
        raise TlsMaterialError("TLS leaf certificate is invalid")
    if _general_name_values(subject_alternative_names) != _identity_values(identities):
        raise TlsMaterialError("TLS leaf certificate SANs are invalid")
    if subject_key_identifier.digest != _subject_key_identifier(certificate):
        raise TlsMaterialError("TLS leaf certificate is invalid")
    if authority_key_identifier.key_identifier != ca_subject_key_identifier.digest:
        raise TlsMaterialError("TLS leaf certificate is invalid")


def _verify_signature(
    certificate: x509.Certificate,
    issuer_public_key: ec.EllipticCurvePublicKey,
    label: str,
) -> None:
    try:
        issuer_public_key.verify(
            certificate.signature,
            certificate.tbs_certificate_bytes,
            ec.ECDSA(certificate.signature_hash_algorithm),
        )
    except (InvalidSignature, ValueError) as exc:
        raise TlsMaterialError(f"TLS {label} is invalid") from exc


def _require_current_validity(
    certificate: x509.Certificate, now: datetime, label: str
) -> None:
    if _not_valid_before(certificate) > now or _not_valid_after(certificate) <= now:
        raise TlsMaterialError(f"TLS {label} is not currently valid")


def _leaf_needs_renewal(certificate: x509.Certificate, now: datetime) -> bool:
    return _not_valid_after(certificate) <= now + _LEAF_RENEWAL_MARGIN


def _not_valid_before(certificate: x509.Certificate) -> datetime:
    return certificate.not_valid_before_utc


def _not_valid_after(certificate: x509.Certificate) -> datetime:
    return certificate.not_valid_after_utc


def _public_keys_match(
    first: ec.EllipticCurvePublicKey, second: ec.EllipticCurvePublicKey
) -> bool:
    return first.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ) == second.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _subject_key_identifier(certificate: x509.Certificate) -> bytes:
    return x509.SubjectKeyIdentifier.from_public_key(certificate.public_key()).digest


def _subject_alternative_names(identities: tuple[str, ...]) -> list[x509.GeneralName]:
    names: list[x509.GeneralName] = []
    for identity in identities:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(identity)))
        except ValueError:
            names.append(x509.DNSName(identity))
    return names


def _general_name_values(
    names: x509.SubjectAlternativeName,
) -> tuple[tuple[str, str], ...]:
    return tuple((type(name).__name__, str(name.value)) for name in names)


def _identity_values(identities: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        ("IPAddress", str(ipaddress.ip_address(identity)))
        if _is_ip_address(identity)
        else ("DNSName", identity)
        for identity in identities
    )


def _is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _trust_code(certificate_path: Path) -> str:
    certificate = _load_certificate(certificate_path, "CA certificate")
    subject_public_key_info = certificate.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    encoded = base64.b32encode(
        hashlib.sha256(subject_public_key_info).digest()[:10]
    ).decode("ascii")
    return "-".join(encoded[index : index + 4] for index in range(0, 16, 4))


@contextmanager
def _material_lock(state_dir: Path) -> Iterator[None]:
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = state_dir / ".tls-material.lock"
    with lock_path.open("a+b") as lock_file:
        _lock_file(lock_file)
        try:
            yield
        finally:
            _unlock_file(lock_file)


def _lock_file(lock_file) -> None:
    lock_file.seek(0)
    if os.fstat(lock_file.fileno()).st_size == 0:
        lock_file.seek(0)
        lock_file.write(b"0")
        lock_file.flush()
        os.fsync(lock_file.fileno())
    lock_file.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    except OSError as exc:
        raise TlsMaterialError("TLS material lock could not be acquired") from exc


def _unlock_file(lock_file) -> None:
    lock_file.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise TlsMaterialError("TLS material lock could not be released") from exc


def _restrict_private_directory(path: Path) -> None:
    if os.name == "nt":
        _restrict_windows_path(path, directory=True)
    else:
        os.chmod(path, 0o700)


def _restrict_private_file(path: Path) -> None:
    if os.name == "nt":
        _restrict_windows_path(path, directory=False)
    else:
        os.chmod(path, 0o600)


def _restrict_windows_path(path: Path, *, directory: bool) -> None:
    sid = _current_windows_user_sid()
    _apply_windows_user_only_dacl(path, sid, directory=directory)

    icacls = (
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "icacls.exe"
    )
    verification = _run_windows_command([str(icacls), str(path)])
    access_lines = [
        line for line in verification.stdout.splitlines() if ":" in line and "(" in line
    ]
    expected_flags = "(OI)(CI)(F)" if directory else "(F)"
    if (
        verification.returncode != 0
        or len(access_lines) != 1
        or expected_flags not in access_lines[0]
    ):
        raise TlsMaterialError("TLS private key ACL could not be verified")


def _apply_windows_user_only_dacl(path: Path, sid: str, *, directory: bool) -> None:
    security_descriptor = ctypes.c_void_p()
    descriptor_size = ctypes.c_ulong()
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_ulong),
    ]
    convert.restype = ctypes.c_int
    set_file_security = advapi32.SetFileSecurityW
    set_file_security.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_void_p]
    set_file_security.restype = ctypes.c_int
    local_free = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p

    ace_flags = "OICI" if directory else ""
    sddl = f"D:P(A;{ace_flags};FA;;;{sid})"
    if not convert(
        sddl, 1, ctypes.byref(security_descriptor), ctypes.byref(descriptor_size)
    ):
        raise TlsMaterialError("TLS private key ACL descriptor could not be created")
    try:
        dacl_security_information = 0x00000004 | 0x80000000
        if not set_file_security(
            str(path), dacl_security_information, security_descriptor
        ):
            raise TlsMaterialError("TLS private key ACL could not be applied")
    finally:
        local_free(security_descriptor)


def _current_windows_user_sid() -> str:
    whoami = (
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "whoami.exe"
    )
    result = _run_windows_command([str(whoami), "/user", "/fo", "csv", "/nh"])
    if result.returncode != 0:
        raise TlsMaterialError("current Windows user SID is unavailable")
    rows = list(csv.reader(result.stdout.splitlines()))
    if len(rows) != 1 or len(rows[0]) < 2:
        raise TlsMaterialError("current Windows user SID is invalid")
    sid = rows[0][-1].strip()
    if not re.fullmatch(r"S-1-[0-9-]+", sid):
        raise TlsMaterialError("current Windows user SID is invalid")
    return sid


def _run_windows_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
        )
    except OSError as exc:
        raise TlsMaterialError("Windows ACL tooling is unavailable") from exc


def _atomic_write(path: Path, data: bytes, *, private: bool) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}."
    )
    temporary_path = Path(temporary_name)
    try:
        if private:
            os.chmod(temporary_path, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        if private:
            _restrict_private_file(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


__all__ = ["TlsMaterial", "TlsMaterialError", "TlsMaterialStore"]
