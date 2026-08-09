import asyncio

import httpx
import pytest

from app.config import Settings
from app.main import create_app


def get_health_response(app: object) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get("/health")

    return asyncio.run(request())


def test_health_returns_only_sanitized_public_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STREAMDECK_HOST", "0.0.0.0")
    monkeypatch.setenv("STREAMDECK_PORT", "9876")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@example.invalid/db")
    monkeypatch.setenv("STREAMDECK_TOKEN", "do-not-return-this-token")

    response = get_health_response(create_app())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "android-streamdeck-server",
        "protocol_version": "0.1",
    }
    assert "secret" not in response.text
    assert "do-not-return-this-token" not in response.text
    assert "9876" not in response.text


def test_settings_use_safe_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAMDECK_HOST", raising=False)
    monkeypatch.delenv("STREAMDECK_PORT", raising=False)

    settings = Settings.from_env()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765


def test_settings_read_host_and_port_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STREAMDECK_HOST", "192.0.2.10")
    monkeypatch.setenv("STREAMDECK_PORT", "9000")

    settings = Settings.from_env()

    assert settings.host == "192.0.2.10"
    assert settings.port == 9000


def test_settings_reject_invalid_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMDECK_PORT", "not-a-port")

    with pytest.raises(ValueError, match="STREAMDECK_PORT"):
        Settings.from_env()
