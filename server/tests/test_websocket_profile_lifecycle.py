from __future__ import annotations

import asyncio
import json
from typing import Any

from app.websocket import ClientSession, WebSocketManager


class RecordingWebSocket:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_text(self, message: str) -> None:
        self.messages.append(message)


def test_deleted_profile_event_is_not_deduplicated_and_allows_recreation() -> None:
    """A deletion must reach the connected profile session even at its last revision."""

    async def exercise() -> list[dict[str, Any]]:
        manager = WebSocketManager(repository=object())
        websocket = RecordingWebSocket()
        await manager.register(
            websocket,
            ClientSession(client_id="android", profile_id="work", ready=True),
        )
        await manager.broadcast_profile_changed("work", 2, reason="updated")
        await manager.broadcast_profile_changed("work", 2, reason="deleted")
        await manager.broadcast_profile_changed("work", 1, reason="created")
        return [json.loads(message) for message in websocket.messages]

    messages = asyncio.run(exercise())

    assert [message["payload"] for message in messages] == [
        {"profile_id": "work", "revision": 2, "reason": "updated"},
        {"profile_id": "work", "revision": 2, "reason": "deleted"},
        {"profile_id": "work", "revision": 1, "reason": "created"},
    ]
