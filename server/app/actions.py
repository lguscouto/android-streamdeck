from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from app.schemas import Action, HotkeyAction

KEYEVENTF_KEYUP = 0x0002
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


def _virtual_key_for(key: str) -> int:
    virtual_key = _VIRTUAL_KEYS.get(key.upper())
    if virtual_key is None:
        raise ActionExecutionRejected("Hotkey is not supported")
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

    def __init__(self, *, hotkey_adapter: HotkeyAdapter | None = None) -> None:
        self._hotkey_adapter = hotkey_adapter or WindowsHotkeyAdapter()

    def execute(self, action: Action) -> ActionExecutionResult:
        if isinstance(action, HotkeyAction):
            self._hotkey_adapter.execute(action)
            return ActionExecutionResult(status="completed", message="Action completed")
        raise ActionExecutionRejected("Action type is not enabled")


__all__ = [
    "ActionExecutionRejected",
    "ActionExecutionResult",
    "ActionExecutor",
    "ActionRegistry",
    "WindowsHotkeyAdapter",
]
