from __future__ import annotations

from typing import Any

import scripts.smoke_windows_bundle as smoke_windows_bundle


class ExitedProcess:
    pid = 43210
    returncode = 0

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


def test_stop_owned_process_does_not_kill_exited_windows_parent(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> None:
        calls.append((command, kwargs))

    monkeypatch.setattr(smoke_windows_bundle.os, "name", "nt")
    monkeypatch.setattr(smoke_windows_bundle.subprocess, "run", fake_run)

    smoke_windows_bundle._stop_owned_process(ExitedProcess())

    assert calls == []


def test_gpu_ack_validator_accepts_only_public_gpu_grammar() -> None:
    assert smoke_windows_bundle._is_gpu_ack_message(
        "GPU: 61°C | VRAM: 2.0/8.0 GB (25%)"
    )
    assert smoke_windows_bundle._is_gpu_ack_message("GPU: N/A | VRAM: N/A")
    assert not smoke_windows_bundle._is_gpu_ack_message("token=internal-path")
