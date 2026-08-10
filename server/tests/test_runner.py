import secrets

import uvicorn

from app.runner import main


def test_main_passes_tls_bind_settings_to_uvicorn(monkeypatch, tmp_path):
    pairing_code = f"test-{secrets.token_urlsafe(24)}"
    tls_state_dir = tmp_path / "tls"
    monkeypatch.setenv("STREAMDECK_HOST", "0.0.0.0")
    monkeypatch.setenv("STREAMDECK_PORT", "18766")
    monkeypatch.setenv("STREAMDECK_PAIRING_CODE", pairing_code)
    monkeypatch.setenv("STREAMDECK_TLS_IDENTITIES", "deck.example.test")
    monkeypatch.setenv("STREAMDECK_TLS_STATE_DIR", str(tls_state_dir))
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
    assert kwargs["ssl_certfile"] == str(tls_state_dir / "leaf-chain.pem")
    assert kwargs["ssl_keyfile"] == str(tls_state_dir / "leaf-key.pem")
