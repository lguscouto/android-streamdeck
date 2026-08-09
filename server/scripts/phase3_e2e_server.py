"""Temporary controlled server for the Android Phase 3 instrumented smoke.

The production server uses WindowsHotkeyAdapter. This runner injects a recorder so
an Android-to-WebSocket smoke can prove the complete authenticated route without
sending a real operating-system hotkey to the user's active desktop session.
"""

from __future__ import annotations

import logging

import uvicorn

from app.actions import ActionRegistry, HotkeyAdapter
from app.config import Settings
from app.main import create_app
from app.schemas import HotkeyAction

LOGGER = logging.getLogger(__name__)


class RecordingHotkeyAdapter(HotkeyAdapter):
    def execute(self, action: HotkeyAction) -> None:
        LOGGER.warning(
            "PHASE3_E2E_RECORDED_HOTKEY modifiers=%s key=%s",
            ",".join(action.modifiers),
            action.key,
        )


def main() -> None:
    settings = Settings.from_env()
    application = create_app(
        settings,
        action_executor=ActionRegistry(hotkey_adapter=RecordingHotkeyAdapter()),
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
