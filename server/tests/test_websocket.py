from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.rate_limit import AttemptRateLimiter
from app.repositories.profiles import ProfileRepository
from app.websocket import ClientSession, WebSocketManager

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def make_repository(tmp_path: Path) -> ProfileRepository:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    return repository


def make_seeded_app(tmp_path: Path, **kwargs: object):
    repository = make_repository(tmp_path)
    repository.seed_profile(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    return create_app(
        Settings(database_path=tmp_path / "streamdeck.sqlite3"),
        repository=repository,
        **kwargs,
    )


def make_client(
    tmp_path: Path, *, manager: WebSocketManager | None = None
) -> TestClient:
    app = make_seeded_app(tmp_path, websocket_manager=manager)
    return TestClient(app)


def hello_message() -> dict[str, object]:
    return {
        "protocol_version": 1,
        "type": "hello",
        "payload": {
            "client_id": "android-1",
            "client_version": "0.1.0",
            "supported_protocol_versions": [1],
        },
    }


def test_websocket_handshake_sends_welcome_and_snapshot(tmp_path: Path) -> None:
    with make_client(tmp_path).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())

        welcome = websocket.receive_json()
        snapshot = websocket.receive_json()

    assert welcome["type"] == "welcome"
    assert welcome["payload"] == {
        "server_id": "windows-server",
        "server_version": "0.1.0",
        "profile_id": "default",
        "revision": 1,
    }
    assert snapshot["type"] == "profile_snapshot"
    assert snapshot["payload"]["profile"]["id"] == "default"
    assert snapshot["payload"]["profile"]["revision"] == 1


def test_websocket_handshake_queues_concurrent_profile_change_after_snapshot(
    tmp_path: Path,
) -> None:
    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository

    class BroadcastDuringHandshake(WebSocketManager):
        async def register(self, websocket, session) -> None:
            await super().register(websocket, session)
            asyncio.create_task(
                self.broadcast_profile_changed("default", 2, reason="updated")
            )

    manager = BroadcastDuringHandshake(repository)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        frames = [websocket.receive_json() for _ in range(3)]

    assert [frame["type"] for frame in frames] == [
        "welcome",
        "profile_snapshot",
        "profile_changed",
    ]


def test_websocket_ping_returns_same_nonce_as_pong(tmp_path: Path) -> None:
    with make_client(tmp_path).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(
            {
                "protocol_version": 1,
                "type": "ping",
                "payload": {"nonce": "heartbeat-1"},
            }
        )

        assert websocket.receive_json() == {
            "protocol_version": 1,
            "type": "pong",
            "payload": {"nonce": "heartbeat-1"},
        }


def test_websocket_valid_press_executes_once_and_caches_completed_ack(
    tmp_path: Path,
) -> None:
    from app.actions import ActionExecutionResult

    class RecordingActionExecutor:
        def __init__(self) -> None:
            self.actions: list[object] = []

        def execute(self, action: object) -> ActionExecutionResult:
            self.actions.append(action)
            return ActionExecutionResult("completed", "Action completed")

    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    action_executor = RecordingActionExecutor()
    manager = WebSocketManager(repository, action_executor=action_executor)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    press = {
        "protocol_version": 1,
        "type": "press",
        "payload": {
            "request_id": "press-1",
            "profile_id": "default",
            "page_id": "main",
            "button_id": "save-shortcut",
            "revision": 1,
        },
    }

    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(press)
        response = websocket.receive_json()
        websocket.send_json(press)
        duplicate = websocket.receive_json()

    assert response == {
        "protocol_version": 1,
        "type": "ack",
        "payload": {
            "request_id": "press-1",
            "status": "completed",
            "message": "Action completed",
        },
    }
    assert duplicate == response
    assert len(action_executor.actions) == 1


def test_websocket_action_rejection_is_sanitized_and_cached(tmp_path: Path) -> None:
    from app.actions import ActionExecutionRejected

    class RejectingActionExecutor:
        def __init__(self) -> None:
            self.call_count = 0

        def execute(self, action: object) -> object:
            self.call_count += 1
            raise ActionExecutionRejected("Action type is not enabled")

    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    action_executor = RejectingActionExecutor()
    manager = WebSocketManager(repository, action_executor=action_executor)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    press = {
        "protocol_version": 1,
        "type": "press",
        "payload": {
            "request_id": "press-rejected",
            "profile_id": "default",
            "page_id": "main",
            "button_id": "save-shortcut",
            "revision": 1,
        },
    }

    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(press)
        response = websocket.receive_json()
        websocket.send_json(press)
        duplicate = websocket.receive_json()

    assert response == {
        "protocol_version": 1,
        "type": "ack",
        "payload": {
            "request_id": "press-rejected",
            "status": "rejected",
            "message": "Action type is not enabled",
        },
    }
    assert duplicate == response
    assert action_executor.call_count == 1


def test_websocket_unexpected_action_failure_is_sanitized_and_keeps_session(
    tmp_path: Path,
) -> None:
    class FailingActionExecutor:
        def execute(self, action: object) -> object:
            raise RuntimeError("C:/private/internal-action-detail")

    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    manager = WebSocketManager(repository, action_executor=FailingActionExecutor())
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    press = {
        "protocol_version": 1,
        "type": "press",
        "payload": {
            "request_id": "press-failed",
            "profile_id": "default",
            "page_id": "main",
            "button_id": "save-shortcut",
            "revision": 1,
        },
    }

    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(press)
        response = websocket.receive_json()
        websocket.send_json(
            {
                "protocol_version": 1,
                "type": "ping",
                "payload": {"nonce": "after-action-failure"},
            }
        )
        pong = websocket.receive_json()

    assert response == {
        "protocol_version": 1,
        "type": "ack",
        "payload": {
            "request_id": "press-failed",
            "status": "rejected",
            "message": "Action could not be completed",
        },
    }
    assert "internal-action-detail" not in str(response)
    assert pong["type"] == "pong"


def test_websocket_press_rejects_stale_revision_and_unknown_button(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(
            {
                "protocol_version": 1,
                "type": "press",
                "payload": {
                    "request_id": "press-stale",
                    "profile_id": "default",
                    "page_id": "main",
                    "button_id": "save-shortcut",
                    "revision": 99,
                },
            }
        )
        stale = websocket.receive_json()

        websocket.send_json(
            {
                "protocol_version": 1,
                "type": "press",
                "payload": {
                    "request_id": "press-missing",
                    "profile_id": "default",
                    "page_id": "main",
                    "button_id": "missing",
                    "revision": 1,
                },
            }
        )
        missing = websocket.receive_json()

    assert stale["type"] == "error"
    assert stale["payload"]["code"] == "PROFILE_REVISION_CONFLICT"
    assert missing["type"] == "error"
    assert missing["payload"]["code"] == "BUTTON_NOT_FOUND"
    assert "sqlite" not in str(stale).lower()


def test_websocket_retryable_conflict_is_not_cached(tmp_path: Path) -> None:
    from app.actions import ActionExecutionResult

    class RecordingActionExecutor:
        def __init__(self) -> None:
            self.call_count = 0

        def execute(self, action: object) -> ActionExecutionResult:
            self.call_count += 1
            return ActionExecutionResult("completed", "Action completed")

    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    action_executor = RecordingActionExecutor()
    manager = WebSocketManager(repository, action_executor=action_executor)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message())
            websocket.receive_json()
            websocket.receive_json()
            press = {
                "protocol_version": 1,
                "type": "press",
                "payload": {
                    "request_id": "retry-conflict",
                    "profile_id": "default",
                    "page_id": "main",
                    "button_id": "save-shortcut",
                    "revision": 99,
                },
            }
            websocket.send_json(press)
            conflict = websocket.receive_json()

            payload = client.get("/api/v1/profile").json()
            payload["revision"] = 2
            response = client.put(
                "/api/v1/profiles/default?expected_revision=1", json=payload
            )
            assert response.status_code == 200
            assert websocket.receive_json()["type"] == "profile_changed"

            press["payload"]["revision"] = 2
            websocket.send_json(press)
            retry = websocket.receive_json()

    assert conflict["payload"]["code"] == "PROFILE_REVISION_CONFLICT"
    assert retry["type"] == "ack"
    assert retry["payload"]["status"] == "completed"
    assert action_executor.call_count == 1


def test_websocket_slow_broadcast_connection_is_removed(tmp_path: Path) -> None:
    class SlowWebSocket:
        async def send_text(self, message: str) -> None:
            await asyncio.sleep(1)

    async def exercise() -> int:
        repository = make_repository(tmp_path)
        manager = WebSocketManager(repository, send_timeout=0.01)
        websocket = SlowWebSocket()
        await manager.register(
            websocket,
            ClientSession(client_id="slow", profile_id="default", ready=True),
        )
        await manager.broadcast_profile_changed("default", 2)
        return manager.connection_count

    assert asyncio.run(exercise()) == 0


def test_websocket_press_cannot_target_another_session_profile(
    tmp_path: Path,
) -> None:
    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    second_profile = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "shared"
            / "fixtures"
            / "default-profile.json"
        ).read_text(encoding="utf-8")
    )
    second_profile["id"] = "second"
    repository.seed_profile(second_profile)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
    )

    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {
                "protocol_version": 1,
                "type": "press",
                "payload": {
                    "request_id": "cross-profile",
                    "profile_id": "second",
                    "page_id": "main",
                    "button_id": "save-shortcut",
                    "revision": 1,
                },
            }
        )
        response = websocket.receive_json()

    assert response == {
        "protocol_version": 1,
        "type": "error",
        "payload": {
            "request_id": "cross-profile",
            "code": "PROFILE_NOT_SELECTED",
            "message": "Profile is not selected for this session",
            "retryable": False,
        },
    }


def test_websocket_profile_change_is_broadcast_to_connected_client(
    tmp_path: Path,
) -> None:
    app = make_seeded_app(tmp_path)
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message())
            websocket.receive_json()
            websocket.receive_json()

            payload = client.get("/api/v1/profile").json()
            payload["revision"] = 2
            payload["pages"][0]["buttons"][0]["title"] = "Atualizado"
            response = client.put(
                "/api/v1/profiles/default?expected_revision=1", json=payload
            )
            assert response.status_code == 200

            changed = websocket.receive_json()

    assert changed == {
        "protocol_version": 1,
        "type": "profile_changed",
        "payload": {
            "profile_id": "default",
            "revision": 2,
            "reason": "updated",
        },
    }


def test_websocket_invalid_first_message_returns_sanitized_error(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json({"type": "shell", "command": "whoami"})
        response = websocket.receive_json()

    assert response == {
        "protocol_version": 1,
        "type": "error",
        "payload": {
            "code": "INVALID_MESSAGE",
            "message": "Invalid WebSocket message",
            "retryable": False,
        },
    }


def test_websocket_handshake_timeout_is_structured(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    manager = WebSocketManager(repository, handshake_timeout=0.01)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        response = websocket.receive_json()

    assert response["type"] == "error"
    assert response["payload"] == {
        "code": "HANDSHAKE_TIMEOUT",
        "message": "WebSocket handshake timed out",
        "retryable": True,
    }


def test_websocket_handshake_deadline_includes_profile_load(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    original = repository.get_active_profile

    def slow_get_active_profile():
        time.sleep(0.1)
        return original()

    monkeypatch.setattr(repository, "get_active_profile", slow_get_active_profile)
    manager = WebSocketManager(repository, handshake_timeout=0.03)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        response = websocket.receive_json()

    assert response["payload"]["code"] == "HANDSHAKE_TIMEOUT"


def test_websocket_idle_timeout_is_structured(tmp_path: Path) -> None:
    seeded_app = make_seeded_app(tmp_path)
    repository = seeded_app.state.profile_repository
    manager = WebSocketManager(repository, idle_timeout=0.05)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )
    with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()
        response = websocket.receive_json()

    assert response["type"] == "error"
    assert response["payload"] == {
        "code": "IDLE_TIMEOUT",
        "message": "WebSocket session timed out",
        "retryable": True,
    }


def test_websocket_handshake_rate_limits_abusive_origin(tmp_path: Path) -> None:
    """Repeated invalid handshakes from one origin are throttled per-origin."""
    limiter = AttemptRateLimiter(max_attempts=2, window_seconds=60.0)
    manager = WebSocketManager(
        make_repository(tmp_path),
        handshake_rate_limiter=limiter,
        require_auth=True,
        pairing_service=None,
    )
    app = create_app(
        Settings(
            database_path=tmp_path / "unused.sqlite3",
            require_auth=True,
            pairing_code="pair-valid",
        ),
        repository=manager.repository,
        websocket_manager=manager,
    )

    with TestClient(app) as client:
        # First connection: accepted and sent a hello need, but auth fails
        # because pairing_service is None -> WS_AUTH_FAILED with close 1008.
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message())
            error = websocket.receive_json()
            assert error["payload"]["code"] == "AUTH_REQUIRED"

        # Second connection from the same origin: rate limiter window at max,
        # but the limiter counts only on *failed* handshakes; the second still
        # passes the limiter guard (2 allowed), auth still fails.
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message())
            error = websocket.receive_json()
            assert error["payload"]["code"] == "AUTH_REQUIRED"

        # Third connection: rate limited before auth -> RATE_LIMITED close.
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message())
            error = websocket.receive_json()
            assert error["payload"]["code"] == "RATE_LIMITED"
