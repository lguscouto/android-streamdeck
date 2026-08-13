from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "dist" / "streamdeck-server.exe"
TRAY_ARTIFACT = ROOT / "dist" / "streamdeck-tray.exe"


def _taskkill_command(pid: int) -> list[str]:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return [
        str(Path(system_root) / "System32" / "taskkill.exe"),
        "/PID",
        str(pid),
        "/T",
        "/F",
    ]


GPU_ACK_PATTERN = re.compile(
    r"^GPU: (?:N/A|-?\d{1,3}°C) \| VRAM: "
    r"(?:N/A|\d+(?:\.\d)?/\d+(?:\.\d)? GB \(\d{1,3}%\))$"
)


def _is_gpu_ack_message(message: object) -> bool:
    return isinstance(message, str) and GPU_ACK_PATTERN.fullmatch(message) is not None


def _assert_bundle_contents() -> None:
    """Check the frozen archive, not just the process health endpoint."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller.utils.cliutils.archive_viewer",
            "-r",
            "-b",
            "-l",
            str(ARTIFACT),
        ],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    listing = result.stdout.casefold()
    required = (
        "third-party-notices.md",
        "licenses\\mpl-2.0.txt",
        "licenses\\third-party-dotnet.md",
        "app\\native\\streamdeck_gpu_bridge.dll",
        "app\\native\\librehardwaremonitorlib.dll",
        "monoposixhelper.dll",
        "libmonoposixhelper.dll",
        "pynvml",
    )
    missing = [item for item in required if item not in listing]
    if missing:
        raise RuntimeError("frozen bundle is missing: " + ", ".join(missing))


async def _smoke_gpu_websocket(port: int) -> str:
    """Press the built-in GPU button through the public WebSocket contract."""
    import websockets

    endpoint = f"ws://127.0.0.1:{port}/api/v1/ws"
    async with websockets.connect(
        endpoint, open_timeout=10, close_timeout=5
    ) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "protocol_version": 1,
                    "type": "hello",
                    "payload": {
                        "client_id": "windows-bundle-smoke",
                        "client_version": "0.1.0",
                        "supported_protocol_versions": [1],
                    },
                }
            )
        )
        welcome = json.loads(await websocket.recv())
        snapshot = json.loads(await websocket.recv())
        if (
            welcome.get("type") != "welcome"
            or snapshot.get("type") != "profile_snapshot"
        ):
            raise RuntimeError(
                "bundled WebSocket handshake returned an unexpected message"
            )

        profile = snapshot["payload"]["profile"]
        gpu_button = next(
            (
                button
                for page in profile["pages"]
                for button in page["buttons"]
                if button.get("id") == "system-gpu"
            ),
            None,
        )
        if gpu_button is None:
            raise RuntimeError("bundled profile does not contain the system-gpu button")

        await websocket.send(
            json.dumps(
                {
                    "protocol_version": 1,
                    "type": "press",
                    "payload": {
                        "request_id": "windows-bundle-gpu",
                        "profile_id": profile["id"],
                        "page_id": profile["active_page_id"],
                        "button_id": gpu_button["id"],
                        "revision": profile["revision"],
                    },
                }
            )
        )
        acknowledgement = json.loads(await websocket.recv())
        payload = acknowledgement.get("payload", {})
        if acknowledgement.get("type") != "ack" or payload.get("status") != "completed":
            raise RuntimeError(
                f"bundled GPU press was not completed: {acknowledgement}"
            )
        message = payload.get("message")
        if not _is_gpu_ack_message(message):
            raise RuntimeError("bundled GPU ACK did not match the public grammar")
        return str(message)


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
            # nosec B310: loopback host only (127.0.0.1 ephemeral port), no
            # file:// or custom schemes reachable from this harness.
            with urllib.request.urlopen(url, timeout=1.0) as response:  # nosec B310
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


def _http_json(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        # nosec B310: requests target the ephemeral loopback harness only.
        with urllib.request.urlopen(request, timeout=5.0) as response:  # nosec B310
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def _assert_port_released(port: int) -> None:
    deadline = time.monotonic() + 10.0
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                last_error = RuntimeError("port is still accepting connections")
        except OSError:
            return
        time.sleep(0.25)
    raise RuntimeError("bundled server left the smoke port listening") from last_error


def _stop_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            _taskkill_command(process.pid),
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


def _visible_window_titles_for_process(process_id: int) -> list[str]:
    """Return visible top-level window titles owned by a Windows process."""
    if os.name != "nt":
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    enum_windows = user32.EnumWindows
    enum_windows.argtypes = [callback_type, wintypes.LPARAM]
    enum_windows.restype = wintypes.BOOL
    get_window_thread_process_id = user32.GetWindowThreadProcessId
    get_window_thread_process_id.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    get_window_thread_process_id.restype = wintypes.DWORD
    is_window_visible = user32.IsWindowVisible
    is_window_visible.argtypes = [wintypes.HWND]
    is_window_visible.restype = wintypes.BOOL
    get_window_text_length = user32.GetWindowTextLengthW
    get_window_text_length.argtypes = [wintypes.HWND]
    get_window_text_length.restype = ctypes.c_int
    get_window_text = user32.GetWindowTextW
    get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    get_window_text.restype = ctypes.c_int

    titles: list[str] = []

    @callback_type
    def callback(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        if not is_window_visible(hwnd):
            return True
        owner = wintypes.DWORD()
        get_window_thread_process_id(hwnd, ctypes.byref(owner))
        if owner.value != process_id:
            return True
        length = get_window_text_length(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        get_window_text(hwnd, buffer, length + 1)
        titles.append(buffer.value)
        return True

    enum_windows(callback, 0)
    return titles


def _smoke_tray_bundle() -> None:
    """Start the tray with a valid port and reject exception dialogs."""
    if not TRAY_ARTIFACT.is_file():
        raise FileNotFoundError(f"build artifact not found: {TRAY_ARTIFACT.name}")

    port = _free_loopback_port()
    with TemporaryDirectory(prefix="streamdeck-tray-smoke-") as runtime_dir:
        environment = os.environ.copy()
        environment.update(
            {
                "STREAMDECK_HOST": "127.0.0.1",
                "STREAMDECK_PORT": str(port),
                "STREAMDECK_DATABASE_PATH": str(
                    Path(runtime_dir) / "streamdeck.sqlite3"
                ),
                "STREAMDECK_LOG_DIR": str(Path(runtime_dir) / "logs"),
                "STREAMDECK_REQUIRE_AUTH": "false",
                "STREAMDECK_DISCOVERY_ENABLED": "false",
            }
        )
        environment.pop("STREAMDECK_PAIRING_CODE", None)
        process = subprocess.Popen(
            [str(TRAY_ARTIFACT)],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
        )
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"bundled tray exited before startup: {process.returncode}"
                    )
                exception_titles = [
                    title
                    for title in _visible_window_titles_for_process(process.pid)
                    if "Unhandled exception in script" in title
                ]
                if exception_titles:
                    raise RuntimeError(
                        "bundled tray opened an unhandled-exception dialog: "
                        + ", ".join(exception_titles)
                    )
                time.sleep(0.25)
        finally:
            _stop_owned_process(process)

    if Path(runtime_dir).exists():
        raise RuntimeError("bundled tray smoke left the temporary runtime directory")


def main() -> None:
    if not ARTIFACT.is_file():
        raise FileNotFoundError(f"build artifact not found: {ARTIFACT.name}")
    _assert_bundle_contents()

    base = f"http://127.0.0.1:{_free_loopback_port()}"
    port = int(base.rsplit(":", 1)[1])
    with TemporaryDirectory(prefix="streamdeck-phase8-smoke-") as runtime_dir:
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

            # Fresh databases install the built-in profile as the active profile;
            # there is no legacy ``default`` row anymore.
            builtin_profile_id = "essential-controls"
            status, exported = _http_json(
                "GET", f"{base}/api/v1/profiles/{builtin_profile_id}/export"
            )
            if status != 200:
                raise RuntimeError(
                    f"bundled export failed: status={status} body={exported}"
                )
            if exported.get("id") != builtin_profile_id:
                raise RuntimeError("bundled export returned unexpected profile id")

            # Import the exported wire payload as a fresh profile id at revision 1,
            # proving the frozen bundle can read the bundled schema during import.
            import_payload = dict(exported)
            import_payload["id"] = "smoke-import"
            import_payload["revision"] = 1
            status, imported = _http_json(
                "POST",
                f"{base}/api/v1/profiles/import",
                body=json.dumps(import_payload).encode("utf-8"),
            )
            if status != 200:
                raise RuntimeError(
                    f"bundled import failed: status={status} body={imported}"
                )
            if imported.get("id") != "smoke-import" or imported.get("revision") != 1:
                raise RuntimeError("bundled import returned unexpected profile state")
            gpu_message = asyncio.run(_smoke_gpu_websocket(port))
        finally:
            _stop_owned_process(process)

        _assert_port_released(port)

    if Path(runtime_dir).exists():
        raise RuntimeError("bundled smoke left the temporary runtime directory")

    print(
        "health={status}; export=ok; import=ok; gpu={gpu}; port_released=true; "
        "temporary_state_removed=true".format(status=health["status"], gpu=gpu_message)
    )
    _smoke_tray_bundle()
    print("tray=ok; no_exception_dialog=true; temporary_state_removed=true")


if __name__ == "__main__":
    main()
