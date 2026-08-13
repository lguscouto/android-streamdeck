from __future__ import annotations

import ipaddress
import multiprocessing
import os
import re
import ssl
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509

from app.tls import TlsMaterialError, TlsMaterialStore


def _hold_tls_material_lock(state_dir: str, entered, release) -> None:
    from app.tls import _material_lock

    with _material_lock(Path(state_dir)):
        entered.set()
        release.wait(timeout=10)


def test_tls_material_persists_ca_and_trust_code(tmp_path) -> None:
    store = TlsMaterialStore(
        state_dir=tmp_path / "tls",
        identities=("deck.example.test", "192.168.50.10"),
    )

    first = store.ensure()
    second = store.ensure()

    assert first.ca_certificate_path.is_file()
    assert first.certificate_path.is_file()
    assert first.private_key_path.is_file()
    assert (
        first.ca_certificate_path.read_bytes()
        == second.ca_certificate_path.read_bytes()
    )
    assert first.trust_code == second.trust_code
    assert re.fullmatch(r"[A-Z2-7]{4}(?:-[A-Z2-7]{4}){3}", first.trust_code)

    context = ssl.create_default_context(cafile=str(first.ca_certificate_path))
    context.load_cert_chain(
        certfile=str(first.certificate_path),
        keyfile=str(first.private_key_path),
    )


def test_tls_leaf_authority_key_identifier_matches_private_ca(tmp_path) -> None:
    material = TlsMaterialStore(
        state_dir=tmp_path / "tls",
        identities=("localhost",),
    ).ensure()

    ca_certificate = x509.load_pem_x509_certificate(
        material.ca_certificate_path.read_bytes()
    )
    leaf_certificate = x509.load_pem_x509_certificate(
        material.certificate_path.read_bytes()
    )
    ca_subject_key_identifier = ca_certificate.extensions.get_extension_for_class(
        x509.SubjectKeyIdentifier
    ).value
    leaf_authority_key_identifier = leaf_certificate.extensions.get_extension_for_class(
        x509.AuthorityKeyIdentifier
    ).value

    assert (
        leaf_authority_key_identifier.key_identifier == ca_subject_key_identifier.digest
    )


def test_tls_material_renews_leaf_when_server_identities_expand(tmp_path) -> None:
    state_dir = tmp_path / "tls"
    first = TlsMaterialStore(
        state_dir=state_dir,
        identities=("192.168.50.10",),
    ).ensure()
    first_ca = first.ca_certificate_path.read_bytes()
    first_leaf = first.certificate_path.read_bytes()

    expanded = TlsMaterialStore(
        state_dir=state_dir,
        identities=("192.168.50.10", "127.0.0.1"),
    ).ensure()

    assert expanded.ca_certificate_path.read_bytes() == first_ca
    assert expanded.trust_code == first.trust_code
    assert expanded.certificate_path.read_bytes() != first_leaf
    leaf_certificate = x509.load_pem_x509_certificate(
        expanded.certificate_path.read_bytes()
    )
    alternative_names = leaf_certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value
    assert alternative_names.get_values_for_type(x509.IPAddress) == [
        ipaddress.ip_address("192.168.50.10"),
        ipaddress.ip_address("127.0.0.1"),
    ]


def test_tls_material_renews_only_leaf_before_expiry(tmp_path) -> None:
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    store = TlsMaterialStore(
        state_dir=tmp_path / "tls",
        identities=("deck.example.test",),
        clock=lambda: now,
    )

    first = store.ensure()
    first_ca = first.ca_certificate_path.read_bytes()
    first_leaf = first.certificate_path.read_bytes()
    first_key = first.private_key_path.read_bytes()

    now += timedelta(days=61)
    renewed = store.ensure()

    assert renewed.ca_certificate_path.read_bytes() == first_ca
    assert renewed.trust_code == first.trust_code
    assert renewed.certificate_path.read_bytes() != first_leaf
    assert renewed.private_key_path.read_bytes() != first_key


def test_tls_material_rejects_corrupt_leaf_private_key(tmp_path) -> None:
    store = TlsMaterialStore(
        state_dir=tmp_path / "tls",
        identities=("deck.example.test",),
    )
    material = store.ensure()
    material.private_key_path.write_text("not a PEM private key", encoding="ascii")

    with pytest.raises(TlsMaterialError, match="leaf private key"):
        store.ensure()


@pytest.mark.parametrize(
    "identity",
    ("*.example.test", "https://deck.example.test", "deck.example.test:8765"),
)
def test_tls_material_rejects_non_hostname_identities(tmp_path, identity: str) -> None:
    with pytest.raises(ValueError, match="TLS identity"):
        TlsMaterialStore(state_dir=tmp_path / "tls", identities=(identity,))


@pytest.mark.skipif(os.name != "nt", reason="requires Windows file locking")
def test_tls_material_lock_serializes_windows_processes(tmp_path) -> None:
    context = multiprocessing.get_context("spawn")
    state_dir = str(tmp_path / "tls")
    first_entered = context.Event()
    second_entered = context.Event()
    release_first = context.Event()
    first = context.Process(
        target=_hold_tls_material_lock,
        args=(state_dir, first_entered, release_first),
    )
    second = context.Process(
        target=_hold_tls_material_lock,
        args=(state_dir, second_entered, release_first),
    )
    try:
        first.start()
        assert first_entered.wait(timeout=10)
        second.start()
        assert not second_entered.wait(timeout=0.5)
        release_first.set()
        assert second_entered.wait(timeout=10)
    finally:
        release_first.set()
        for process in (first, second):
            if process.pid is None:
                continue
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="requires Windows NTFS ACLs")
def test_tls_private_material_uses_single_user_acl_on_windows(tmp_path) -> None:
    material = TlsMaterialStore(
        state_dir=tmp_path / "tls",
        identities=("localhost",),
    ).ensure()

    icacls = Path(os.environ["SystemRoot"]) / "System32" / "icacls.exe"
    for path in (
        material.ca_certificate_path.parent,
        material.ca_certificate_path.parent / "ca-key.pem",
        material.private_key_path,
    ):
        result = subprocess.run(
            [str(icacls), str(path)],
            check=True,
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
        )
        access_lines = [
            line for line in result.stdout.splitlines() if ":" in line and "(" in line
        ]
        assert len(access_lines) == 1
        assert "(F)" in access_lines[0]
