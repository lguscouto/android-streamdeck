from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.repositories.profiles import ProfileRepository
from app.websocket import WebSocketManager


def make_repository(tmp_path: Path) -> ProfileRepository:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    return repository


def make_client(
    tmp_path: Path, *, manager: WebSocketManager | None = None
) -> TestClient:
    app = create_app(
        Settings(database_path=tmp_path / "streamdeck.sqlite3"),
        websocket_manager=manager,
    )
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


def test_websocket_valid_press_is_acknowledged_as_unavailable(tmp_path: Path) -> None:
    with make_client(tmp_path).websocket_connect("/api/v1/ws") as websocket:
        websocket.send_json(hello_message())
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(
            {
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
        )

        response = websocket.receive_json()
        websocket.send_json(
            {
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
        )
        duplicate = websocket.receive_json()

    assert response["type"] == "ack"
    assert response["payload"] == {
        "request_id": "press-1",
        "status": "rejected",
        "message": "Action execution unavailable in phase 1",
    }
    assert duplicate == response


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


def test_websocket_profile_change_is_broadcast_to_connected_client(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
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


def test_websocket_idle_timeout_is_structured(tmp_path: Path) -> None:
    seeded_app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
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