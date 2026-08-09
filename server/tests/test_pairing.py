from __future__ import annotations

import asyncio
import secrets
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.repositories.profiles import ProfileRepository

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def request(
    app: Any,
    method: str,
    path: str,
    *,
    json_body: Any = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json_body)

    return asyncio.run(send())


def make_repository(tmp_path: Path) -> ProfileRepository:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    return repository


def make_authenticated_app(tmp_path: Path) -> tuple[Any, str]:
    pairing_code = f"test-{secrets.token_urlsafe(24)}"
    app = create_app(
        Settings(
            database_path=tmp_path / "streamdeck.sqlite3",
            pairing_code=pairing_code,
            require_auth=True,
        )
    )
    return app, pairing_code


def hello_message(*, token: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_id": "android-1",
        "client_version": "0.1.0",
        "supported_protocol_versions": [1],
    }
    if token is not None:
        payload["access_token"] = token
    return {
        "protocol_version": 1,
        "type": "hello",
        "payload": payload,
    }


def test_pairing_claim_returns_opaque_token_and_persists_only_hash(
    tmp_path: Path,
) -> None:
    app, pairing_code = make_authenticated_app(tmp_path)

    response = request(
        app,
        "POST",
        "/api/v1/pairing/claim",
        json_body={
            "client_id": "android-1",
            "client_version": "0.1.0",
            "pairing_code": pairing_code,
        },
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    assert isinstance(token, str)
    assert len(token) >= 32
    assert response.json()["client_id"] == "android-1"

    with app.state.database.connect() as connection:
        row = connection.execute(
            "SELECT token_hash FROM paired_clients WHERE client_id = ?",
            ("android-1",),
        ).fetchone()
    assert row is not None
    assert row["token_hash"] != token
    assert len(row["token_hash"]) == 64


def test_pairing_claim_rejects_wrong_code_without_secret_details(
    tmp_path: Path,
) -> None:
    app, pairing_code = make_authenticated_app(tmp_path)
    response = request(
        app,
        "POST",
        "/api/v1/pairing/claim",
        json_body={
            "client_id": "android-1",
            "client_version": "0.1.0",
            "pairing_code": "wrong-code",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "PAIRING_CODE_INVALID",
        "message": "Pairing code is invalid",
        "retryable": False,
    }
    assert pairing_code not in response.text


def test_pairing_token_authenticates_websocket_and_missing_token_is_rejected(
    tmp_path: Path,
) -> None:
    app, pairing_code = make_authenticated_app(tmp_path)
    claim = request(
        app,
        "POST",
        "/api/v1/pairing/claim",
        json_body={
            "client_id": "android-1",
            "client_version": "0.1.0",
            "pairing_code": pairing_code,
        },
    )
    token = claim.json()["access_token"]

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message())
            unauthenticated = websocket.receive_json()
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message(token=token))
            welcome = websocket.receive_json()
            snapshot = websocket.receive_json()

    assert unauthenticated["payload"]["code"] == "AUTH_REQUIRED"
    assert welcome["type"] == "welcome"
    assert snapshot["type"] == "profile_snapshot"


def test_repairing_same_client_revokes_previous_token(tmp_path: Path) -> None:
    app, pairing_code = make_authenticated_app(tmp_path)

    def claim() -> str:
        return request(
            app,
            "POST",
            "/api/v1/pairing/claim",
            json_body={
                "client_id": "android-1",
                "client_version": "0.1.0",
                "pairing_code": pairing_code,
            },
        ).json()["access_token"]

    first = claim()
    second = claim()

    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message(token=first))
            revoked = websocket.receive_json()
        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json(hello_message(token=second))
            accepted = websocket.receive_json()

    assert revoked["payload"]["code"] == "AUTH_INVALID"
    assert accepted["type"] == "welcome"


def test_remote_bind_requires_authentication() -> None:
    try:
        Settings(host="0.0.0.0", port=8765)
    except ValueError as error:
        assert "authentication" in str(error).lower()
    else:
        raise AssertionError("remote bind without authentication must be rejected")


def test_migration_creates_pairing_table(tmp_path: Path) -> None:
    database = Database(tmp_path / "streamdeck.sqlite3")
    database.initialize()

    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "paired_clients" in tables
