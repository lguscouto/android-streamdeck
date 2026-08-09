from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.repositories.profiles import ProfileNotFoundError, ProfileRepository
from app.schemas import (
    AckMessage,
    AckPayload,
    ErrorMessage,
    ErrorPayload,
    HelloMessage,
    MessageAdapter,
    PingMessage,
    PongMessage,
    PressMessage,
    ProfileChangedMessage,
    ProfileSnapshotMessage,
    WelcomeMessage,
    WelcomePayload,
)

LOGGER = logging.getLogger(__name__)
WEBSOCKET_PREFIX = "/api/v1"
WEBSOCKET_PATH = "/ws"
SERVER_ID = "windows-server"
SERVER_VERSION = "0.1.0"
DEFAULT_HANDSHAKE_TIMEOUT = 5.0
DEFAULT_IDLE_TIMEOUT = 60.0
MAX_CACHED_RESPONSES = 256


@dataclass(slots=True)
class ClientSession:
    client_id: str
    profile_id: str
    responses: dict[str, str] = field(default_factory=dict)


class WebSocketManager:
    """Track connected clients and broadcast validated protocol events."""

    def __init__(
        self,
        repository: ProfileRepository,
        *,
        server_id: str = SERVER_ID,
        server_version: str = SERVER_VERSION,
        handshake_timeout: float = DEFAULT_HANDSHAKE_TIMEOUT,
        idle_timeout: float = DEFAULT_IDLE_TIMEOUT,
    ) -> None:
        self.repository = repository
        self.server_id = server_id
        self.server_version = server_version
        self.handshake_timeout = handshake_timeout
        self.idle_timeout = idle_timeout
        self._sessions: dict[WebSocket, ClientSession] = {}

    @property
    def connection_count(self) -> int:
        return len(self._sessions)

    async def register(self, websocket: WebSocket, session: ClientSession) -> None:
        self._sessions[websocket] = session

    async def unregister(self, websocket: WebSocket) -> None:
        self._sessions.pop(websocket, None)

    async def broadcast_profile_changed(
        self,
        profile_id: str,
        revision: int,
        *,
        reason: str = "updated",
    ) -> None:
        message = ProfileChangedMessage(
            protocol_version=1,
            type="profile_changed",
            payload={
                "profile_id": profile_id,
                "revision": revision,
                "reason": reason,
            },
        ).to_wire_json()
        stale: list[WebSocket] = []
        for websocket, session in tuple(self._sessions.items()):
            if session.profile_id != profile_id:
                continue
            try:
                await websocket.send_text(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.unregister(websocket)


def _error_message(
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    retryable: bool = False,
) -> ErrorMessage:
    payload: dict[str, Any] = {"code": code, "message": message, "retryable": retryable}
    if request_id is not None:
        payload["request_id"] = request_id
    return ErrorMessage(
        protocol_version=1,
        type="error",
        payload=ErrorPayload(**payload),
    )


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    retryable: bool = False,
) -> str:
    wire = _error_message(
        code,
        message,
        request_id=request_id,
        retryable=retryable,
    ).to_wire_json()
    await websocket.send_text(wire)
    return wire


async def _send_invalid_message(websocket: WebSocket) -> None:
    await _send_error(
        websocket,
        "INVALID_MESSAGE",
        "Invalid WebSocket message",
    )


def _parse_message(raw_message: str) -> Any | None:
    try:
        return MessageAdapter.validate_json(raw_message)
    except (ValidationError, ValueError, TypeError):
        return None


async def _load_requested_profile(
    repository: ProfileRepository,
    requested_profile_id: str | None,
) -> Any:
    if requested_profile_id is not None:
        return await run_in_threadpool(repository.get_profile, requested_profile_id)
    profile = await run_in_threadpool(repository.get_active_profile)
    if profile is None:
        raise ProfileNotFoundError("active profile not found")
    return profile


async def _handle_press(
    websocket: WebSocket,
    repository: ProfileRepository,
    session: ClientSession,
    message: PressMessage,
) -> None:
    request_id = message.payload.request_id
    previous = session.responses.get(request_id)
    if previous is not None:
        await websocket.send_text(previous)
        return

    if message.payload.profile_id != session.profile_id:
        wire = await _send_error(
            websocket,
            "PROFILE_NOT_SELECTED",
            "Profile is not selected for this session",
            request_id=request_id,
        )
        _cache_response(session, request_id, wire)
        return

    try:
        profile = await run_in_threadpool(
            repository.get_profile,
            message.payload.profile_id,
        )
    except ProfileNotFoundError:
        wire = await _send_error(
            websocket,
            "PROFILE_NOT_FOUND",
            "Profile not found",
            request_id=request_id,
        )
        _cache_response(session, request_id, wire)
        return
    except Exception:
        wire = await _send_error(
            websocket,
            "INTERNAL_ERROR",
            "Internal server error",
            request_id=request_id,
        )
        _cache_response(session, request_id, wire)
        return

    if profile.revision != message.payload.revision:
        wire = await _send_error(
            websocket,
            "PROFILE_REVISION_CONFLICT",
            "Profile revision conflict",
            request_id=request_id,
            retryable=True,
        )
        _cache_response(session, request_id, wire)
        return

    page = next(
        (
            candidate
            for candidate in profile.pages
            if candidate.id == message.payload.page_id
        ),
        None,
    )
    if page is None:
        wire = await _send_error(
            websocket,
            "PAGE_NOT_FOUND",
            "Page not found",
            request_id=request_id,
        )
        _cache_response(session, request_id, wire)
        return

    button = next(
        (
            candidate
            for candidate in page.buttons
            if candidate.id == message.payload.button_id
        ),
        None,
    )
    if button is None:
        wire = await _send_error(
            websocket,
            "BUTTON_NOT_FOUND",
            "Button not found",
            request_id=request_id,
        )
        _cache_response(session, request_id, wire)
        return

    ack = AckMessage(
        protocol_version=1,
        type="ack",
        payload=AckPayload(
            request_id=request_id,
            status="rejected",
            message="Action execution unavailable in phase 1",
        ),
    ).to_wire_json()
    _cache_response(session, request_id, ack)
    await websocket.send_text(ack)


def _cache_response(session: ClientSession, request_id: str, wire: str) -> None:
    if len(session.responses) >= MAX_CACHED_RESPONSES:
        session.responses.pop(next(iter(session.responses)))
    session.responses[request_id] = wire


async def _serve_websocket(
    websocket: WebSocket,
    repository: ProfileRepository,
    manager: WebSocketManager,
) -> None:
    await websocket.accept()
    session: ClientSession | None = None
    try:
        try:
            raw_hello = await asyncio.wait_for(
                websocket.receive_text(), timeout=manager.handshake_timeout
            )
        except asyncio.TimeoutError:
            await _send_error(
                websocket,
                "HANDSHAKE_TIMEOUT",
                "WebSocket handshake timed out",
                retryable=True,
            )
            await websocket.close(code=1008)
            return
        except WebSocketDisconnect:
            return

        hello = _parse_message(raw_hello)
        if not isinstance(hello, HelloMessage):
            await _send_invalid_message(websocket)
            await websocket.close(code=1002)
            return

        try:
            profile = await _load_requested_profile(
                repository,
                hello.payload.requested_profile_id,
            )
        except ProfileNotFoundError:
            await _send_error(
                websocket,
                "PROFILE_NOT_FOUND",
                "Profile not found",
                retryable=False,
            )
            await websocket.close(code=1008)
            return
        except Exception:
            await _send_error(websocket, "INTERNAL_ERROR", "Internal server error")
            await websocket.close(code=1011)
            return

        session = ClientSession(
            client_id=hello.payload.client_id,
            profile_id=profile.id,
        )
        await manager.register(websocket, session)
        await websocket.send_text(
            WelcomeMessage(
                protocol_version=1,
                type="welcome",
                payload=WelcomePayload(
                    server_id=manager.server_id,
                    server_version=manager.server_version,
                    profile_id=profile.id,
                    revision=profile.revision,
                ),
            ).to_wire_json()
        )
        await websocket.send_text(
            ProfileSnapshotMessage(
                protocol_version=1,
                type="profile_snapshot",
                payload={"profile": profile},
            ).to_wire_json()
        )

        while True:
            try:
                raw_message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=manager.idle_timeout
                )
            except asyncio.TimeoutError:
                await _send_error(
                    websocket,
                    "IDLE_TIMEOUT",
                    "WebSocket session timed out",
                    retryable=True,
                )
                await websocket.close(code=1000)
                return
            except WebSocketDisconnect:
                return

            message = _parse_message(raw_message)
            if isinstance(message, PingMessage):
                await websocket.send_text(
                    PongMessage(
                        protocol_version=1,
                        type="pong",
                        payload={"nonce": message.payload.nonce},
                    ).to_wire_json()
                )
            elif isinstance(message, PressMessage):
                await _handle_press(websocket, repository, session, message)
            else:
                await _send_error(
                    websocket,
                    "UNEXPECTED_MESSAGE",
                    "Message is not valid in this session state",
                )
    except WebSocketDisconnect:
        return
    except Exception:
        LOGGER.warning("WebSocket session terminated unexpectedly")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if session is not None:
            await manager.unregister(websocket)


def create_websocket_router(
    repository: ProfileRepository,
    manager: WebSocketManager | None = None,
) -> APIRouter:
    active_manager = manager or WebSocketManager(repository)
    router = APIRouter(prefix=WEBSOCKET_PREFIX, tags=["websocket"])

    @router.websocket(WEBSOCKET_PATH)
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await _serve_websocket(websocket, repository, active_manager)

    return router


__all__ = ["ClientSession", "WebSocketManager", "create_websocket_router"]
