from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "dist" / "streamdeck-server.exe"


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(port: int, process: subprocess.Popen[bytes]) -> dict[str, str]:
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + 30.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("bundled server exited before health became available")
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload != {
                "status": "ok",
                "service": "android-streamdeck-server",
                "protocol_version": "0.1",
            }:
                raise RuntimeError("bundled server returned unexpected health metadata")
            return payload
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError("bundled server health timeout") from last_error


def _assert_port_released(port: int) -> None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            raise RuntimeError("bundled server left the smoke port listening")
    except OSError:
        return


def _stop_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            close_fds=True,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10.0)


def main() -> None:
    if not ARTIFACT.is_file():
        raise FileNotFoundError(f"build artifact not found: {ARTIFACT.name}")

    port = _free_loopback_port()
    with TemporaryDirectory(prefix="streamdeck-phase6-smoke-") as runtime_dir:
        environment = os.environ.copy()
        environment.update(
            {
                "STREAMDECK_HOST": "127.0.0.1",
                "STREAMDECK_PORT": str(port),
                "STREAMDECK_DATABASE_PATH": str(
                    Path(runtime_dir) / "streamdeck.sqlite3"
                ),
                "STREAMDECK_REQUIRE_AUTH": "false",
                "STREAMDECK_DISCOVERY_ENABLED": "false",
            }
        )
        environment.pop("STREAMDECK_PAIRING_CODE", None)
        process = subprocess.Popen(
            [str(ARTIFACT)],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
        )
        try:
            health = _wait_for_health(port, process)
        finally:
            _stop_owned_process(process)
        _assert_port_released(port)

    print(f"health={health['status']}; service={health['service']}; port_released=true")


if __name__ == "__main__":
    main()
