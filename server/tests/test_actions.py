from __future__ import annotations

import pytest

from app.actions import (
    ActionExecutionRejected,
    ActionRegistry,
    WindowsHotkeyAdapter,
)
from app.schemas import HotkeyAction, MediaAction


class RecordingKeyEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[int, bool]] = []

    def __call__(self, virtual_key: int, key_up: bool) -> None:
        self.events.append((virtual_key, key_up))


def test_windows_hotkey_adapter_emits_closed_modifier_and_key_sequence() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsHotkeyAdapter(emit_key=emitter)

    adapter.execute(
        HotkeyAction(
            type="hotkey",
            modifiers=["ctrl", "shift"],
            key="S",
        )
    )

    assert emitter.events == [
        (0x11, False),  # Ctrl down
        (0x10, False),  # Shift down
        (0x53, False),  # S down
        (0x53, True),   # S up
        (0x10, True),   # Shift up
        (0x11, True),   # Ctrl up
    ]


def test_action_registry_executes_only_hotkey_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(hotkey_adapter=WindowsHotkeyAdapter(emit_key=emitter))

    result = registry.execute(
        HotkeyAction(type="hotkey", modifiers=["ctrl"], key="S")
    )

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0x11, False),
        (0x53, False),
        (0x53, True),
        (0x11, True),
    ]


def test_action_registry_rejects_action_without_an_explicit_adapter() -> None:
    registry = ActionRegistry()

    with pytest.raises(ActionExecutionRejected) as error:
        registry.execute(MediaAction(type="media", command="play_pause"))

    assert error.value.public_message == "Action type is not enabled"


def test_windows_hotkey_adapter_rejects_key_outside_closed_virtual_key_map() -> None:
    adapter = WindowsHotkeyAdapter(emit_key=RecordingKeyEmitter())

    with pytest.raises(ActionExecutionRejected) as error:
        adapter.execute(
            HotkeyAction(type="hotkey", modifiers=["ctrl"], key="NotConfigured")
        )

    assert error.value.public_message == "Hotkey is not supported"
