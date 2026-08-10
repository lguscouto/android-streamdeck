"""Phase 10 — measure press→ack latency over the real authenticated WSS protocol.

Starts a disposable TLS server, pairs an ephemeral client, opens a WSS
connection, and measures N press→ack round trips. The measured value is an
observation of this machine/emulator, not a promise. No secrets are printed.
"""

from __future__ import annotations

import asyncio
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

import websockets

from app.tls import TlsMaterialStore

ROOT = Path(__file__).resolve().parents[1]
ITERATIONS = int(os.environ.get("PHASE10_LATENCY_ITERATIONS", "5"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _fetch_health(port: int, cafile: Path) -> bool:
    context = ssl.create_default_context(cafile=str(cafile))
    import http.client

    connection = http.client.HTTPSConnection(
        "localhost", port, context=context, timeout=2
    )
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        return response.status == 200
    finally:
        connection.close()


async def _claim_token(port: int, cafile: Path, pairing_code: str) -> tuple[str, str]:
    """Pair an ephemeral client over HTTPS and return (client_id, token)."""
    import http.client
    import ssl as ssl_module

    context = ssl_module.create_default_context(cafile=str(cafile))
    client_id = f"bench-{secrets.token_hex(6)}"
    connection = http.client.HTTPSConnection(
        "localhost", port, context=context, timeout=5
    )
    try:
        body = json.dumps(
            {
                "client_id": client_id,
                "client_version": "0.1.0",
                "pairing_code": pairing_code,
            }
        ).encode("utf-8")
        connection.request(
            "POST",
            "/api/v1/pairing/claim",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        if response.status != 200:
            raise RuntimeError(f"pairing claim failed: {response.status} {payload}")
        return client_id, str(payload["access_token"])
    finally:
        connection.close()


async def _benchmark(
    port: int,
    cafile: Path,
    pairing_code: str,
) -> dict[str, object]:
    context = ssl.create_default_context(cafile=str(cafile))
    endpoint = f"wss://localhost:{port}/api/v1/ws"
    latencies_ms: list[float] = []

    client_id, access_token = await _claim_token(port, cafile, pairing_code)

    async with websockets.connect(
        endpoint,
        ssl=context,
        open_timeout=10,
        close_timeout=5,
    ) as websocket:
        hello = {
            "protocol_version": 1,
            "type": "hello",
            "payload": {
                "client_id": client_id,
                "client_version": "0.1.0",
                "supported_protocol_versions": [1],
                "access_token": access_token,
            },
        }
        await websocket.send(json.dumps(hello))
        welcome = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        if welcome.get("type") != "welcome":
            raise RuntimeError(
                f"unexpected welcome {welcome.get('type')}: "
                f"{welcome.get('payload', {})}"
            )
        snapshot = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        if snapshot.get("type") != "profile_snapshot":
            raise RuntimeError(
                f"unexpected snapshot {snapshot.get('type')}: "
                f"{snapshot.get('payload', {})}"
            )
        profile = snapshot.get("payload", {}).get("profile", {})
        usable_buttons = [
            button
            for page in profile.get("pages", [])
            for button in page.get("buttons", [])
        ]
        if not usable_buttons:
            raise RuntimeError("profile has no buttons to press")
        button = usable_buttons[0]

        for iteration in range(ITERATIONS):
            request_id = f"bench-{iteration}"
            press = {
                "protocol_version": 1,
                "type": "press",
                "payload": {
                    "request_id": request_id,
                    "profile_id": profile["id"],
                    "page_id": profile["active_page_id"],
                    "button_id": button["id"],
                    "revision": profile["revision"],
                },
            }
            started = time.perf_counter()
            await websocket.send(json.dumps(press))
            message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(round(elapsed_ms, 1))
            if message.get("type") != "ack":
                raise RuntimeError(f"expected ack, got {message.get('type')}")

    latencies_ms.sort()
    return {
        "iterations": ITERATIONS,
        "min_ms": latencies_ms[0],
        "median_ms": latencies_ms[len(latencies_ms) // 2],
        "max_ms": latencies_ms[-1],
        "accepted_status": "ack-received",
        "note": "local TLS loopback; action outcome depends on the Windows runner",
    }


def main() -> int:
    port = _free_port()
    pairing_code = f"bench-{secrets.token_hex(6)}"
    with tempfile.TemporaryDirectory(prefix="streamdeck-phase10-latency-") as raw:
        root = Path(raw)
        tls_state_dir = root / "tls"
        material = TlsMaterialStore(tls_state_dir, ("localhost",)).ensure()
        environment = os.environ.copy()
        environment.update(
            {
                "STREAMDECK_HOST": "127.0.0.1",
                "STREAMDECK_PORT": str(port),
                "STREAMDECK_DATABASE_PATH": str(root / "streamdeck.sqlite3"),
                "STREAMDECK_PAIRING_CODE": pairing_code,
                "STREAMDECK_REQUIRE_AUTH": "true",
                "STREAMDECK_TLS_MODE": "required",
                "STREAMDECK_TLS_IDENTITIES": "localhost",
                "STREAMDECK_TLS_STATE_DIR": str(tls_state_dir),
                "STREAMDECK_DISCOVERY_ENABLED": "false",
            }
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "app.runner"],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    if _fetch_health(port, material.ca_certificate_path):
                        break
                except Exception:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError("temporary HTTPS server did not become ready")
            result = asyncio.run(
                _benchmark(port, material.ca_certificate_path, pairing_code)
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        finally:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        # case: server failed to become ready
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
