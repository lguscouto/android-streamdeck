from __future__ import annotations

import runpy
import sys

import uvicorn


def test_runner_calls_main_when_executed_as_a_script(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("STREAMDECK_HOST", "127.0.0.1")
    monkeypatch.setenv("STREAMDECK_PORT", "18767")
    monkeypatch.setenv("STREAMDECK_DATABASE_PATH", str(tmp_path / "entrypoint.sqlite3"))
    monkeypatch.setenv("STREAMDECK_REQUIRE_AUTH", "false")
    monkeypatch.setenv("STREAMDECK_DISCOVERY_ENABLED", "false")
    monkeypatch.delenv("STREAMDECK_PAIRING_CODE", raising=False)
    def fake_run(_application, **kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.delitem(sys.modules, "app.runner", raising=False)

    runpy.run_module("app.runner", run_name="__main__")

    assert calls == [{"host": "127.0.0.1", "port": 18767}]
