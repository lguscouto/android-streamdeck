from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.body_limit import MAX_WRITE_BODY_BYTES
from app.main import create_app
from app.resources import fixtures_dir

FIXTURE_PATH = fixtures_dir() / "profile-export-v1.json"


@pytest.fixture()
def client(tmp_path) -> TestClient:
    from app.config import Settings

    settings = Settings(
        database_path=tmp_path / "test.sqlite3",
        require_auth=False,
        discovery_enabled=False,
        tls_mode="disabled",
        log_dir=tmp_path / "logs",
    )
    app = create_app(settings)
    return TestClient(app)


def _valid_profile(*, profile_id: str, revision: int) -> dict[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["id"] = profile_id
    payload["revision"] = revision
    return payload


def _oversized_json(*, extra: int = 256) -> bytes:
    payload = _valid_profile(profile_id="big-profile", revision=1)
    payload["metadata"] = {"padding": "x" * (MAX_WRITE_BODY_BYTES + extra)}
    return json.dumps(payload).encode("utf-8")


def test_create_profile_rejects_body_over_global_cap(client: TestClient) -> None:
    response = client.post(
        "/api/v1/profiles",
        content=_oversized_json(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "PAYLOAD_TOO_LARGE"
    assert "x-streamdeck" not in json.dumps(body).lower()


def test_update_profile_rejects_body_over_global_cap(client: TestClient) -> None:
    created = client.post(
        "/api/v1/profiles", json=_valid_profile(profile_id="cap-profile", revision=1)
    )
    assert created.status_code == 200
    revision = created.json()["revision"]

    response = client.patch(
        f"/api/v1/profiles/cap-profile?expected_revision={revision}",
        content=_oversized_json(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_create_page_rejects_body_over_global_cap(client: TestClient) -> None:
    profile = _valid_profile(profile_id="page-cap", revision=1)
    created = client.post("/api/v1/profiles", json=profile)
    assert created.status_code == 200
    revision = created.json()["revision"]

    big_page = {
        "id": "big-page",
        "title": "Overflow",
        "order": 1,
        "buttons": [{"id": "b1", "title": "y", "row": 0, "column": 0}],
        "metadata": {"padding": "x" * (MAX_WRITE_BODY_BYTES + 512)},
    }
    response = client.post(
        f"/api/v1/profiles/page-cap/pages?expected_revision={revision}",
        content=json.dumps(big_page).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_normal_write_bodies_still_succeed(client: TestClient) -> None:
    response = client.post(
        "/api/v1/profiles", json=_valid_profile(profile_id="ok-profile", revision=1)
    )

    assert response.status_code == 200
    assert response.json()["id"] == "ok-profile"
