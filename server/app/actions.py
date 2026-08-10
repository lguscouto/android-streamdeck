from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from app.schemas import (
    Action,
    HotkeyAction,
    KeyAction,
    MediaAction,
    TextAction,
    UrlAction,
)

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
_MODIFIER_VIRTUAL_KEYS = {
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
}
_NAMED_VIRTUAL_KEYS = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "END": 0x23,
    "HOME": 0x24,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
}
_ALPHANUMERIC_VIRTUAL_KEYS = {
    character: ord(character) for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
}
_FUNCTION_VIRTUAL_KEYS = {f"F{number}": 0x6F + number for number in range(1, 25)}
_VIRTUAL_KEYS = {
    **_ALPHANUMERIC_VIRTUAL_KEYS,
    **_FUNCTION_VIRTUAL_KEYS,
    **_NAMED_VIRTUAL_KEYS,
}
_MEDIA_VIRTUAL_KEYS = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    "mute": 0xAD,
}


@dataclass(frozen=True, slots=True)
class ActionExecutionResult:
    status: Literal["completed", "rejected"]
    message: str


class ActionExecutionRejected(RuntimeError):
    """A safe, user-facing reason why a closed action was not executed."""

    def __init__(self, public_message: str) -> None:
        super().__init__(public_message)
        self.public_message = public_message


class HotkeyAdapter(Protocol):
    def execute(self, action: HotkeyAction) -> None: ...


class KeyAdapter(Protocol):
    def execute(self, action: KeyAction) -> None: ...


class MediaAdapter(Protocol):
    def execute(self, action: MediaAction) -> None: ...


class TextAdapter(Protocol):
    def execute(self, action: TextAction) -> None: ...


class UrlAdapter(Protocol):
    def execute(self, action: UrlAction) -> None: ...


class ActionExecutor(Protocol):
    def execute(self, action: Action) -> ActionExecutionResult: ...


class WindowsHotkeyAdapter:
    """Send a closed, validated virtual-key sequence without invoking a shell."""

    def __init__(self, *, emit_key: Callable[[int, bool], None] | None = None) -> None:
        self._emit_key = emit_key or _emit_windows_key

    def execute(self, action: HotkeyAction) -> None:
        modifier_keys = tuple(
            _MODIFIER_VIRTUAL_KEYS[modifier] for modifier in action.modifiers
        )
        virtual_key = _virtual_key_for(action.key)
        pressed_modifiers: list[int] = []
        primary_pressed = False
        try:
            for modifier_key in modifier_keys:
                self._emit_key(modifier_key, False)
                pressed_modifiers.append(modifier_key)
            self._emit_key(virtual_key, False)
            primary_pressed = True
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc
        finally:
            if primary_pressed:
                _release_key_safely(self._emit_key, virtual_key)
            for modifier_key in reversed(pressed_modifiers):
                _release_key_safely(self._emit_key, modifier_key)


class WindowsKeyAdapter:
    """Send one closed, validated virtual-key tap without modifiers."""

    def __init__(self, *, emit_key: Callable[[int, bool], None] | None = None) -> None:
        self._emit_key = emit_key or _emit_windows_key

    def execute(self, action: KeyAction) -> None:
        virtual_key = _key_virtual_key_for(action.key)
        primary_pressed = False
        try:
            self._emit_key(virtual_key, False)
            primary_pressed = True
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc
        finally:
            if primary_pressed:
                _release_key_safely(self._emit_key, virtual_key)


class WindowsMediaAdapter:
    """Send one closed, validated media-key tap without arbitrary payloads."""

    def __init__(self, *, emit_key: Callable[[int, bool], None] | None = None) -> None:
        self._emit_key = emit_key or _emit_windows_key

    def execute(self, action: MediaAction) -> None:
        virtual_key = _media_virtual_key_for(action.command)
        primary_pressed = False
        try:
            self._emit_key(virtual_key, False)
            primary_pressed = True
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc
        finally:
            if primary_pressed:
                _release_key_safely(self._emit_key, virtual_key)


class WindowsTextAdapter:
    """Type validated text through Win32 Unicode input, without a shell."""

    def __init__(self, *, emit_text: Callable[[str], None] | None = None) -> None:
        self._emit_text = emit_text or _emit_windows_text

    def execute(self, action: TextAction) -> None:
        try:
            self._emit_text(action.text)
        except ActionExecutionRejected:
            raise
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc


class WindowsUrlAdapter:
    """Open a validated HTTPS URL through the Windows default browser."""

    def __init__(self, *, open_url: Callable[[str], None] | None = None) -> None:
        self._open_url = open_url or _open_windows_url

    def execute(self, action: UrlAction) -> None:
        try:
            self._open_url(action.url)
        except ActionExecutionRejected:
            raise
        except Exception as exc:
            raise ActionExecutionRejected("Action could not be completed") from exc


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [
        ("ki", _KeyboardInput),
        (
            "_reserved",
            ctypes.c_ubyte * (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 24),
        ),
    ]


class _Input(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _InputUnion),
    ]


def _emit_windows_text(text: str) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("Text execution requires Windows")
    encoded_text = text.encode("utf-16-le", errors="surrogatepass")
    code_units = [
        int.from_bytes(encoded_text[index : index + 2], byteorder="little")
        for index in range(0, len(encoded_text), 2)
    ]
    inputs = (_Input * (len(code_units) * 2))()
    for index, code_unit in enumerate(code_units):
        down = inputs[index * 2]
        down.type = INPUT_KEYBOARD
        down.union.ki = _KeyboardInput(
            wVk=0,
            wScan=code_unit,
            dwFlags=KEYEVENTF_UNICODE,
            time=0,
            dwExtraInfo=None,
        )
        up = inputs[index * 2 + 1]
        up.type = INPUT_KEYBOARD
        up.union.ki = _KeyboardInput(
            wVk=0,
            wScan=code_unit,
            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
            time=0,
            dwExtraInfo=None,
        )
    sent = ctypes.windll.user32.SendInput(
        len(inputs),
        ctypes.byref(inputs),
        ctypes.sizeof(_Input),
    )
    if sent != len(inputs):
        raise ActionExecutionRejected("Text input was not accepted")


def _open_windows_url(url: str) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("URL execution requires Windows")
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "open",
        url,
        None,
        None,
        1,
    )
    if result <= 32:
        raise ActionExecutionRejected("URL could not be opened")


def _virtual_key_for(key: str) -> int:
    virtual_key = _VIRTUAL_KEYS.get(key.upper())
    if virtual_key is None:
        raise ActionExecutionRejected("Hotkey is not supported")
    return virtual_key


def _key_virtual_key_for(key: str) -> int:
    virtual_key = _VIRTUAL_KEYS.get(key.upper())
    if virtual_key is None:
        raise ActionExecutionRejected("Key is not supported")
    return virtual_key


def _media_virtual_key_for(command: str) -> int:
    virtual_key = _MEDIA_VIRTUAL_KEYS.get(command)
    if virtual_key is None:
        raise ActionExecutionRejected("Media command is not supported")
    return virtual_key


def _emit_windows_key(virtual_key: int, key_up: bool) -> None:
    if sys.platform != "win32":
        raise ActionExecutionRejected("Hotkey execution requires Windows")
    flags = KEYEVENTF_KEYUP if key_up else 0
    ctypes.windll.user32.keybd_event(virtual_key, 0, flags, 0)


def _release_key_safely(
    emit_key: Callable[[int, bool], None], virtual_key: int
) -> None:
    try:
        emit_key(virtual_key, True)
    except Exception:
        # A best-effort release cannot expose adapter internals to the client.
        return


class ActionRegistry:
    """Registry of explicitly enabled action types for this server version."""

    def __init__(
        self,
        *,
        hotkey_adapter: HotkeyAdapter | None = None,
        key_adapter: KeyAdapter | None = None,
        media_adapter: MediaAdapter | None = None,
        text_adapter: TextAdapter | None = None,
        url_adapter: UrlAdapter | None = None,
    ) -> None:
        self._hotkey_adapter = hotkey_adapter or WindowsHotkeyAdapter()
        self._key_adapter = key_adapter or WindowsKeyAdapter()
        self._media_adapter = media_adapter or WindowsMediaAdapter()
        self._text_adapter = text_adapter or WindowsTextAdapter()
        self._url_adapter = url_adapter or WindowsUrlAdapter()

    def execute(self, action: Action) -> ActionExecutionResult:
        if isinstance(action, HotkeyAction):
            self._hotkey_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, KeyAction):
            self._key_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, MediaAction):
            self._media_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, TextAction):
            self._text_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        if isinstance(action, UrlAction):
            self._url_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        raise ActionExecutionRejected("Action type is not enabled")


__all__ = [
    "ActionExecutionRejected",
    "ActionExecutionResult",
    "ActionExecutor",
    "ActionRegistry",
    "KeyAdapter",
    "MediaAdapter",
    "TextAdapter",
    "UrlAdapter",
    "WindowsHotkeyAdapter",
    "WindowsKeyAdapter",
    "WindowsMediaAdapter",
    "WindowsTextAdapter",
    "WindowsUrlAdapter",
]
