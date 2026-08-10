from __future__ import annotations

from types import SimpleNamespace

import app.runner as runner


class FakePublisher:
    def __init__(self, settings: object, events: list[str]) -> None:
        self.settings = settings
        self.events = events

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


def test_runner_registers_and_unregisters_discovery_around_uvicorn(monkeypatch) -> None:
    events: list[str] = []
    settings = SimpleNamespace(host="127.0.0.1", port=8765, tls_required=False)
    publisher = FakePublisher(settings, events)

    monkeypatch.setattr(runner.Settings, "from_env", classmethod(lambda _cls: settings))
    monkeypatch.setattr(
        runner, "create_app", lambda received: (events.append("app"), received)[1]
    )
    monkeypatch.setattr(runner, "DiscoveryPublisher", lambda received: publisher)
    monkeypatch.setattr(
        runner.uvicorn,
        "run",
        lambda _application, **_kwargs: events.append("run"),
    )

    runner.main()

    assert events == ["app", "start", "run", "stop"]


def test_runner_keeps_server_available_when_optional_discovery_fails(
    monkeypatch, caplog
) -> None:
    events: list[str] = []
    settings = SimpleNamespace(host="127.0.0.1", port=8765, tls_required=False)

    class FailingPublisher:
        def __init__(self, _settings: object) -> None:
            events.append("publisher")

        def start(self) -> None:
            events.append("start")
            raise runner.DiscoveryError("pairing-code-must-not-leak")

        def stop(self) -> None:
            events.append("stop")

    monkeypatch.setattr(runner.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(
        runner, "create_app", lambda _settings: events.append("app") or object()
    )
    monkeypatch.setattr(runner, "DiscoveryPublisher", FailingPublisher)
    monkeypatch.setattr(
        runner.uvicorn,
        "run",
        lambda _application, **_kwargs: events.append("uvicorn"),
    )

    runner.main()

    assert events == ["app", "publisher", "start", "uvicorn", "stop"]
    assert "pairing-code-must-not-leak" not in caplog.text


def test_runner_unregisters_discovery_when_uvicorn_fails(monkeypatch) -> None:
    events: list[str] = []
    settings = SimpleNamespace(host="127.0.0.1", port=8765, tls_required=False)
    publisher = FakePublisher(settings, events)

    monkeypatch.setattr(runner.Settings, "from_env", classmethod(lambda _cls: settings))
    monkeypatch.setattr(runner, "create_app", lambda received: received)
    monkeypatch.setattr(runner, "DiscoveryPublisher", lambda received: publisher)

    def fail_run(_application, **_kwargs):
        events.append("run")
        raise RuntimeError("synthetic uvicorn failure")

    monkeypatch.setattr(runner.uvicorn, "run", fail_run)

    try:
        runner.main()
    except RuntimeError as exc:
        assert str(exc) == "synthetic uvicorn failure"
    else:
        raise AssertionError("runner should propagate uvicorn failure")

    assert events == ["start", "run", "stop"]
