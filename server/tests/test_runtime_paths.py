from __future__ import annotations

from pathlib import Path

import app.config as config


def test_frozen_bundle_database_path_uses_local_app_data(monkeypatch) -> None:
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")

    assert config.default_database_path() == (
        Path(r"C:\Users\test\AppData\Local")
        / "AndroidStreamDeck"
        / "streamdeck.sqlite3"
    )


def test_tls_state_path_uses_local_app_data_in_source_mode(monkeypatch) -> None:
    monkeypatch.setattr(config.sys, "frozen", False, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")

    assert config.default_tls_state_dir() == (
        Path(r"C:\Users\test\AppData\Local") / "AndroidStreamDeck" / "tls"
    )
