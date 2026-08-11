from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.pairing_session import (
    PairingProofInvalidError,
    PairingSessionExpiredError,
    PairingSessionManager,
    PairingSessionUsedError,
    compute_client_proof,
    derive_pairing_key,
    derive_session_id,
    normalize_pairing_code,
    verify_server_proof,
)

VALID_CA_PEM = (
    "-----BEGIN CERTIFICATE-----\nc3ludGhldGljLWNh\n-----END CERTIFICATE-----"
)
OTHER_CA_PEM = "-----BEGIN CERTIFICATE-----\nb3RoZXItY2E=\n-----END CERTIFICATE-----"


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        self.monotonic_value = 1000.0

    def __call__(self) -> datetime:
        return self.value

    def monotonic(self) -> float:
        return self.monotonic_value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)
        self.monotonic_value += seconds


def create_manager() -> tuple[PairingSessionManager, MutableClock]:
    clock = MutableClock()
    return PairingSessionManager(clock=clock, monotonic=clock.monotonic), clock


def session_material(
    manager: PairingSessionManager,
) -> tuple[object, object, bytes, str]:
    presentation = manager.create_session(
        server_ip="192.168.100.20",
        port=8765,
        ca_certificate_pem=VALID_CA_PEM,
    )
    bundle = manager.bootstrap(presentation.session_id)
    key = derive_pairing_key(
        presentation.pairing_code,
        base64.urlsafe_b64decode(bundle.salt + "=" * (-len(bundle.salt) % 4)),
    )
    proof = compute_client_proof(
        key,
        session_id=bundle.session_id,
        client_id="android-test",
        client_version="0.1.0",
    )
    return presentation, bundle, key, proof


def test_session_password_has_at_least_128_bits_and_is_not_persisted() -> None:
    manager, _ = create_manager()

    presentation = manager.create_session(
        server_ip="192.168.100.20",
        port=8765,
        ca_certificate_pem=VALID_CA_PEM,
    )

    decoded = base64.b32decode(
        presentation.pairing_code + "=" * (-len(presentation.pairing_code) % 8)
    )
    assert len(decoded) >= 16
    assert presentation.pairing_code == presentation.pairing_code.upper()
    assert presentation.session_id == derive_session_id(presentation.pairing_code)
    assert manager.active_session_count == 1
    assert not hasattr(manager, "database")


def test_hkdf_vector_is_independent_of_the_implementation() -> None:
    key = derive_pairing_key("A" * 26, bytes(16))

    assert base64.urlsafe_b64encode(key).decode("ascii").rstrip("=") == (
        "W8ZB0GOaZy6XU5OrE6Wcu0E9uVfUKxUS2YseoJGO1iI"
    )


@pytest.mark.parametrize(
    "value",
    ["A" * 6, "A" * 25, "A" * 27, "A" * 25 + "0"],
)
def test_normalize_pairing_code_rejects_noncanonical_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_pairing_code(value)


def test_normalize_pairing_code_accepts_human_case_and_separators() -> None:
    assert normalize_pairing_code("a" * 26) == "A" * 26
    assert normalize_pairing_code("A" * 13 + "-" + "A" * 13) == "A" * 26


def test_bootstrap_proof_binds_all_public_fields_to_the_password() -> None:
    manager, _ = create_manager()
    presentation, bundle, key, _ = session_material(manager)

    assert verify_server_proof(bundle, key)
    mutations = (
        replace(bundle, version=2),
        replace(bundle, session_id="B" * 22),
        replace(bundle, salt="B" * 22),
        replace(bundle, expires_at="2026-08-11T12:01:00Z"),
        replace(bundle, server_ip="192.168.100.21"),
        replace(bundle, port=8766),
        replace(bundle, ca_certificate_pem=OTHER_CA_PEM),
    )
    assert all(not verify_server_proof(mutated, key) for mutated in mutations)
    assert bundle.session_id == presentation.session_id


def test_claim_invalid_proof_does_not_consume_session() -> None:
    manager, _ = create_manager()
    presentation, bundle, key, proof = session_material(manager)

    with pytest.raises(PairingProofInvalidError):
        manager.claim(
            session_id=bundle.session_id,
            client_id="android-test",
            client_version="0.1.0",
            client_proof="A" * 43,
        )

    claim = manager.claim(
        session_id=presentation.session_id,
        client_id="android-test",
        client_version="0.1.0",
        client_proof=proof,
    )
    assert claim.client_id == "android-test"


def test_claim_consumes_session_once_and_rejects_replay() -> None:
    manager, _ = create_manager()
    _, bundle, _, proof = session_material(manager)

    claim = manager.claim(
        session_id=bundle.session_id,
        client_id="android-test",
        client_version="0.1.0",
        client_proof=proof,
    )

    assert claim.client_id == "android-test"
    with pytest.raises(PairingSessionUsedError):
        manager.claim(
            session_id=bundle.session_id,
            client_id="android-test",
            client_version="0.1.0",
            client_proof=proof,
        )


def test_expired_session_rejects_claim_at_exact_ttl_boundary() -> None:
    manager, clock = create_manager()
    _, bundle, _, proof = session_material(manager)
    clock.advance(600)

    with pytest.raises(PairingSessionExpiredError):
        manager.claim(
            session_id=bundle.session_id,
            client_id="android-test",
            client_version="0.1.0",
            client_proof=proof,
        )


def test_expired_session_is_rejected_without_consuming_a_new_session() -> None:
    manager, clock = create_manager()
    presentation = manager.create_session(
        server_ip="192.168.100.20",
        port=8765,
        ca_certificate_pem=VALID_CA_PEM,
    )
    clock.advance(601)

    with pytest.raises(PairingSessionExpiredError):
        manager.bootstrap(presentation.session_id)

    assert manager.active_session_count == 0


def test_regeneration_invalidates_previous_session() -> None:
    manager, _ = create_manager()
    first = manager.create_session(
        server_ip="192.168.100.20",
        port=8765,
        ca_certificate_pem=VALID_CA_PEM,
    )
    second = manager.create_session(
        server_ip="192.168.100.20",
        port=8765,
        ca_certificate_pem=VALID_CA_PEM,
    )

    assert first.session_id != second.session_id
    with pytest.raises(PairingSessionExpiredError):
        manager.bootstrap(first.session_id)
    assert manager.bootstrap(second.session_id).session_id == second.session_id


def test_invalid_port_and_session_shapes_fail_closed() -> None:
    manager, _ = create_manager()
    with pytest.raises(ValueError):
        manager.create_session(
            server_ip="192.168.100.20",
            port=1.5,  # type: ignore[arg-type]
            ca_certificate_pem=VALID_CA_PEM,
        )
    with pytest.raises(PairingSessionExpiredError):
        manager.bootstrap("not-a-session")


def test_ca_pem_shape_is_validated_before_session_creation() -> None:
    manager, _ = create_manager()
    invalid_values = (
        "synthetic-ca-pem",
        "-----BEGIN CERTIFICATE-----\nnot base64!\n-----END CERTIFICATE-----",
        "-----BEGIN CERTIFICATE-----\nYWJj\n-----END PRIVATE KEY-----",
    )
    for value in invalid_values:
        with pytest.raises(ValueError):
            manager.create_session(
                server_ip="192.168.100.20",
                port=8765,
                ca_certificate_pem=value,
            )


def test_ca_pem_size_is_bounded() -> None:
    manager, _ = create_manager()
    oversized = (
        "-----BEGIN CERTIFICATE-----\n"
        + "A" * (64 * 1024)
        + "\n-----END CERTIFICATE-----"
    )
    with pytest.raises(ValueError):
        manager.create_session(
            server_ip="192.168.100.20",
            port=8765,
            ca_certificate_pem=oversized,
        )


def test_concurrent_claims_accept_exactly_one_attempt() -> None:
    manager, _ = create_manager()
    _, bundle, _, proof = session_material(manager)

    def attempt() -> str:
        try:
            manager.claim(
                session_id=bundle.session_id,
                client_id="android-test",
                client_version="0.1.0",
                client_proof=proof,
            )
            return "accepted"
        except PairingSessionUsedError:
            return "used"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: attempt(), range(2)))

    assert sorted(outcomes) == ["accepted", "used"]


def test_retired_used_sessions_are_bounded() -> None:
    manager, _ = create_manager()

    for _ in range(40):
        presentation, bundle, _, proof = session_material(manager)
        manager.claim(
            session_id=presentation.session_id,
            client_id="android-test",
            client_version="0.1.0",
            client_proof=proof,
        )
        assert bundle.session_id == presentation.session_id

    assert len(manager._retired) <= 32  # noqa: SLF001


def test_expiring_session_clears_derived_material() -> None:
    manager, clock = create_manager()
    presentation = manager.create_session(
        server_ip="192.168.100.20",
        port=8765,
        ca_certificate_pem=VALID_CA_PEM,
    )
    session = manager._session  # noqa: SLF001
    assert session is not None
    assert session.pairing_key
    assert session.salt

    clock.advance(600)
    with pytest.raises(PairingSessionExpiredError):
        manager.bootstrap(presentation.session_id)

    assert session.pairing_key == bytearray()
    assert session.salt == bytearray()
