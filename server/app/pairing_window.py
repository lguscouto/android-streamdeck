from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.pairing_session import PairingSessionPresentation, normalize_pairing_code

_SESSION_ID_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
)


class PairingWindowError(RuntimeError):
    """Raised for safe, user-facing local pairing window failures."""


@dataclass(frozen=True, slots=True)
class _WindowPresentation:
    session_id: str
    pairing_code: str
    expires_at: str
    server_ip: str
    port: int
    qr_uri: str


class PairingWindow:
    """Show the one-time local pairing secret and QR without writing it to disk."""

    def __init__(
        self,
        controller: Any,
        *,
        host: str,
        port: int,
        ca_certificate_path: Path,
        client_factory: Callable[..., Any] = httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        monotonic_values: Iterator[float] | None = None,
        health_timeout_seconds: float = 15.0,
    ) -> None:
        self.controller = controller
        self.host = _require_private_ipv4(host)
        if not 1 <= port <= 65535:
            raise ValueError("pairing window port must be between 1 and 65535")
        if health_timeout_seconds <= 0:
            raise ValueError("pairing window timeout must be positive")
        self.port = port
        self.ca_certificate_path = Path(ca_certificate_path)
        self._client_factory = client_factory
        self._sleep = sleep
        self._monotonic = (
            (lambda: next(monotonic_values))
            if monotonic_values is not None
            else monotonic
        )
        self._health_timeout_seconds = health_timeout_seconds
        self._presentation: PairingSessionPresentation | None = None

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"

    def fetch_session(self) -> PairingSessionPresentation:
        """Start child if needed, wait for health, and claim a display session."""
        if not self.controller.is_running:
            self.controller.start()
        with self._client_factory(
            verify=str(self.ca_certificate_path),
            timeout=2.0,
        ) as client:
            self._wait_for_health(client)
            response = client.post(
                f"{self.base_url}/api/v1/local/pairing-session",
                headers={"X-StreamDeck-Admin-Code": self.controller.admin_code},
            )
            if response.status_code != 200:
                raise PairingWindowError("local pairing session could not be created")
            presentation = self._parse_presentation(response.json())
        self._presentation = presentation
        return presentation

    def open(self) -> None:
        """Open the native Windows window; the optional GUI is imported lazily."""
        presentation = self.fetch_session()
        try:
            import tkinter as tk
            from tkinter import messagebox
        except ImportError as exc:
            self._presentation = None
            raise PairingWindowError("Windows pairing window is unavailable") from exc

        root = tk.Tk()
        root.title("Parear Android Stream Deck")
        root.resizable(False, False)
        frame = tk.Frame(root, padx=20, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Parear dispositivo", font=("Segoe UI", 16, "bold")).pack()
        ip_label = tk.Label(frame, anchor="w")
        ip_label.pack(fill="x", pady=(12, 0))
        password_label = tk.Label(frame, anchor="w", font=("Consolas", 14, "bold"))
        password_label.pack(fill="x", pady=(4, 0))
        expiry_label = tk.Label(frame, anchor="w")
        expiry_label.pack(fill="x", pady=(4, 8))
        qr_label = tk.Label(frame)
        qr_label.pack(pady=8)
        image_holder: dict[str, Any] = {}
        current_presentation: dict[str, PairingSessionPresentation] = {
            "value": presentation,
        }

        def render(current: PairingSessionPresentation) -> None:
            ip_label.configure(text=f"Endereço: {current.server_ip}:{current.port}")
            password_label.configure(text=f"Senha temporária: {current.pairing_code}")
            expiry_label.configure(text=f"Válida até: {current.expires_at}")
            image = self.qr_image(current.qr_uri)
            try:
                from PIL import ImageTk

                photo = ImageTk.PhotoImage(image)
            except ImportError as exc:
                raise PairingWindowError("QR image support is unavailable") from exc
            image_holder["photo"] = photo
            qr_label.configure(image=photo)

        def copy_value(value: str) -> None:
            root.clipboard_clear()
            root.clipboard_append(value)
            root.update()

        def refresh() -> None:
            try:
                refreshed = self.fetch_session()
                current_presentation["value"] = refreshed
                render(refreshed)
            except PairingWindowError:
                messagebox.showerror(
                    "Pareamento", "Não foi possível gerar uma nova senha."
                )

        def close() -> None:
            root.clipboard_clear()
            root.update()
            self._presentation = None
            current_presentation.clear()
            image_holder.clear()
            root.destroy()

        buttons = tk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        tk.Button(
            buttons,
            text="Copiar IP",
            command=lambda: copy_value(current_presentation["value"].server_ip),
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(
            buttons,
            text="Copiar senha",
            command=lambda: copy_value(current_presentation["value"].pairing_code),
        ).pack(side="left", expand=True, fill="x", padx=4)
        tk.Button(buttons, text="Gerar nova senha", command=refresh).pack(
            side="left", expand=True, fill="x", padx=(4, 0)
        )
        root.protocol("WM_DELETE_WINDOW", close)
        render(presentation)
        root.mainloop()
        self._presentation = None

    @staticmethod
    def qr_image(qr_uri: str) -> Any:
        """Generate the QR image in memory; no payload file is created."""
        try:
            import qrcode
        except ImportError as exc:
            raise PairingWindowError("QR support is unavailable") from exc
        return qrcode.make(qr_uri)

    def _wait_for_health(self, client: Any) -> None:
        deadline = self._monotonic() + self._health_timeout_seconds
        while True:
            try:
                response = client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if self._monotonic() >= deadline:
                raise PairingWindowError("local server did not become ready")
            self._sleep(0.2)

    @staticmethod
    def _parse_presentation(payload: Any) -> PairingSessionPresentation:
        if not isinstance(payload, dict):
            raise PairingWindowError("local pairing response is invalid")
        required = {
            "session_id",
            "pairing_code",
            "expires_at",
            "server_ip",
            "port",
            "qr_uri",
        }
        if set(payload) != required:
            raise PairingWindowError("local pairing response is invalid")
        session_id = payload["session_id"]
        if (
            not isinstance(session_id, str)
            or not 16 <= len(session_id) <= 64
            or any(character not in _SESSION_ID_ALPHABET for character in session_id)
        ):
            raise PairingWindowError("local pairing response is invalid")
        try:
            pairing_code = normalize_pairing_code(payload["pairing_code"])
            server_ip = _require_private_ipv4(payload["server_ip"])
            port = int(payload["port"])
        except (TypeError, ValueError):
            raise PairingWindowError("local pairing response is invalid") from None
        if not 1 <= port <= 65535:
            raise PairingWindowError("local pairing response is invalid")
        if not all(isinstance(payload[key], str) for key in ("expires_at", "qr_uri")):
            raise PairingWindowError("local pairing response is invalid")
        return PairingSessionPresentation(
            session_id=session_id,
            pairing_code=pairing_code,
            expires_at=payload["expires_at"],
            server_ip=server_ip,
            port=port,
            qr_uri=payload["qr_uri"],
        )


def _require_private_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("pairing window requires a private IPv4 address") from exc
    if address.version != 4 or not address.is_private or address.is_loopback:
        raise ValueError("pairing window requires a private IPv4 address")
    return str(address)


__all__ = ["PairingWindow", "PairingWindowError"]
