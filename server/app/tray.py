from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import Settings, resolve_pairing_server_ip
from app.service_control import ServerProcessController


class TrayUnavailableError(RuntimeError):
    """Raised when the optional Windows tray dependency is not installed."""


class TrayApplication:
    """Small system-tray facade around the owned server process."""

    def __init__(
        self,
        controller: ServerProcessController,
        *,
        icon_name: str = "android-streamdeck",
        title: str = "Android Stream Deck",
        pairing_window_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.controller = controller
        self.icon_name = icon_name
        self.title = title
        self._pairing_window_factory = (
            pairing_window_factory or self._default_pairing_window
        )

    def build_menu(self, pystray_module: Any) -> Any:
        menu_item = pystray_module.MenuItem
        menu = pystray_module.Menu
        return menu(
            menu_item(self._status_text, lambda _icon, _item: None, enabled=False),
            menu_item(
                "Iniciar servidor",
                self._start_server,
                enabled=lambda _item: not self.controller.is_running,
            ),
            menu_item(
                "Parar servidor",
                self._stop_server,
                enabled=lambda _item: self.controller.is_running,
            ),
            menu_item("Parear dispositivo", self._pair_device),
            menu_item("Sair", self._quit),
        )

    def run(self) -> None:
        pystray_module = self._load_pystray()
        icon = pystray_module.Icon(
            self.icon_name,
            self._create_image(),
            self.title,
            self.build_menu(pystray_module),
        )
        icon.run()

    def _status_text(self, _item: Any = None) -> str:
        state = "iniciado" if self.controller.is_running else "parado"
        return f"Servidor: {state}"

    def _start_server(self, icon: Any, _item: Any) -> None:
        try:
            self.controller.start()
        except Exception:
            self._notify(icon, "Não foi possível iniciar o servidor")
        finally:
            icon.update_menu()

    def _stop_server(self, icon: Any, _item: Any) -> None:
        try:
            self.controller.stop()
        except Exception:
            self._notify(icon, "Não foi possível parar o servidor")
        finally:
            icon.update_menu()

    def _pair_device(self, icon: Any, _item: Any) -> None:
        try:
            self._pairing_window_factory().open()
        except Exception:
            self._notify(icon, "Não foi possível abrir o pareamento")

    def _quit(self, icon: Any, _item: Any) -> None:
        try:
            self.controller.stop()
        finally:
            icon.stop()

    @staticmethod
    def _notify(icon: Any, message: str) -> None:
        notify = getattr(icon, "notify", None)
        if callable(notify):
            notify(message, "Android Stream Deck")

    @staticmethod
    def _load_pystray() -> Any:
        try:
            import pystray
        except ImportError as exc:
            raise TrayUnavailableError(
                "tray support is unavailable; install the Windows bundle"
            ) from exc
        return pystray

    @staticmethod
    def _create_image() -> Any:
        try:
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise TrayUnavailableError(
                "tray icon support is unavailable; install the Windows bundle"
            ) from exc

        image = Image.new("RGB", (64, 64), "#172033")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=10, fill="#2f80ed")
        draw.rectangle((18, 20, 26, 28), fill="#ffffff")
        draw.rectangle((38, 20, 46, 28), fill="#ffffff")
        draw.rectangle((18, 36, 46, 42), fill="#ffffff")
        return image

    def _default_pairing_window(self) -> Any:
        from app.pairing_window import PairingWindow

        settings = self.controller.settings
        if not settings.local_pairing_supported:
            raise TrayUnavailableError(
                "local pairing requires a bind with loopback access"
            )
        host = resolve_pairing_server_ip(settings)
        if host is None:
            raise TrayUnavailableError("private pairing address is unavailable")
        return PairingWindow(
            self.controller,
            host=host,
            port=settings.port,
            ca_certificate_path=settings.tls_state_dir / "ca-cert.pem",
        )


def main() -> None:
    settings = Settings.from_env()
    controller = ServerProcessController(settings)
    TrayApplication(controller).run()


if __name__ == "__main__":
    main()


__all__ = ["TrayApplication", "TrayUnavailableError", "main"]
