"""Temporary controlled server for the Android Phase 4 instrumented smoke.

The production server uses Windows adapters. This runner injects recorders for
all currently enabled action types so the Android-to-HTTP/WebSocket smoke proves
the complete authenticated route without sending real input to the desktop.
"""

from __future__ import annotations

import logging

import uvicorn

from app.actions import (
    ActionRegistry,
    HotkeyAdapter,
    KeyAdapter,
    MediaAdapter,
    TextAdapter,
    UrlAdapter,
)
from app.config import Settings
from app.main import create_app
from app.schemas import HotkeyAction, KeyAction, MediaAction, TextAction, UrlAction

LOGGER = logging.getLogger(__name__)


class RecordingHotkeyAdapter(HotkeyAdapter):
    def execute(self, action: HotkeyAction) -> None:
        LOGGER.warning(
            "PHASE4_E2E_RECORDED_HOTKEY modifiers=%s key=%s",
            ",".join(action.modifiers),
            action.key,
        )


class RecordingKeyAdapter(KeyAdapter):
    def execute(self, action: KeyAction) -> None:
        LOGGER.warning("PHASE4_E2E_RECORDED_KEY key=%s", action.key)


class RecordingMediaAdapter(MediaAdapter):
    def execute(self, action: MediaAction) -> None:
        LOGGER.warning("PHASE4_E2E_RECORDED_MEDIA command=%s", action.command)


class RecordingTextAdapter(TextAdapter):
    def execute(self, action: TextAction) -> None:
        LOGGER.warning("PHASE4_E2E_RECORDED_TEXT length=%s", len(action.text))


class RecordingUrlAdapter(UrlAdapter):
    def execute(self, action: UrlAction) -> None:
        LOGGER.warning("PHASE4_E2E_RECORDED_URL host=%s", action.url.split("/", 3)[2])


def main() -> None:
    settings = Settings.from_env()
    application = create_app(
        settings,
        action_executor=ActionRegistry(
            hotkey_adapter=RecordingHotkeyAdapter(),
            key_adapter=RecordingKeyAdapter(),
            media_adapter=RecordingMediaAdapter(),
            text_adapter=RecordingTextAdapter(),
            url_adapter=RecordingUrlAdapter(),
        ),
    )
    uvicorn.run(
        application,
        host=settings.host,
        port=settings.port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
