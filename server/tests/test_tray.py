from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.tray import TrayApplication


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
