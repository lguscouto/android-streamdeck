from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app


async def _send(
    app: Any,
    method: str,
    path: str,
    *,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            json=json_body,
            headers=headers,
        )


def request(
    app: Any,
    method: str,
    path: str,
    *,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return asyncio.run(_send(app, method, path, json_body=json_body, headers=headers))


def make_app(tmp_path: Path) -> Any:
    return create_app(
        Settings(
            database_path=tmp_path / "streamdeck.sqlite3",
            pairing_code="pairing-code",
            require_auth=True,
            admin_code="admin-code",
        )
    )


def admin_headers() -> dict[str, str]:
    return {"x-streamdeck-admin-code": "admin-code"}


def claim(app: Any) -> str:
    response = request(
        app,
        "POST",
        "/api/v1/pairing/claim",
        json_body={
            "client_id": "android-1",
            "client_version": "0.1.0",
            "pairing_code": "pairing-code",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_device_inventory_requires_separate_admin_code(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    claim(app)

    missing = request(app, "GET", "/api/v1/devices")
    wrong = request(
        app,
        "GET",
        "/api/v1/devices",
        headers={"x-streamdeck-admin-code": "wrong-code"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json() == {
        "code": "DEVICE_ADMIN_REQUIRED",
        "message": "Device administration requires local owner authorization",
        "retryable": False,
    }


def test_device_inventory_is_sanitized_and_revoke_is_idempotent(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    token = claim(app)

    inventory = request(
        app,
        "GET",
        "/api/v1/devices",
        headers=admin_headers(),
    )
    assert inventory.status_code == 200
    assert inventory.json() == {
        "devices": [
            {
                "client_id": "android-1",
                "client_version": "0.1.0",
                "platform": "android",
                "credential_generation": 1,
                "paired_at": inventory.json()["devices"][0]["paired_at"],
                "last_seen_at": None,
                "revoked_at": None,
                "revoked_reason": None,
            }
        ]
    }
    serialized = inventory.text
    assert token not in serialized
    assert "token_hash" not in serialized
    assert "device_label" not in serialized

    revoked = request(
        app,
        "POST",
        "/api/v1/devices/android-1/revoke",
        json_body={"reason": "lost_device"},
        headers=admin_headers(),
    )
    assert revoked.status_code == 200
    assert revoked.json()["device"]["revoked_reason"] == "lost_device"
    assert revoked.json()["device"]["revoked_at"] is not None

    repeated = request(
        app,
        "POST",
        "/api/v1/devices/android-1/revoke",
        json_body={"reason": "lost_device"},
        headers=admin_headers(),
    )
    assert repeated.status_code == 200
    assert repeated.json() == revoked.json()

    assert (
        request(
            app,
            "GET",
            "/api/v1/devices",
            headers=admin_headers(),
        ).json()["devices"][0]["revoked_reason"]
        == "lost_device"
    )

    with app.state.database.connect() as connection:
        row = connection.execute(
            "SELECT token_hash FROM paired_clients WHERE client_id = ?",
            ("android-1",),
        ).fetchone()
    assert row is not None
    assert token != row["token_hash"]


def test_pairing_attempts_are_rate_limited_per_origin(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    responses = [
        request(
            app,
            "POST",
            "/api/v1/pairing/claim",
            json_body={
                "client_id": "android-1",
                "client_version": "0.1.0",
                "pairing_code": "wrong-code",
            },
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401] * 5 + [429]
    assert responses[-1].json() == {
        "code": "PAIRING_RATE_LIMITED",
        "message": "Too many pairing attempts",
        "retryable": True,
    }


def test_device_admin_attempts_are_rate_limited_per_origin(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    responses = [
        request(
            app,
            "GET",
            "/api/v1/devices",
            headers={"x-streamdeck-admin-code": "wrong-code"},
        )
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401] * 5 + [429]
    assert responses[-1].json() == {
        "code": "DEVICE_ADMIN_RATE_LIMITED",
        "message": "Too many device administration attempts",
        "retryable": True,
    }


def test_admin_revoke_closes_authenticated_websocket_immediately(
    tmp_path: Path,
) -> None:
    app = make_app(tmp_path)
    token = claim(app)
    hello = {
        "protocol_version": 1,
        "type": "hello",
        "payload": {
            "client_id": "android-1",
            "client_version": "0.1.0",
            "supported_protocol_versions": [1],
            "access_token": token,
        },
    }

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello)
            assert websocket.receive_json()["type"] == "welcome"
            assert websocket.receive_json()["type"] == "profile_snapshot"

            revoked = client.post(
                "/api/v1/devices/android-1/revoke",
                json={"reason": "security"},
                headers=admin_headers(),
            )
            assert revoked.status_code == 200

            error = websocket.receive_json()
            assert error["payload"]["code"] == "AUTH_REVOKED"
            try:
                websocket.receive_text()
            except WebSocketDisconnect as exc:
                assert exc.code == 1008
            else:
                raise AssertionError("revoked websocket did not close immediately")

    assert app.state.websocket_manager.connection_count == 0


def test_repairing_closes_previous_websocket_immediately(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    old_token = claim(app)
    hello = {
        "protocol_version": 1,
        "type": "hello",
        "payload": {
            "client_id": "android-1",
            "client_version": "0.1.0",
            "supported_protocol_versions": [1],
            "access_token": old_token,
        },
    }

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello)
            websocket.receive_json()
            websocket.receive_json()

            repaired = client.post(
                "/api/v1/pairing/claim",
                json={
                    "client_id": "android-1",
                    "client_version": "0.1.0",
                    "pairing_code": "pairing-code",
                },
            )
            assert repaired.status_code == 200
            assert repaired.json()["access_token"] != old_token

            error = websocket.receive_json()
            assert error["payload"]["code"] == "AUTH_REVOKED"
            try:
                websocket.receive_text()
            except WebSocketDisconnect as exc:
                assert exc.code == 1008
            else:
                raise AssertionError("repaired websocket did not close immediately")

    assert app.state.websocket_manager.connection_count == 0


def test_device_admin_is_unavailable_without_explicit_admin_code(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "streamdeck.sqlite3",
            pairing_code="pairing-code",
            require_auth=True,
        )
    )

    response = request(app, "GET", "/api/v1/devices")

    assert response.status_code == 503
    assert response.json() == {
        "code": "DEVICE_ADMIN_UNAVAILABLE",
        "message": "Device administration unavailable",
        "retryable": True,
    }
