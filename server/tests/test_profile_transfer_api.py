from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_PATH = REPO_ROOT / "shared" / "fixtures" / "default-profile.json"


def load_profile(*, profile_id: str = "default", revision: int = 1) -> dict[str, Any]:
    profile = json.loads(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    profile["id"] = profile_id
    profile["revision"] = revision
    return profile


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_body: Any = None,
    content: str | bytes | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.request(
                method,
                path,
                json=json_body,
                content=content,
                headers=headers,
            )

    return asyncio.run(send())


def auth_headers(app: FastAPI) -> dict[str, str]:
    claim = request(
        app,
        "POST",
        "/api/v1/pairing/claim",
        json_body={
            "client_id": "test-client",
            "client_version": "0.5.0",
            "pairing_code": "phase5-code",
        },
    )
    assert claim.status_code == 200
    return {
        "Authorization": f"Bearer {claim.json()['access_token']}",
        "X-StreamDeck-Client-Id": "test-client",
    }


def test_export_returns_current_sanitized_profile_as_json(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))

    response = request(app, "GET", "/api/v1/profiles/default/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["id"] == "default"
    assert response.json()["revision"] == 1
    assert "null" not in response.text
    assert "token" not in response.text.lower()
    assert "shell" not in response.text.lower()
    assert "whoami" not in response.text.lower()


def test_import_creates_new_profile_at_revision_one(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
    payload = load_profile(profile_id="imported", revision=99)

    response = request(
        app,
        "POST",
        "/api/v1/profiles/import",
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "imported"
    assert response.json()["revision"] == 1
    snapshot = request(app, "GET", "/api/v1/profiles/imported/export")
    assert snapshot.status_code == 200
    assert snapshot.json()["revision"] == 1


def test_import_updates_existing_profile_using_expected_revision(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
    payload = load_profile(revision=999)
    payload["pages"][0]["buttons"][0]["title"] = "Importado"

    response = request(
        app,
        "POST",
        "/api/v1/profiles/import?expected_revision=1",
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "default"
    assert response.json()["revision"] == 2
    assert response.json()["pages"][0]["buttons"][0]["title"] == "Importado"


def test_import_and_export_require_authentication_when_enabled(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "streamdeck.sqlite3",
            host="192.0.2.10",
            pairing_code="phase5-code",
            require_auth=True,
        )
    )
    payload = load_profile(profile_id="auth-import")

    export_response = request(app, "GET", "/api/v1/profiles/default/export")
    import_response = request(
        app,
        "POST",
        "/api/v1/profiles/import",
        content=json.dumps(payload),
    )

    assert export_response.status_code == 401
    assert import_response.status_code == 401
    assert export_response.json() == import_response.json() == {
        "code": "AUTH_REQUIRED",
        "message": "Authentication required",
        "retryable": False,
    }

    headers = auth_headers(app)
    authenticated_export = request(
        app,
        "GET",
        "/api/v1/profiles/default/export",
        headers=headers,
    )
    authenticated_import = request(
        app,
        "POST",
        "/api/v1/profiles/import",
        content=json.dumps(payload),
        headers=headers,
    )

    assert authenticated_export.status_code == 200
    assert authenticated_import.status_code == 200


def test_import_rejects_stale_expected_revision_without_mutation(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
    first_payload = load_profile(revision=500)
    second_payload = copy.deepcopy(first_payload)
    second_payload["pages"][0]["buttons"][0]["title"] = "Stale"

    first = request(
        app,
        "POST",
        "/api/v1/profiles/import?expected_revision=1",
        content=json.dumps(first_payload),
    )
    stale = request(
        app,
        "POST",
        "/api/v1/profiles/import?expected_revision=1",
        content=json.dumps(second_payload),
    )

    assert first.status_code == 200
    assert first.json()["revision"] == 2
    assert stale.status_code == 409
    assert stale.json() == {
        "code": "PROFILE_REVISION_CONFLICT",
        "message": "Profile revision conflict",
        "retryable": True,
    }
    current = request(app, "GET", "/api/v1/profiles/default/export")
    assert current.json()["revision"] == 2
    assert current.json()["pages"][0]["buttons"][0]["title"] != "Stale"


def test_import_existing_profile_requires_expected_revision(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
    response = request(
        app,
        "POST",
        "/api/v1/profiles/import",
        content=json.dumps(load_profile(revision=100)),
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "PROFILE_REVISION_CONFLICT",
        "message": "Profile revision conflict",
        "retryable": True,
    }


def test_import_rejects_shell_extra_and_invalid_json_with_sanitized_errors(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
    extra = load_profile(profile_id="extra")
    extra["unexpected"] = "nope"
    shell = load_profile(profile_id="shell")
    shell["pages"][0]["buttons"][0]["action"] = {
        "type": "shell",
        "command": "whoami",
    }

    responses = [
        request(app, "POST", "/api/v1/profiles/import", content=json.dumps(extra)),
        request(app, "POST", "/api/v1/profiles/import", content=json.dumps(shell)),
        request(app, "POST", "/api/v1/profiles/import", content="not-json"),
    ]

    assert all(response.status_code == 422 for response in responses)
    assert all(
        response.json()
        == {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "retryable": False,
        }
        for response in responses
    )
    assert "whoami" not in responses[1].text
    assert "command" not in responses[1].text.lower()


def test_import_rejects_json_over_512_kib_with_sanitized_error(tmp_path: Path) -> None:
    app = create_app(Settings(database_path=tmp_path / "streamdeck.sqlite3"))
    oversized = json.dumps({"padding": "x" * (512 * 1024)})

    response = request(
        app,
        "POST",
        "/api/v1/profiles/import",
        content=oversized,
        headers={"content-type": "application/json"},
    )

    assert len(oversized.encode("utf-8")) > 512 * 1024
    assert response.status_code == 413
    assert response.json() == {
        "code": "PAYLOAD_TOO_LARGE",
        "message": "Profile payload is too large",
        "retryable": False,
    }
    assert "padding" not in response.text
    assert "Traceback" not in response.text


def test_import_persistence_succeeds_when_broadcast_fails(tmp_path: Path) -> None:
    class FailingBroadcast:
        async def broadcast_profile_changed(
            self,
            _profile_id: str,
            _revision: int,
            *,
            reason: str,
        ) -> None:
            raise RuntimeError(reason)

    app = create_app(
        Settings(database_path=tmp_path / "streamdeck.sqlite3"),
        websocket_manager=FailingBroadcast(),
    )
    payload = load_profile(profile_id="broadcast-failure")

    response = request(
        app,
        "POST",
        "/api/v1/profiles/import",
        content=json.dumps(payload),
    )

    assert response.status_code == 200
    assert response.json()["id"] == "broadcast-failure"
    assert request(
        app,
        "GET",
        "/api/v1/profiles/broadcast-failure/export",
    ).status_code == 200
