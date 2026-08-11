from __future__ import annotations

import base64
import copy
import http.client
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.db import Database
from app.repositories.profiles import ProfileRepository
from app.schemas import Profile
from app.tls import TlsMaterialStore

TEST_CLASS = "br.com.gustavo.streamdeck.network.PairingFlowInstrumentedTest"


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


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


def _health(port: int, ca_certificate_path: Path) -> bool:
    context = ssl.create_default_context(cafile=str(ca_certificate_path))
    connection = http.client.HTTPSConnection(
        "localhost", port, context=context, timeout=1
    )
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and body.get("status") == "ok"
    finally:
        connection.close()


def _seed_visual_profile(database_path: Path, project_root: Path) -> None:
    """Seed an isolated two-page profile without changing shared fixtures."""
    fixture_path = project_root / "shared" / "fixtures" / "default-profile.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    secondary = copy.deepcopy(payload["pages"][0])
    secondary["id"] = "secondary"
    secondary["title"] = "Secundária"
    secondary["order"] = 1
    for button in secondary["buttons"]:
        button["id"] = f"secondary-{button['id']}"
        button["title"] = f"Secundária · {button['title']}"
    payload["pages"].append(secondary)
    profile = Profile.model_validate(payload)
    database = Database(database_path)
    repository = ProfileRepository(database)
    repository.initialize()
    repository.seed_profile(profile)
    database.close()


def main() -> None:
    android_home = os.environ.get("ANDROID_HOME", "")
    adb = Path(android_home) / "platform-tools" / "adb.exe"
    if not adb.is_file():
        raise RuntimeError("Android adb was not found")
    device_state = subprocess.run(
        [str(adb), "get-state"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if device_state != "device":
        raise RuntimeError("an online Android emulator/device is required")

    server_root = Path.cwd()
    project_root = server_root.parent
    android_root = project_root / "android"
    pairing_code = f"phase7-e2e-{secrets.token_hex(8)}"
    port = _available_port()
    with tempfile.TemporaryDirectory(prefix="streamdeck-phase7-android-") as raw_root:
        root = Path(raw_root)
        tls_state_dir = root / "tls"
        database_path = root / "streamdeck.sqlite3"
        _seed_visual_profile(database_path, project_root)
        material = TlsMaterialStore(
            tls_state_dir,
            ("10.0.2.2", "localhost"),
        ).ensure()
        ca_pem = material.ca_certificate_path.read_text(encoding="ascii")
        environment = os.environ.copy()
        environment.update(
            {
                # nosec B104: intentional 0.0.0.0 bind so the Android emulator
                # (10.0.2.2) can reach this disposable TLS test server.
                "STREAMDECK_HOST": "0.0.0.0",  # nosec B104
                "STREAMDECK_PORT": str(port),
                "STREAMDECK_DATABASE_PATH": str(database_path),
                "STREAMDECK_PAIRING_CODE": pairing_code,
                "STREAMDECK_REQUIRE_AUTH": "true",
                "STREAMDECK_TLS_MODE": "required",
                "STREAMDECK_TLS_IDENTITIES": "10.0.2.2,localhost",
                "STREAMDECK_TLS_STATE_DIR": str(tls_state_dir),
                "STREAMDECK_DISCOVERY_ENABLED": "false",
                # Generous idle timeout: UI automation on a JIT-warmed emulator
                # can spend >60s between WebSocket messages, which the default
                # would otherwise treat as a dead session.
                "STREAMDECK_WEBSOCKET_IDLE_TIMEOUT": "300",
            }
        )
        server = subprocess.Popen(
            [sys.executable, "-m", "app.runner"],
            cwd=server_root,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if material.ca_certificate_path.is_file():
                    try:
                        if _health(port, material.ca_certificate_path):
                            break
                    except (
                        ConnectionError,
                        OSError,
                        ssl.SSLError,
                        json.JSONDecodeError,
                    ):
                        pass
                time.sleep(0.2)
            else:
                raise RuntimeError("temporary HTTPS server did not become ready")

            ca_base64 = base64.b64encode(ca_pem.encode("ascii")).decode("ascii")
            command = [
                str(android_root / "gradlew.bat"),
                ":app:connectedDebugAndroidTest",
                f"-Pandroid.testInstrumentationRunnerArguments.class={TEST_CLASS}",
                f"-Pandroid.testInstrumentationRunnerArguments.serverAddress=https://10.0.2.2:{port}",
                f"-Pandroid.testInstrumentationRunnerArguments.pairingCode={pairing_code}",
                f"-Pandroid.testInstrumentationRunnerArguments.trustCode={material.trust_code}",
                f"-Pandroid.testInstrumentationRunnerArguments.caPemBase64={ca_base64}",
            ]
            result = subprocess.run(
                command,
                cwd=android_root,
                env=environment,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Android HTTPS/WSS instrumentation failed: {result.returncode}"
                )
        finally:
            _stop_process(server)
        if not _port_is_released(port):
            raise RuntimeError("temporary HTTPS server port remained active")
    print("android_https_wss_e2e=ok; port_released=true; temporary_state_removed=true")


if __name__ == "__main__":
    main()
