from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import Settings


class ProcessStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"


class ServerStartError(RuntimeError):
    """Raised when the owned server process cannot be started."""


ProcessFactory = Callable[..., Any]


def build_server_command(
    *,
    frozen: bool | None = None,
    executable: str | None = None,
    executable_dir: str | Path | None = None,
) -> tuple[str, ...]:
    """Build the only commands the local controller is allowed to launch."""
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if is_frozen:
        directory = Path(executable_dir or Path(sys.executable).resolve().parent)
        return (str(directory / "streamdeck-server.exe"),)
    return (executable or sys.executable, "-m", "app.runner")


class ServerProcessController:
    """Own the optional local server child process used by the Windows tray."""

    def __init__(
        self,
        settings: Settings,
        *,
        command: Sequence[str] | None = None,
        cwd: str | Path | None = None,
        process_factory: ProcessFactory = subprocess.Popen,
        stop_timeout_seconds: float = 5.0,
    ) -> None:
        selected_command = tuple(command or build_server_command())
        if not selected_command or any(
            not str(part).strip() for part in selected_command
        ):
            raise ValueError("server command must not be empty")
        if stop_timeout_seconds <= 0:
            raise ValueError("stop timeout must be positive")

        self.settings = settings
        self._command = selected_command
        self._cwd = Path(cwd) if cwd is not None else self._default_cwd()
        self._process_factory = process_factory
        self._stop_timeout_seconds = stop_timeout_seconds
        self._process: Any | None = None

    @staticmethod
    def _default_cwd() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]

    @property
    def status(self) -> ProcessStatus:
        process = self._process
        if process is not None and process.poll() is None:
            return ProcessStatus.RUNNING
        if process is not None:
            self._process = None
        return ProcessStatus.STOPPED

    @property
    def is_running(self) -> bool:
        return self.status is ProcessStatus.RUNNING

    def start(self) -> bool:
        """Start the owned server once; return False when it is already running."""
        if self.is_running:
            return False

        try:
            self._process = self._process_factory(
                list(self._command),
                cwd=str(self._cwd),
                env=self._child_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                **self._creation_flags(),
            )
        except OSError as exc:
            self._process = None
            raise ServerStartError("server process could not be started") from exc
        return True

    def stop(self) -> bool:
        """Stop only the process owned by this controller."""
        process = self._process
        if process is None or process.poll() is not None:
            self._process = None
            return False

        process.terminate()
        try:
            process.wait(timeout=self._stop_timeout_seconds)
        except (subprocess.TimeoutExpired, TimeoutError):
            process.kill()
            process.wait(timeout=self._stop_timeout_seconds)
        finally:
            self._process = None
        return True

    def _child_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["STREAMDECK_HOST"] = self.settings.host
        environment["STREAMDECK_PORT"] = str(self.settings.port)
        environment["STREAMDECK_DATABASE_PATH"] = str(self.settings.database_path)
        environment["STREAMDECK_REQUIRE_AUTH"] = (
            "true" if self.settings.require_auth else "false"
        )
        if self.settings.pairing_code is None:
            environment.pop("STREAMDECK_PAIRING_CODE", None)
        else:
            environment["STREAMDECK_PAIRING_CODE"] = self.settings.pairing_code

        discovery_enabled = getattr(self.settings, "discovery_enabled", False)
        discovery_name = getattr(self.settings, "discovery_name", None)
        environment["STREAMDECK_DISCOVERY_ENABLED"] = (
            "true" if discovery_enabled else "false"
        )
        if discovery_name:
            environment["STREAMDECK_DISCOVERY_NAME"] = discovery_name
        else:
            environment.pop("STREAMDECK_DISCOVERY_NAME", None)
        return environment

    @staticmethod
    def _creation_flags() -> dict[str, int]:
        if os.name == "nt":
            return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
        return {}


__all__ = [
    "ProcessStatus",
    "ServerProcessController",
    "ServerStartError",
    "build_server_command",
]
