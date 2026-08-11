from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.repositories.profiles import ProfileRepository

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


class BroadcastSpy:
    def __init__(self) -> None:
        self.changes: list[tuple[str, int, str]] = []

    async def broadcast_profile_changed(
        self,
        profile_id: str,
        revision: int,
        *,
        reason: str,
    ) -> None:
        self.changes.append((profile_id, revision, reason))


def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_body: Any = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.request(method, path, json=json_body)

    return asyncio.run(send())


def _profile(profile_id: str) -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    return payload


def _seeded_app(tmp_path: Path, *, websocket_manager: Any) -> FastAPI:
    repository = ProfileRepository(Database(tmp_path / "streamdeck.sqlite3"))
    repository.initialize()
    repository.seed_profile(_profile("default"))
    return create_app(
        Settings(database_path=tmp_path / "streamdeck.sqlite3"),
        repository=repository,
        websocket_manager=websocket_manager,
    )


def test_activation_and_deletion_emit_revisioned_lifecycle_events(
    tmp_path: Path,
) -> None:
    broadcaster = BroadcastSpy()
    app = _seeded_app(tmp_path, websocket_manager=broadcaster)
    created = _request(app, "POST", "/api/v1/profiles", json_body=_profile("work"))
    assert created.status_code == 200
    broadcaster.changes.clear()

    activated = _request(
        app,
        "POST",
        "/api/v1/profiles/work/activate?expected_revision=1",
    )
    assert activated.status_code == 200
    assert activated.json()["revision"] == 2
    assert broadcaster.changes == [("work", 2, "updated")]

    broadcaster.changes.clear()
    deleted = _request(
        app,
        "DELETE",
        "/api/v1/profiles/work?expected_revision=2&replacement_profile_id=default",
    )
    assert deleted.status_code == 200
    assert broadcaster.changes == [
        ("work", 2, "deleted"),
        ("default", 2, "updated"),
    ]
