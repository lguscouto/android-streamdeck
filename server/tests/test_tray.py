from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.config import Settings
from app.tray import TrayApplication, TrayUnavailableError


@dataclass
class FakeController:
    running: bool = False
    starts: int = 0
    stops: int = 0

    @property
    def is_running(self) -> bool:
        return self.running

    def start(self) -> bool:
        if self.running:
            return False
        self.running = True
        self.starts += 1
        return True

    def stop(self) -> bool:
        if not self.running:
            return False
        self.running = False
        self.stops += 1
        return True


class FakeIcon:
    def __init__(self) -> None:
        self.menu_updates = 0
        self.stop_calls = 0

    def update_menu(self) -> None:
        self.menu_updates += 1

    def stop(self) -> None:
        self.stop_calls += 1


@dataclass
class FakeMenuItem:
    text: str
    callback: Any
    enabled: Any = True


class FakeMenu:
    def __init__(self, *items: FakeMenuItem) -> None:
        self.items = items


class FakePystray:
    MenuItem = FakeMenuItem
    Menu = FakeMenu


class FakePairingWindow:
    def __init__(self) -> None:
        self.opens = 0

    def open(self) -> None:
        self.opens += 1


def test_tray_menu_exposes_safe_status_and_start_stop_actions() -> None:
    controller = FakeController()
    tray = TrayApplication(controller)
    menu = tray.build_menu(FakePystray)

    assert menu.items[0].text() == "Servidor: parado"
    assert menu.items[1].text == "Iniciar servidor"
    assert menu.items[2].text == "Parar servidor"
    assert menu.items[2].enabled(FakeMenuItem("ignored", lambda *_: None)) is False

    icon = FakeIcon()
    menu.items[1].callback(icon, menu.items[1])
    assert controller.starts == 1
    assert controller.is_running is True
    assert icon.menu_updates == 1
    assert menu.items[0].text() == "Servidor: iniciado"
    assert menu.items[2].enabled(FakeMenuItem("ignored", lambda *_: None)) is True

    menu.items[2].callback(icon, menu.items[2])
    assert controller.stops == 1
    assert controller.is_running is False
    assert icon.menu_updates == 2


def test_tray_quit_stops_owned_server_before_closing_icon() -> None:
    controller = FakeController(running=True)
    tray = TrayApplication(controller)
    menu = tray.build_menu(FakePystray)
    icon = FakeIcon()

    quit_item = next(item for item in menu.items if item.text == "Sair")
    quit_item.callback(icon, quit_item)

    assert controller.stops == 1
    assert icon.stop_calls == 1


def test_tray_menu_opens_local_pairing_window() -> None:
    controller = FakeController()
    window = FakePairingWindow()
    tray = TrayApplication(controller, pairing_window_factory=lambda: window)
    menu = tray.build_menu(FakePystray)
    icon = FakeIcon()

    pairing_item = next(
        item for item in menu.items if item.text == "Parear dispositivo"
    )
    pairing_item.callback(icon, pairing_item)

    assert window.opens == 1


def test_tray_rejects_pairing_when_bind_has_no_loopback_access() -> None:
    controller = FakeController()
    controller.settings = Settings(
        host="streamdeck.local",
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("streamdeck.local",),
    )
    tray = TrayApplication(controller)

    with pytest.raises(TrayUnavailableError, match="loopback access"):
        tray._default_pairing_window()


def test_tray_uses_configured_private_bind_host_for_pairing(monkeypatch) -> None:
    class CapturingPairingWindow:
        def __init__(self, _controller, *, host, port, ca_certificate_path) -> None:
            self.host = host
            self.port = port
            self.ca_certificate_path = ca_certificate_path

    monkeypatch.delenv("STREAMDECK_PAIRING_SERVER_IP", raising=False)
    monkeypatch.setattr(
        "app.pairing_window.PairingWindow",
        CapturingPairingWindow,
    )
    controller = FakeController()
    controller.settings = Settings(
        host="192.168.100.20",
        port=8765,
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("192.168.100.21", "deck.example.test"),
    )

    window = TrayApplication(controller)._default_pairing_window()

    assert window.host == "192.168.100.20"


def test_tray_ignores_override_for_concrete_bind_host(monkeypatch) -> None:
    class CapturingPairingWindow:
        def __init__(self, _controller, *, host, port, ca_certificate_path) -> None:
            self.host = host
            self.port = port
            self.ca_certificate_path = ca_certificate_path

    monkeypatch.setenv("STREAMDECK_PAIRING_SERVER_IP", "192.168.100.21")
    monkeypatch.setattr(
        "app.pairing_window.PairingWindow",
        CapturingPairingWindow,
    )
    controller = FakeController()
    controller.settings = Settings(
        host="192.168.100.20",
        port=8765,
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("192.168.100.20",),
    )

    window = TrayApplication(controller)._default_pairing_window()

    assert window.host == "192.168.100.20"


def test_tray_uses_private_identity_for_wildcard_emulator_bind(monkeypatch) -> None:
    class CapturingPairingWindow:
        def __init__(self, _controller, *, host, port, ca_certificate_path) -> None:
            self.host = host
            self.port = port
            self.ca_certificate_path = ca_certificate_path

    monkeypatch.delenv("STREAMDECK_PAIRING_SERVER_IP", raising=False)
    monkeypatch.setattr(
        "app.pairing_window.PairingWindow",
        CapturingPairingWindow,
    )
    controller = FakeController()
    controller.settings = Settings(
        host="0.0.0.0",
        port=8765,
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("10.0.2.2", "localhost"),
    )

    window = TrayApplication(controller)._default_pairing_window()

    assert window.host == "10.0.2.2"


def test_tray_uses_san_covered_wildcard_override(monkeypatch) -> None:
    class CapturingPairingWindow:
        def __init__(self, _controller, *, host, port, ca_certificate_path) -> None:
            self.host = host
            self.port = port
            self.ca_certificate_path = ca_certificate_path

    monkeypatch.setenv("STREAMDECK_PAIRING_SERVER_IP", "192.168.100.250")
    monkeypatch.setattr(
        "app.pairing_window.PairingWindow",
        CapturingPairingWindow,
    )
    controller = FakeController()
    controller.settings = Settings(
        host="0.0.0.0",
        port=8765,
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("10.0.2.2", "192.168.100.250"),
    )

    window = TrayApplication(controller)._default_pairing_window()

    assert window.host == "192.168.100.250"


def test_tray_ignores_wildcard_override_outside_tls_san(monkeypatch) -> None:
    class CapturingPairingWindow:
        def __init__(self, _controller, *, host, port, ca_certificate_path) -> None:
            self.host = host
            self.port = port
            self.ca_certificate_path = ca_certificate_path

    monkeypatch.setenv("STREAMDECK_PAIRING_SERVER_IP", "192.168.100.250")
    monkeypatch.setattr(
        "app.pairing_window.PairingWindow",
        CapturingPairingWindow,
    )
    controller = FakeController()
    controller.settings = Settings(
        host="0.0.0.0",
        port=8765,
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("10.0.2.2", "localhost"),
    )

    window = TrayApplication(controller)._default_pairing_window()

    assert window.host == "10.0.2.2"


def test_tray_skips_unspecified_tls_identity_for_wildcard_bind(monkeypatch) -> None:
    class CapturingPairingWindow:
        def __init__(self, _controller, *, host, port, ca_certificate_path) -> None:
            self.host = host
            self.port = port
            self.ca_certificate_path = ca_certificate_path

    monkeypatch.delenv("STREAMDECK_PAIRING_SERVER_IP", raising=False)
    monkeypatch.setattr(
        "app.pairing_window.PairingWindow",
        CapturingPairingWindow,
    )
    controller = FakeController()
    controller.settings = Settings(
        host="0.0.0.0",
        port=8765,
        pairing_code="safe-test-code",
        require_auth=True,
        tls_mode="required",
        tls_identities=("0.0.0.0", "10.0.2.2"),
    )

    window = TrayApplication(controller)._default_pairing_window()

    assert window.host == "10.0.2.2"
