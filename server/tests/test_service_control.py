from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import app.service_control as service_control
from app.config import Settings
from app.service_control import (
    ProcessStatus,
    ServerProcessController,
    build_server_command,
)


class FakeProcess:
    def __init__(self, *, running: bool = True) -> None:
        self.pid = 43210
        self.returncode = None if running else 0
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = 0

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.returncode is None:
            raise TimeoutError
        return self.returncode


def test_build_server_command_uses_fixed_module_in_source_mode() -> None:
    assert build_server_command(
        frozen=False,
        executable="python.exe",
        executable_dir=Path("C:/bundle"),
    ) == ("python.exe", "-m", "app.runner")


def test_build_server_command_uses_sibling_executable_when_frozen() -> None:
    command = build_server_command(
        frozen=True,
        executable="ignored.exe",
        executable_dir=Path("C:/bundle"),
    )

    assert len(command) == 1
    assert Path(command[0]) == Path("C:/bundle") / "streamdeck-server.exe"


def test_controller_starts_once_with_sanitized_fixed_environment() -> None:
    processes: list[FakeProcess] = []
    calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    def fake_popen(command: tuple[str, ...], **kwargs: Any) -> FakeProcess:
        calls.append((command, kwargs))
        process = FakeProcess()
        processes.append(process)
        return process

    settings = Settings(
        host="192.168.1.20",
        port=9000,
        database_path=Path("C:/runtime/streamdeck.sqlite3"),
        pairing_code="pairing-test",
        require_auth=True,
        discovery_enabled=True,
        discovery_name="Desk Test",
        tls_mode="required",
        tls_state_dir=Path("C:/runtime/tls"),
        tls_identities=("deck.example.test", "192.168.1.20"),
    )
    controller = ServerProcessController(
        settings,
        command=("server.exe",),
        cwd=Path("C:/bundle"),
        process_factory=fake_popen,
    )

    assert controller.start() is True
    assert controller.start() is False
    assert controller.status is ProcessStatus.RUNNING
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert tuple(command) == ("server.exe",)
    assert Path(kwargs["cwd"]) == Path("C:/bundle")
    assert kwargs["shell"] is False
    assert kwargs["env"]["STREAMDECK_HOST"] == "192.168.1.20"
    assert kwargs["env"]["STREAMDECK_PORT"] == "9000"
    assert Path(kwargs["env"]["STREAMDECK_DATABASE_PATH"]) == Path(
        "C:/runtime/streamdeck.sqlite3"
    )
    assert kwargs["env"]["STREAMDECK_PAIRING_CODE"] == "pairing-test"
    assert kwargs["env"]["STREAMDECK_REQUIRE_AUTH"] == "true"
    assert kwargs["env"]["STREAMDECK_DISCOVERY_ENABLED"] == "true"
    assert kwargs["env"]["STREAMDECK_DISCOVERY_NAME"] == "Desk Test"
    assert kwargs["env"]["STREAMDECK_TLS_MODE"] == "required"
    assert Path(kwargs["env"]["STREAMDECK_TLS_STATE_DIR"]) == Path("C:/runtime/tls")
    assert kwargs["env"]["STREAMDECK_TLS_IDENTITIES"] == (
        "deck.example.test,192.168.1.20"
    )


def test_controller_stop_is_idempotent_and_terminates_owned_process(
    monkeypatch,
) -> None:
    monkeypatch.setattr(service_control.os, "name", "posix")
    process = FakeProcess()

    controller = ServerProcessController(
        Settings(),
        command=("server.exe",),
        cwd="C:/bundle",
        process_factory=lambda *_args, **_kwargs: process,
    )

    assert controller.stop() is False
    assert controller.start() is True
    assert controller.stop() is True
    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert controller.status is ProcessStatus.STOPPED
    assert controller.stop() is False


def test_controller_stops_the_owned_process_tree_on_windows(monkeypatch) -> None:
    process = FakeProcess()
    taskkill_calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> None:
        taskkill_calls.append((command, kwargs))
        process.returncode = 0

    monkeypatch.setattr(service_control.os, "name", "nt")
    monkeypatch.setattr(service_control.subprocess, "run", fake_run)
    controller = ServerProcessController(
        Settings(),
        command=("server.exe",),
        cwd="C:/bundle",
        process_factory=lambda *_args, **_kwargs: process,
    )

    assert controller.start() is True
    assert controller.stop() is True

    assert taskkill_calls == [
        (
            [r"C:\Windows\System32\taskkill.exe", "/PID", "43210", "/T", "/F"],
            {
                "check": False,
                "stdout": service_control.subprocess.DEVNULL,
                "stderr": service_control.subprocess.DEVNULL,
            },
        )
    ]
    assert process.terminate_calls == 0


def test_controller_does_not_taskkill_an_already_exited_process(monkeypatch) -> None:
    process = FakeProcess(running=False)
    taskkill_calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> None:
        taskkill_calls.append((command, kwargs))

    monkeypatch.setattr(service_control.os, "name", "nt")
    monkeypatch.setattr(service_control.subprocess, "run", fake_run)
    controller = ServerProcessController(
        Settings(),
        command=("server.exe",),
        cwd="C:/bundle",
        process_factory=lambda *_args, **_kwargs: process,
    )

    assert controller.start() is True
    assert controller.status is ProcessStatus.STOPPED
    assert controller.stop() is False
    assert taskkill_calls == []


def test_controller_start_is_single_flight_under_concurrency() -> None:
    processes: list[FakeProcess] = []
    first_factory_call = threading.Event()
    release_factory = threading.Event()

    def fake_popen(_command: tuple[str, ...], **_kwargs: Any) -> FakeProcess:
        first_factory_call.set()
        assert release_factory.wait(timeout=2)
        process = FakeProcess()
        processes.append(process)
        return process

    controller = ServerProcessController(
        Settings(),
        command=("server.exe",),
        process_factory=fake_popen,
    )
    results: list[bool] = []

    def start_controller() -> None:
        results.append(controller.start())

    first = threading.Thread(target=start_controller)
    second = threading.Thread(target=start_controller)
    first.start()
    assert first_factory_call.wait(timeout=2)
    second.start()
    release_factory.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert sorted(results) == [False, True]
    assert len(processes) == 1


def test_controller_generates_internal_admin_code_for_child_without_static_code() -> (
    None
):
    calls: list[dict[str, Any]] = []

    def fake_popen(_command: tuple[str, ...], **kwargs: Any) -> FakeProcess:
        calls.append(kwargs)
        return FakeProcess()

    controller = ServerProcessController(
        Settings(require_auth=True),
        command=("server.exe",),
        process_factory=fake_popen,
    )

    controller.start()

    assert len(controller.admin_code) >= 32
    assert calls[0]["env"]["STREAMDECK_ADMIN_CODE"] == controller.admin_code
    assert "STREAMDECK_PAIRING_CODE" not in calls[0]["env"]
