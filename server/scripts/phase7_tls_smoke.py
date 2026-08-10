from __future__ import annotations

import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _health(port: int, ca_certificate_path: Path) -> dict[str, object]:
    context = ssl.create_default_context(cafile=str(ca_certificate_path))
    connection = http.client.HTTPSConnection(
        "localhost", port, context=context, timeout=1
    )
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"unexpected health status: {response.status}")
        return json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()


def _port_is_released(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        process.terminate()
    process.wait(timeout=10)


def main() -> None:
    server_root = Path(__file__).resolve().parents[1]
    port = _available_port()
    with tempfile.TemporaryDirectory(prefix="streamdeck-phase7-") as temporary_root:
        temporary_path = Path(temporary_root)
        tls_state_dir = temporary_path / "tls"
        environment = os.environ.copy()
        environment.update(
            {
                "STREAMDECK_HOST": "127.0.0.1",
                "STREAMDECK_PORT": str(port),
                "STREAMDECK_DATABASE_PATH": str(temporary_path / "streamdeck.sqlite3"),
                "STREAMDECK_PAIRING_CODE": "phase7-smoke-code",
                "STREAMDECK_REQUIRE_AUTH": "true",
                "STREAMDECK_TLS_MODE": "required",
                "STREAMDECK_TLS_IDENTITIES": "localhost",
                "STREAMDECK_TLS_STATE_DIR": str(tls_state_dir),
            }
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "app.runner"],
            cwd=server_root,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ca_certificate_path = tls_state_dir / "ca-cert.pem"
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if ca_certificate_path.is_file():
                    try:
                        body = _health(port, ca_certificate_path)
                    except (ConnectionError, OSError, ssl.SSLError):
                        time.sleep(0.1)
                    else:
                        if body == {
                            "status": "ok",
                            "service": "android-streamdeck-server",
                            "protocol_version": "0.1",
                        }:
                            break
                time.sleep(0.1)
            else:
                raise RuntimeError("TLS health endpoint did not become ready")
        finally:
            _stop_process(process)
        if not _port_is_released(port):
            raise RuntimeError("TLS smoke listener remained active")
    print("https_health=ok; port_released=true")


if __name__ == "__main__":
    main()
