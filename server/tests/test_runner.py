import secrets

import uvicorn

from app.runner import main


def test_main_passes_environment_bind_settings_to_uvicorn(monkeypatch):
    pairing_code = f"test-{secrets.token_urlsafe(24)}"
    monkeypatch.setenv("STREAMDECK_HOST", "0.0.0.0")
    monkeypatch.setenv("STREAMDECK_PORT", "18766")
    monkeypatch.setenv("STREAMDECK_PAIRING_CODE", pairing_code)
    calls = []

    def fake_run(application, **kwargs):
        calls.append((application, kwargs))

    monkeypatch.setattr(uvicorn, "run", fake_run)

    main()

    assert len(calls) == 1
    application, kwargs = calls[0]
    assert application.state.settings.host == "0.0.0.0"
    assert application.state.settings.port == 18766
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 18766
