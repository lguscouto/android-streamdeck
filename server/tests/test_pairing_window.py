from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.pairing_window import PairingWindow


class FakeController:
    is_running = False
    admin_code = "admin-test-only"

    def start(self) -> bool:
        return True


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(
        self,
        payload: dict[str, Any],
        calls: list[tuple[str, str, dict[str, str] | None]],
    ) -> None:
        self.payload = payload
        self.calls = calls

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(self, url: str, **_kwargs: Any) -> FakeResponse:
        self.calls.append(("GET", url, None))
        return FakeResponse({"status": "ok"})

    def post(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        self.calls.append(("POST", url, headers))
        return FakeResponse(self.payload)


def test_pairing_window_fetches_local_session_through_loopback_tls_endpoint(
    tmp_path: Path,
) -> None:
    payload = {
        "session_id": "a" * 22,
        "pairing_code": "A" * 26,
        "expires_at": "2026-08-11T12:00:00Z",
        "server_ip": "192.168.100.20",
        "port": 8765,
        "qr_uri": "streamdeck://pair/v1?ip=192.168.100.20&port=8765&session="
        + "a" * 22
        + "&secret="
        + "A" * 26,
    }
    calls: list[tuple[str, str, dict[str, str] | None]] = []
    client = FakeClient(payload, calls)
    ca_certificate_path = tmp_path / "ca-cert.pem"
    ca_certificate_path.write_text("synthetic CA", encoding="ascii")
    window = PairingWindow(
        FakeController(),
        host="192.168.100.20",
        port=8765,
        ca_certificate_path=ca_certificate_path,
        client_factory=lambda **_kwargs: client,
        sleep=lambda _seconds: None,
        monotonic_values=iter([0.0, 0.1]),
    )

    presentation = window.fetch_session()

    assert presentation.server_ip == "192.168.100.20"
    assert presentation.pairing_code == "A" * 26
    assert calls == [
        ("GET", "https://127.0.0.1:8765/health", None),
        (
            "POST",
            "https://127.0.0.1:8765/api/v1/local/pairing-session",
            {"X-StreamDeck-Admin-Code": "admin-test-only"},
        ),
    ]


def test_pairing_window_waits_for_ca_created_by_starting_server(tmp_path: Path) -> None:
    ca_certificate_path = tmp_path / "ca-cert.pem"
    payload = {
        "session_id": "a" * 22,
        "pairing_code": "A" * 26,
        "expires_at": "2026-08-11T12:00:00Z",
        "server_ip": "192.168.100.20",
        "port": 8765,
        "qr_uri": "streamdeck://pair/v1?ip=192.168.100.20&port=8765&session="
        + "a" * 22
        + "&secret="
        + "A" * 26,
    }
    client_created: list[bool] = []

    def client_factory(**_kwargs: Any) -> FakeClient:
        client_created.append(ca_certificate_path.is_file())
        if not ca_certificate_path.is_file():
            raise FileNotFoundError(ca_certificate_path)
        return FakeClient(payload, [])

    def create_ca(_seconds: float) -> None:
        ca_certificate_path.write_text("synthetic CA", encoding="ascii")

    window = PairingWindow(
        FakeController(),
        host="192.168.100.20",
        port=8765,
        ca_certificate_path=ca_certificate_path,
        client_factory=client_factory,
        sleep=create_ca,
        monotonic_values=iter([0.0, 0.1, 0.2]),
    )

    presentation = window.fetch_session()

    assert client_created == [True]
    assert presentation.server_ip == "192.168.100.20"


def test_pairing_window_qr_image_is_created_in_memory(monkeypatch: Any) -> None:
    class FakeQr:
        def make(self, value: str) -> str:
            return value

    monkeypatch.setitem(__import__("sys").modules, "qrcode", FakeQr())

    image = PairingWindow.qr_image("streamdeck://pair/v1?session=redacted")

    assert image == "streamdeck://pair/v1?session=redacted"


def test_pairing_window_rejects_unspecified_host(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="private IPv4"):
        PairingWindow(
            FakeController(),
            host="0.0.0.0",
            port=8765,
            ca_certificate_path=tmp_path / "ca-cert.pem",
        )
