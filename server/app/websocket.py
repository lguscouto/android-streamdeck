from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.pairing import PairingError, PairingService
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
DEFAULT_SEND_TIMEOUT = 1.0
MAX_CONNECTIONS = 32
MAX_FRAME_BYTES = 256 * 1024
MAX_CACHED_RESPONSES = 256


@dataclass(slots=True)
class ClientSession:
    client_id: str
    profile_id: str
    responses: dict[str, str] = field(default_factory=dict)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ready: bool = False
    pending_messages: list[str] = field(default_factory=list)


async def _send_session_text(
    websocket: WebSocket,
    session: ClientSession,
    message: str,
) -> None:
    async with session.send_lock:
        await websocket.send_text(message)


async def _close_handshake_timeout(websocket: WebSocket) -> None:
    await _send_error(
        websocket,
        "HANDSHAKE_TIMEOUT",
        "WebSocket handshake timed out",
        retryable=True,
    )
    await websocket.close(code=1008)


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
        send_timeout: float = DEFAULT_SEND_TIMEOUT,
        max_connections: int = MAX_CONNECTIONS,
        pairing_service: PairingService | None = None,
        require_auth: bool = False,
    ) -> None:
        self.repository = repository
        self.server_id = server_id
        self.server_version = server_version
        self.handshake_timeout = handshake_timeout
        self.idle_timeout = idle_timeout
        self.send_timeout = send_timeout
        self.max_connections = max_connections
        self.pairing_service = pairing_service
        self.require_auth = require_auth
        self._sessions: dict[WebSocket, ClientSession] = {}
        self._broadcast_lock = asyncio.Lock()
        self._last_broadcast_revision: dict[str, int] = {}

    @property
    def connection_count(self) -> int:
        return len(self._sessions)

    async def register(self, websocket: WebSocket, session: ClientSession) -> None:
        if self.connection_count >= self.max_connections:
            raise RuntimeError("websocket connection limit reached")
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
        async with self._broadcast_lock:
            if revision <= self._last_broadcast_revision.get(profile_id, 0):
                return
            self._last_broadcast_revision[profile_id] = revision
            message = ProfileChangedMessage(
                protocol_version=1,
                type="profile_changed",
                payload={
                    "profile_id": profile_id,
                    "revision": revision,
                    "reason": reason,
                },
            ).to_wire_json()
            targets = [
                (websocket, session)
                for websocket, session in tuple(self._sessions.items())
                if session.profile_id == profile_id
            ]
            results = await asyncio.gather(
                *(
                    self._send_broadcast(websocket, session, message)
                    for websocket, session in targets
                )
            )
            stale = [
                websocket
                for (websocket, _), failed in zip(targets, results, strict=True)
                if failed
            ]
        for websocket in stale:
            await self.unregister(websocket)

    async def _send_broadcast(
        self,
        websocket: WebSocket,
        session: ClientSession,
        message: str,
    ) -> bool:
        async with session.send_lock:
            if not session.ready:
                session.pending_messages.append(message)
                return False
            try:
                await asyncio.wait_for(
                    websocket.send_text(message), timeout=self.send_timeout
                )
            except Exception:
                return True
        return False


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
    session: ClientSession | None = None,
) -> str:
    wire = _error_message(
        code,
        message,
        request_id=request_id,
        retryable=retryable,
    ).to_wire_json()
    if session is None:
        await websocket.send_text(wire)
    else:
        await _send_session_text(websocket, session, wire)
    return wire


async def _send_invalid_message(
    websocket: WebSocket,
    *,
    session: ClientSession | None = None,
) -> None:
    await _send_error(
        websocket,
        "INVALID_MESSAGE",
        "Invalid WebSocket message",
        session=session,
    )


def _parse_message(raw_message: str) -> Any | None:
    if len(raw_message.encode("utf-8")) > MAX_FRAME_BYTES:
        return None
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
        await _send_session_text(websocket, session, previous)
        return

    if message.payload.profile_id != session.profile_id:
        wire = await _send_error(
            websocket,
            "PROFILE_NOT_SELECTED",
            "Profile is not selected for this session",
            request_id=request_id,
            session=session,
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
            session=session,
        )
        _cache_response(session, request_id, wire)
        return
    except Exception:
        wire = await _send_error(
            websocket,
            "INTERNAL_ERROR",
            "Internal server error",
            request_id=request_id,
            session=session,
        )
        _cache_response(session, request_id, wire)
        return

    if profile.revision != message.payload.revision:
        await _send_error(
            websocket,
            "PROFILE_REVISION_CONFLICT",
            "Profile revision conflict",
            request_id=request_id,
            retryable=True,
            session=session,
        )
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
            session=session,
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
            session=session,
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
    await _send_session_text(websocket, session, ack)


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
    handshake_started = asyncio.get_running_loop().time()
    try:
        try:
            raw_hello = await asyncio.wait_for(
                websocket.receive_text(), timeout=manager.handshake_timeout
            )
        except asyncio.TimeoutError:
            await _close_handshake_timeout(websocket)
            return
        except WebSocketDisconnect:
            return

        hello = _parse_message(raw_hello)
        if not isinstance(hello, HelloMessage):
            await _send_invalid_message(websocket)
            await websocket.close(code=1002)
            return

        if manager.require_auth:
            pairing_service = manager.pairing_service
            if pairing_service is None or hello.payload.access_token is None:
                await _send_error(
                    websocket,
                    "AUTH_REQUIRED",
                    "Authenticated WebSocket session required",
                )
                await websocket.close(code=1008)
                return
            try:
                authenticated = await run_in_threadpool(
                    pairing_service.authenticate,
                    hello.payload.client_id,
                    hello.payload.access_token,
                )
            except PairingError:
                authenticated = False
            if not authenticated:
                await _send_error(
                    websocket,
                    "AUTH_INVALID",
                    "WebSocket authentication failed",
                )
                await websocket.close(code=1008)
                return

        remaining_handshake = manager.handshake_timeout - (
            asyncio.get_running_loop().time() - handshake_started
        )
        if remaining_handshake <= 0:
            await _close_handshake_timeout(websocket)
            return
        try:
            profile = await asyncio.wait_for(
                _load_requested_profile(
                    repository,
                    hello.payload.requested_profile_id,
                ),
                timeout=remaining_handshake,
            )
        except asyncio.TimeoutError:
            await _close_handshake_timeout(websocket)
            return
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
        try:
            await manager.register(websocket, session)
        except RuntimeError:
            await _send_error(
                websocket,
                "CONNECTION_LIMIT",
                "WebSocket connection limit reached",
                retryable=True,
            )
            await websocket.close(code=1013)
            return
        welcome_wire = WelcomeMessage(
            protocol_version=1,
            type="welcome",
            payload=WelcomePayload(
                server_id=manager.server_id,
                server_version=manager.server_version,
                profile_id=profile.id,
                revision=profile.revision,
            ),
        ).to_wire_json()
        snapshot_wire = ProfileSnapshotMessage(
            protocol_version=1,
            type="profile_snapshot",
            payload={"profile": profile},
        ).to_wire_json()
        async with session.send_lock:
            await websocket.send_text(welcome_wire)
            await websocket.send_text(snapshot_wire)
            session.ready = True
            pending_messages = tuple(session.pending_messages)
            session.pending_messages.clear()
            for pending_message in pending_messages:
                await websocket.send_text(pending_message)

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
                    session=session,
                )
                await websocket.close(code=1000)
                return
            except WebSocketDisconnect:
                return

            message = _parse_message(raw_message)
            if message is None:
                await _send_invalid_message(websocket, session=session)
            elif isinstance(message, PingMessage):
                await _send_session_text(
                    websocket,
                    session,
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
                    session=session,
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
