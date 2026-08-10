from __future__ import annotations

import pytest

from app.actions import (
    ActionExecutionRejected,
    ActionRegistry,
    WindowsHotkeyAdapter,
    WindowsKeyAdapter,
    WindowsMediaAdapter,
    WindowsTextAdapter,
    WindowsUrlAdapter,
)
from app.schemas import (
    ApplicationAction,
    HotkeyAction,
    KeyAction,
    MediaAction,
    TextAction,
    UrlAction,
)


class RecordingKeyEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[int, bool]] = []

    def __call__(self, virtual_key: int, key_up: bool) -> None:
        self.events.append((virtual_key, key_up))


def test_windows_key_adapter_emits_one_allowed_key_without_modifier() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsKeyAdapter(emit_key=emitter)

    adapter.execute(KeyAction(type="key", key="A"))

    assert emitter.events == [
        (0x41, False),  # A down
        (0x41, True),  # A up
    ]


def test_windows_media_adapter_emits_one_allowed_media_command() -> None:
    emitter = RecordingKeyEmitter()
    adapter = WindowsMediaAdapter(emit_key=emitter)

    adapter.execute(MediaAction(type="media", command="play_pause"))

    assert emitter.events == [
        (0xB3, False),  # Play/pause down
        (0xB3, True),  # Play/pause up
    ]


def test_windows_text_adapter_emits_only_validated_text() -> None:
    emitted: list[str] = []
    adapter = WindowsTextAdapter(emit_text=emitted.append)

    adapter.execute(TextAction(type="text", text="Olá Stream Deck"))

    assert emitted == ["Olá Stream Deck"]


def test_windows_url_adapter_opens_only_validated_https_url() -> None:
    opened: list[str] = []
    adapter = WindowsUrlAdapter(open_url=opened.append)

    adapter.execute(UrlAction(type="url", url="https://example.com/docs"))

    assert opened == ["https://example.com/docs"]


def test_action_registry_executes_text_and_url_adapters() -> None:
    emitted: list[str] = []
    opened: list[str] = []
    registry = ActionRegistry(
        text_adapter=WindowsTextAdapter(emit_text=emitted.append),
        url_adapter=WindowsUrlAdapter(open_url=opened.append),
    )

    text_result = registry.execute(TextAction(type="text", text="hello"))
    url_result = registry.execute(UrlAction(type="url", url="https://example.com"))

    assert text_result.status == "completed"
    assert url_result.status == "completed"
    assert emitted == ["hello"]
    assert opened == ["https://example.com"]


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
        (0x53, True),  # S up
        (0x10, True),  # Shift up
        (0x11, True),  # Ctrl up
    ]


def test_action_registry_executes_only_hotkey_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(hotkey_adapter=WindowsHotkeyAdapter(emit_key=emitter))

    result = registry.execute(HotkeyAction(type="hotkey", modifiers=["ctrl"], key="S"))

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0x11, False),
        (0x53, False),
        (0x53, True),
        (0x11, True),
    ]


def test_action_registry_executes_key_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(key_adapter=WindowsKeyAdapter(emit_key=emitter))

    result = registry.execute(KeyAction(type="key", key="ENTER"))

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0x0D, False),
        (0x0D, True),
    ]


def test_action_registry_executes_media_adapter() -> None:
    emitter = RecordingKeyEmitter()
    registry = ActionRegistry(media_adapter=WindowsMediaAdapter(emit_key=emitter))

    result = registry.execute(MediaAction(type="media", command="mute"))

    assert result.status == "completed"
    assert result.message == "Action completed"
    assert emitter.events == [
        (0xAD, False),
        (0xAD, True),
    ]


def test_action_registry_rejects_action_without_an_explicit_adapter() -> None:
    registry = ActionRegistry()

    with pytest.raises(ActionExecutionRejected) as error:
        registry.execute(ApplicationAction(type="application", app_id="not-enabled"))

    assert error.value.public_message == "Action type is not enabled"


def test_windows_hotkey_adapter_rejects_key_outside_closed_virtual_key_map() -> None:
    adapter = WindowsHotkeyAdapter(emit_key=RecordingKeyEmitter())

    with pytest.raises(ActionExecutionRejected) as error:
        adapter.execute(
            HotkeyAction(type="hotkey", modifiers=["ctrl"], key="NotConfigured")
        )

    assert error.value.public_message == "Hotkey is not supported"
