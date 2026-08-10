from __future__ import annotations

import asyncio
import copy
import json
import secrets
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.repositories.profiles import ProfileRepository

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


def load_profile_payload(
    *, profile_id: str = "default", revision: int = 1
) -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    payload["revision"] = revision
    return payload


def updated_profile_payload(*, revision: int = 2) -> dict[str, Any]:
    payload = copy.deepcopy(load_profile_payload(revision=revision))
    payload["pages"][0]["buttons"][0]["title"] = "Atalho atualizado"
    return payload


def request(
    app: Any,
    method: str,
    path: str,
    *,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.request(method, path, json=json_body, headers=headers)

    return asyncio.run(send())


def make_repository(tmp_path: Path) -> ProfileRepository:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    return repository


def make_seeded_app(tmp_path: Path, **kwargs: Any) -> Any:
    return create_app(
        Settings(database_path=tmp_path / "streamdeck.sqlite3"),
        **kwargs,
    )


def test_health_regression_is_exactly_sanitized(tmp_path: Path) -> None:
    response = request(make_seeded_app(tmp_path), "GET", "/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "android-streamdeck-server",
        "protocol_version": "0.1",
    }


def test_settings_include_database_path_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pairing_code = f"test-{secrets.token_urlsafe(24)}"
    monkeypatch.setenv("STREAMDECK_HOST", "192.0.2.10")
    monkeypatch.setenv("STREAMDECK_PORT", "9000")
    monkeypatch.setenv("STREAMDECK_DATABASE_PATH", "custom/streamdeck.sqlite3")
    monkeypatch.setenv("STREAMDECK_PAIRING_CODE", pairing_code)
    monkeypatch.setenv("STREAMDECK_ADMIN_CODE", "admin-code")
    monkeypatch.setenv("STREAMDECK_REQUIRE_AUTH", "true")
    monkeypatch.setenv("STREAMDECK_TLS_IDENTITIES", "deck.example.test")

    settings = Settings.from_env()

    assert settings.host == "192.0.2.10"
    assert settings.port == 9000
    assert settings.database_path == "custom/streamdeck.sqlite3"
    assert settings.pairing_code == pairing_code
    assert settings.admin_code == "admin-code"
    assert settings.require_auth is True


def test_active_profile_returns_wire_json_without_unset_optionals(
    tmp_path: Path,
) -> None:
    response = request(make_seeded_app(tmp_path), "GET", "/api/v1/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "default"
    assert body["revision"] == 1
    assert all(
        "icon" in button or "color" in button
        for page in body["pages"]
        for button in page["buttons"]
    )
    assert "null" not in response.text


def test_active_profile_returns_structured_not_found(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
    )

    response = request(app, "GET", "/api/v1/profile")

    assert response.status_code == 404
    assert response.json() == {
        "code": "PROFILE_NOT_FOUND",
        "message": "Profile not found",
        "retryable": False,
    }


def test_snapshot_returns_current_and_exact_historical_revision(tmp_path: Path) -> None:
    app = make_seeded_app(tmp_path)
    update = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
    )
    assert update.status_code == 200

    current = request(app, "GET", "/api/v1/profiles/default/snapshot")
    historical = request(
        app,
        "GET",
        "/api/v1/profiles/default/snapshot?revision=1",
    )

    assert current.status_code == 200
    assert current.json()["revision"] == 2
    assert current.json()["pages"][0]["buttons"][0]["title"] == "Atalho atualizado"
    assert historical.status_code == 200
    assert historical.json()["revision"] == 1
    assert historical.json()["pages"][0]["buttons"][0]["title"] == (
        "Atalho Ctrl+Shift+S"
    )


def test_snapshot_not_found_is_safe_for_profile_and_revision(tmp_path: Path) -> None:
    app = make_seeded_app(tmp_path)

    missing_profile = request(
        app,
        "GET",
        "/api/v1/profiles/missing/snapshot",
    )
    missing_revision = request(
        app,
        "GET",
        "/api/v1/profiles/default/snapshot?revision=99",
    )

    assert missing_profile.status_code == 404
    assert missing_revision.status_code == 404
    assert missing_profile.json()["code"] == "PROFILE_NOT_FOUND"
    assert missing_revision.json()["code"] == "PROFILE_REVISION_NOT_FOUND"
    assert all(
        set(response.json()) == {"code", "message", "retryable"}
        for response in [missing_profile, missing_revision]
    )


def test_snapshot_rejects_invalid_revision_with_sanitized_422(tmp_path: Path) -> None:
    response = request(
        make_seeded_app(tmp_path),
        "GET",
        "/api/v1/profiles/default/snapshot?revision=0",
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "retryable": False,
    }


def test_put_requires_expected_revision(tmp_path: Path) -> None:
    response = request(
        make_seeded_app(tmp_path),
        "PUT",
        "/api/v1/profiles/default",
        json_body=updated_profile_payload(),
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "retryable": False,
    }


def test_app_restart_keeps_user_edited_profile(tmp_path: Path) -> None:
    database_path = tmp_path / "streamdeck.sqlite3"
    first_app = create_app(Settings(database_path=database_path))
    updated = request(
        first_app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
    )
    assert updated.status_code == 200

    second_app = create_app(Settings(database_path=database_path))
    current = request(second_app, "GET", "/api/v1/profiles/default/snapshot")

    assert current.status_code == 200
    assert current.json()["revision"] == 2
    assert current.json()["pages"][0]["buttons"][0]["title"] == ("Atalho atualizado")


def test_broadcast_failure_does_not_hide_committed_update(tmp_path: Path) -> None:
    class FailingBroadcast:
        async def broadcast_profile_changed(
            self, _profile_id: str, _revision: int, *, reason: str
        ) -> None:
            raise RuntimeError(reason)

    app = make_seeded_app(tmp_path, websocket_manager=FailingBroadcast())
    response = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
    )

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert (
        request(app, "GET", "/api/v1/profiles/default/snapshot").json()["revision"] == 2
    )


def test_action_catalog_is_exactly_closed_and_contains_no_command_surface(
    tmp_path: Path,
) -> None:
    response = request(make_seeded_app(tmp_path), "GET", "/api/v1/actions")

    assert response.status_code == 200
    assert response.json() == {
        "actions": [
            {"type": "hotkey"},
            {"type": "key"},
            {"type": "media"},
            {"type": "text"},
            {"type": "url"},
            {"type": "application"},
        ]
    }
    assert "shell" not in response.text.lower()
    assert "command" not in response.text.lower()


def test_put_saves_next_revision_and_broadcasts_change(tmp_path: Path) -> None:
    class BroadcastSpy:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, str]] = []

        async def broadcast_profile_changed(
            self, profile_id: str, revision: int, *, reason: str
        ) -> None:
            self.calls.append((profile_id, revision, reason))

    manager = BroadcastSpy()
    app = make_seeded_app(tmp_path, websocket_manager=manager)

    response = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
    )

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert manager.calls == [("default", 2, "updated")]
    assert (
        request(app, "GET", "/api/v1/profiles/default/snapshot").json()["revision"] == 2
    )


def test_put_stale_revision_returns_409_without_mutation(tmp_path: Path) -> None:
    app = make_seeded_app(tmp_path)
    stale_payload = updated_profile_payload()

    response = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=99",
        json_body=stale_payload,
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "PROFILE_REVISION_CONFLICT",
        "message": "Profile revision conflict",
        "retryable": True,
    }
    unchanged = request(app, "GET", "/api/v1/profiles/default/snapshot")
    assert unchanged.status_code == 200
    assert unchanged.json()["revision"] == 1
    assert unchanged.json()["pages"][0]["buttons"][0]["title"] == (
        "Atalho Ctrl+Shift+S"
    )


def test_put_rejects_url_and_body_id_mismatch(tmp_path: Path) -> None:
    payload = load_profile_payload(profile_id="other")
    response = request(
        make_seeded_app(tmp_path),
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=payload,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_put_rejects_extra_fields_and_shell_action(tmp_path: Path) -> None:
    extra = load_profile_payload()
    extra["unexpected"] = "nope"
    shell = load_profile_payload()
    shell["pages"][0]["buttons"][0]["action"] = {
        "type": "shell",
        "command": "whoami",
    }
    app = make_seeded_app(tmp_path)

    extra_response = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=extra,
    )
    shell_response = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=shell,
    )

    assert extra_response.status_code == 422
    assert shell_response.status_code == 422
    assert (
        extra_response.json()
        == shell_response.json()
        == {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "retryable": False,
        }
    )
    assert "whoami" not in shell_response.text
    assert "command" not in shell_response.text.lower()


def test_errors_never_expose_secrets_paths_or_tracebacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = make_repository(tmp_path)
    secret = "token=super-secret"
    database_path = str(tmp_path / "private.sqlite3")

    def explode() -> None:
        raise RuntimeError(f"{secret} {database_path}")

    monkeypatch.setattr(repository, "get_active_profile", explode)
    app = create_app(Settings(database_path=database_path), repository=repository)

    response = request(app, "GET", "/api/v1/profile")

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "Internal server error",
        "retryable": False,
    }
    assert secret not in response.text
    assert database_path not in response.text
    assert "Traceback" not in response.text


def test_create_app_exposes_runtime_dependencies_on_state(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    manager = object()
    app = create_app(
        Settings(database_path=tmp_path / "unused.sqlite3"),
        repository=repository,
        websocket_manager=manager,
    )

    assert app.state.database is repository.database
    assert app.state.profile_repository is repository
    assert app.state.websocket_manager is manager


def test_put_requires_client_authentication_when_remote_auth_is_enabled(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(
            host="192.0.2.10",
            pairing_code="phase4-code",
            require_auth=True,
            tls_identities=("deck.example.test",),
            database_path=tmp_path / "streamdeck.sqlite3",
        )
    )
    unauthenticated = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {
        "code": "AUTH_REQUIRED",
        "message": "Authentication required",
        "retryable": False,
    }
    unauthenticated_read = request(
        app,
        "GET",
        "/api/v1/profiles/default/snapshot",
    )
    assert unauthenticated_read.status_code == 401
    assert unauthenticated_read.json() == unauthenticated.json()
    unauthenticated_actions = request(app, "GET", "/api/v1/actions")
    assert unauthenticated_actions.status_code == 401
    assert unauthenticated_actions.json() == unauthenticated.json()

    claim = request(
        app,
        "POST",
        "/api/v1/pairing/claim",
        json_body={
            "client_id": "android",
            "client_version": "0.2.0",
            "pairing_code": "phase4-code",
        },
    )
    assert claim.status_code == 200
    token = claim.json()["access_token"]
    authenticated = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
        headers={
            "Authorization": f"Bearer {token}",
            "X-StreamDeck-Client-Id": "android",
        },
    )

    assert authenticated.status_code == 200
    assert authenticated.json()["revision"] == 2
    authenticated_read = request(
        app,
        "GET",
        "/api/v1/profiles/default/snapshot",
        headers={
            "Authorization": f"Bearer {token}",
            "X-StreamDeck-Client-Id": "android",
        },
    )
    assert authenticated_read.status_code == 200


def test_profile_audit_exposes_revision_metadata_without_snapshot_content(
    tmp_path: Path,
) -> None:
    app = make_seeded_app(tmp_path)
    update = request(
        app,
        "PUT",
        "/api/v1/profiles/default?expected_revision=1",
        json_body=updated_profile_payload(),
    )
    assert update.status_code == 200

    response = request(app, "GET", "/api/v1/profiles/default/audit")

    assert response.status_code == 200
    assert response.json()["profile_id"] == "default"
    entries = response.json()["entries"]
    assert [entry["revision"] for entry in entries] == [1, 2]
    assert [entry["reason"] for entry in entries] == ["created", "updated"]
    assert all(set(entry) == {"revision", "reason", "created_at"} for entry in entries)
    assert "snapshot_json" not in response.text
    assert "Atalho atualizado" not in response.text


def test_profile_audit_missing_profile_is_sanitized(tmp_path: Path) -> None:
    response = request(
        make_seeded_app(tmp_path),
        "GET",
        "/api/v1/profiles/missing/audit",
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "PROFILE_NOT_FOUND",
        "message": "Profile not found",
        "retryable": False,
    }


def test_profile_crud_http_routes_are_revision_guarded_and_explicit(
    tmp_path: Path,
) -> None:
    app = make_seeded_app(tmp_path)
    created_payload = load_profile_payload(profile_id="work")

    listed = request(app, "GET", "/api/v1/profiles")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["profiles"]] == ["default"]

    created = request(
        app,
        "POST",
        "/api/v1/profiles",
        json_body=created_payload,
    )
    assert created.status_code == 200
    assert created.json()["id"] == "work"
    assert created.json()["revision"] == 1

    renamed = request(
        app,
        "PATCH",
        "/api/v1/profiles/work?expected_revision=1",
        json_body={"name": "Trabalho"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Trabalho"
    assert renamed.json()["revision"] == 2

    stale = request(
        app,
        "PATCH",
        "/api/v1/profiles/work?expected_revision=1",
        json_body={"name": "Não sobrescrever"},
    )
    assert stale.status_code == 409
    assert stale.json() == {
        "code": "PROFILE_REVISION_CONFLICT",
        "message": "Profile revision conflict",
        "retryable": True,
    }

    duplicated = request(
        app,
        "POST",
        "/api/v1/profiles/work/duplicate?expected_revision=2",
        json_body={"id": "copy", "name": "Cópia"},
    )
    assert duplicated.status_code == 200
    assert duplicated.json()["id"] == "copy"
    assert duplicated.json()["revision"] == 1

    activated = request(
        app,
        "POST",
        "/api/v1/profiles/copy/activate?expected_revision=1",
    )
    assert activated.status_code == 200
    assert activated.json()["revision"] == 2
    assert request(app, "GET", "/api/v1/profile").json()["id"] == "copy"

    blocked = request(
        app,
        "DELETE",
        "/api/v1/profiles/copy?expected_revision=2",
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "PROFILE_DELETE_PROTECTED"

    deleted = request(
        app,
        "DELETE",
        "/api/v1/profiles/copy?expected_revision=2&replacement_profile_id=work",
    )
    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted_profile_id": "copy",
        "active_profile_id": "work",
    }


def test_page_crud_http_routes_validate_ids_orders_and_active_replacement(
    tmp_path: Path,
) -> None:
    app = make_seeded_app(tmp_path)
    new_page = {
        "id": "secondary",
        "title": "Secundária",
        "order": 1,
        "rows": 1,
        "columns": 1,
        "buttons": [
            {
                "id": "secondary-button",
                "row": 0,
                "column": 0,
                "title": "Ação",
                "action": {"type": "key", "key": "A"},
            }
        ],
    }

    created = request(
        app,
        "POST",
        "/api/v1/profiles/default/pages?expected_revision=1",
        json_body=new_page,
    )
    assert created.status_code == 200
    assert created.json()["revision"] == 2

    renamed = request(
        app,
        "PATCH",
        "/api/v1/profiles/default/pages/secondary?expected_revision=2",
        json_body={"title": "Secundária renomeada"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["revision"] == 3

    reordered = request(
        app,
        "POST",
        "/api/v1/profiles/default/pages/secondary/reorder?expected_revision=3",
        json_body={"order": 0},
    )
    assert reordered.status_code == 200
    assert [page["id"] for page in reordered.json()["pages"]] == [
        "secondary",
        "main",
    ]

    stale = request(
        app,
        "DELETE",
        "/api/v1/profiles/default/pages/main?expected_revision=3",
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "PROFILE_REVISION_CONFLICT"

    blocked = request(
        app,
        "DELETE",
        "/api/v1/profiles/default/pages/main?expected_revision=4",
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "PAGE_DELETE_PROTECTED"

    deleted = request(
        app,
        "DELETE",
        "/api/v1/profiles/default/pages/main?expected_revision=4&replacement_page_id=secondary",
    )
    assert deleted.status_code == 200
    assert deleted.json()["active_page_id"] == "secondary"
    assert deleted.json()["revision"] == 5


def test_phase5_mutation_payloads_are_closed_and_sanitized(tmp_path: Path) -> None:
    app = make_seeded_app(tmp_path)
    extra = request(
        app,
        "PATCH",
        "/api/v1/profiles/default?expected_revision=1",
        json_body={"name": "Novo", "shell": "whoami"},
    )
    assert extra.status_code == 422
    assert extra.json() == {
        "code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "retryable": False,
    }
    assert "whoami" not in extra.text
    assert "shell" not in extra.text.lower()

    invalid_order = request(
        app,
        "POST",
        "/api/v1/profiles/default/pages/main/reorder?expected_revision=1",
        json_body={"order": -1},
    )
    assert invalid_order.status_code == 422
    assert invalid_order.json()["code"] == "VALIDATION_ERROR"
