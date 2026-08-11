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

from defusedxml import ElementTree as ET

from app.db import Database
from app.pairing_session import (
    compute_client_proof,
    derive_pairing_key,
    derive_session_id,
)
from app.repositories.profiles import ProfileRepository
from app.schemas import Profile
from app.tls import TlsMaterialStore

EXPECTED_TEST_CLASSES = (
    "br.com.gustavo.streamdeck.OnboardingFlowInstrumentedTest",
    "br.com.gustavo.streamdeck.VisualGoldenInstrumentedTest",
    "br.com.gustavo.streamdeck.network.PairingFlowInstrumentedTest",
)
INSTRUMENTATION_SCREENSHOTS = (
    "pairing",
    "editor",
    "deck-main",
    "deck-secondary",
    "settings",
)
COMMON_ENVIRONMENT_KEYS = frozenset(
    {
        "APPDATA",
        "COMSPEC",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "NUMBER_OF_PROCESSORS",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
)
ANDROID_ENVIRONMENT_KEYS = COMMON_ENVIRONMENT_KEYS | {
    "ANDROID_HOME",
    "ANDROID_SDK_ROOT",
    "ANDROID_SERIAL",
    "ANDROID_USER_HOME",
    "GRADLE_USER_HOME",
    "JAVA_HOME",
}


def _allowlisted_environment(keys: frozenset[str]) -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key in keys}


def _adb_command(adb: Path, serial: str, *arguments: str) -> list[str]:
    return [str(adb), *(["-s", serial] if serial else []), *arguments]


def _push_instrumentation_fixture(
    adb: Path,
    serial: str,
    filename: str,
    payload: dict[str, str],
    environment: dict[str, str],
    host_directory: Path,
) -> None:
    host_fixture = host_directory / filename
    host_fixture.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    command = _adb_command(
        adb,
        serial,
        "push",
        str(host_fixture),
        f"/data/local/tmp/{filename}",
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=environment,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError("could not deliver the temporary Android fixture")
        chmod_result = subprocess.run(
            _adb_command(
                adb,
                serial,
                "shell",
                "chmod",
                "600",
                f"/data/local/tmp/{filename}",
            ),
            capture_output=True,
            check=False,
            env=environment,
            timeout=15,
        )
        if chmod_result.returncode != 0:
            raise RuntimeError("could not protect the temporary Android fixture")
    finally:
        host_fixture.unlink(missing_ok=True)


def _remove_instrumentation_fixture(
    adb: Path,
    serial: str,
    filename: str,
    environment: dict[str, str],
) -> None:
    result = subprocess.run(
        _adb_command(
            adb,
            serial,
            "shell",
            "rm",
            "-f",
            f"/data/local/tmp/{filename}",
        ),
        capture_output=True,
        check=False,
        env=environment,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError("temporary Android fixture cleanup failed")
    check = subprocess.run(
        _adb_command(
            adb,
            serial,
            "shell",
            "test",
            "!",
            "-e",
            f"/data/local/tmp/{filename}",
        ),
        capture_output=True,
        check=False,
        env=environment,
        timeout=15,
    )
    if check.returncode != 0:
        raise RuntimeError("temporary Android fixture remained on the device")


def _assert_android_artifacts_removed(
    adb: Path,
    serial: str,
    environment: dict[str, str],
) -> None:
    for name in INSTRUMENTATION_SCREENSHOTS:
        result = subprocess.run(
            _adb_command(
                adb,
                serial,
                "shell",
                "test",
                "!",
                "-e",
                f"/sdcard/streamdeck-golden-{name}.png",
            ),
            capture_output=True,
            check=False,
            env=environment,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError("instrumentation screenshot cleanup failed")


def _remove_android_artifacts(
    adb: Path,
    serial: str,
    environment: dict[str, str],
) -> None:
    for name in INSTRUMENTATION_SCREENSHOTS:
        result = subprocess.run(
            _adb_command(
                adb,
                serial,
                "shell",
                "rm",
                "-f",
                f"/sdcard/streamdeck-golden-{name}.png",
            ),
            capture_output=True,
            check=False,
            env=environment,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError("instrumentation screenshot cleanup command failed")


def _assert_instrumentation_executed(android_root: Path, started_at: float) -> None:
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    reports = [
        path
        for path in report_dir.rglob("*.xml")
        if path.is_file() and path.stat().st_mtime > started_at
    ]
    testcases_by_class = {name: [] for name in EXPECTED_TEST_CLASSES}
    parse_errors: list[str] = []
    if not reports:
        raise RuntimeError("fresh instrumented test result XML was not produced")

    for report in reports:
        try:
            root = ET.parse(report).getroot()
        except ET.ParseError as exc:
            parse_errors.append(f"{report.name}: {exc}")
            continue
        required_attributes = ("tests", "failures", "errors", "skipped")
        missing_attributes = [
            attribute
            for attribute in required_attributes
            if attribute not in root.attrib
        ]
        if missing_attributes:
            raise RuntimeError(
                f"instrumented XML {report.name} misses attributes: "
                + ", ".join(missing_attributes)
            )
        all_testcases = list(root.iter("testcase"))
        try:
            counts = {
                attribute: int(root.attrib[attribute])
                for attribute in required_attributes
            }
        except ValueError as exc:
            raise RuntimeError(
                f"instrumented XML {report.name} has invalid counts"
            ) from exc
        if counts["tests"] != len(all_testcases):
            raise RuntimeError(
                f"instrumented XML {report.name} has inconsistent test count"
            )
        observed_failures = sum(
            testcase.find("failure") is not None for testcase in all_testcases
        )
        observed_errors = sum(
            testcase.find("error") is not None for testcase in all_testcases
        )
        observed_skips = sum(
            testcase.find("skipped") is not None for testcase in all_testcases
        )
        if counts["failures"] != observed_failures:
            raise RuntimeError(
                f"instrumented XML {report.name} has inconsistent failure count"
            )
        if counts["errors"] != observed_errors:
            raise RuntimeError(
                f"instrumented XML {report.name} has inconsistent error count"
            )
        if counts["skipped"] != observed_skips:
            raise RuntimeError(
                f"instrumented XML {report.name} has inconsistent skip count"
            )
        for testcase in all_testcases:
            classname = testcase.attrib.get("classname")
            if classname not in testcases_by_class:
                raise RuntimeError(
                    f"unexpected instrumented test class in XML: {classname!r}"
                )
            testcases_by_class[classname].append(testcase)

    if parse_errors:
        raise RuntimeError("invalid instrumented XML: " + "; ".join(parse_errors))

    missing_or_duplicated = [
        name for name, testcases in testcases_by_class.items() if len(testcases) != 1
    ]
    if missing_or_duplicated:
        raise RuntimeError(
            "expected instrumented test result XML was missing or duplicated: "
            + ", ".join(missing_or_duplicated)
        )

    for name, testcases in testcases_by_class.items():
        testcase = testcases[0]
        failed = testcase.find("failure") is not None
        errored = testcase.find("error") is not None
        skipped = testcase.find("skipped") is not None
        if failed or errored or skipped:
            raise RuntimeError(
                f"{name} was not executed without failures or skips: "
                f"failure={failed}, error={errored}, skipped={skipped}"
            )


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


def _create_local_session(
    port: int,
    ca_certificate_path: Path,
    admin_code: str,
) -> dict[str, str]:
    context = ssl.create_default_context(cafile=str(ca_certificate_path))
    connection = http.client.HTTPSConnection(
        "localhost", port, context=context, timeout=5
    )
    try:
        connection.request(
            "POST",
            "/api/v1/local/pairing-session",
            headers={"x-streamdeck-admin-code": admin_code},
        )
        response = connection.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        if response.status != 200:
            raise RuntimeError("local pairing session creation failed")
        return body
    finally:
        connection.close()


def _https_json(
    port: int,
    ca_certificate_path: Path,
    method: str,
    path: str,
    payload: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    context = ssl.create_default_context(cafile=str(ca_certificate_path))
    connection = http.client.HTTPSConnection(
        "localhost", port, context=context, timeout=5
    )
    try:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw_body = response.read().decode("utf-8")
        return response.status, json.loads(raw_body)
    finally:
        connection.close()


def _run_protocol_matrix(
    port: int,
    ca_certificate_path: Path,
    admin_code: str,
) -> None:
    rotated_session = _create_local_session(port, ca_certificate_path, admin_code)
    session = _create_local_session(port, ca_certificate_path, admin_code)
    rotated_status, _ = _https_json(
        port,
        ca_certificate_path,
        "GET",
        f"/api/v1/pairing/bootstrap?session_id={rotated_session['session_id']}",
    )
    if rotated_status != 410:
        raise RuntimeError("regenerated pairing session was not invalidated")
    secret = str(session["pairing_code"])
    session_id = str(session["session_id"])
    status, bootstrap = _https_json(
        port,
        ca_certificate_path,
        "GET",
        f"/api/v1/pairing/bootstrap?session_id={session_id}",
    )
    if status != 200 or bootstrap.get("session_id") != session_id:
        raise RuntimeError("valid pairing bootstrap failed")
    salt = str(bootstrap["salt"])
    salt_bytes = base64.urlsafe_b64decode(salt + "=" * (-len(salt) % 4))
    pairing_key = derive_pairing_key(secret, salt_bytes)
    wrong_key = derive_pairing_key("B" * 26, salt_bytes)
    wrong_password_payload = {
        "client_id": "android-e2e",
        "client_version": "0.1.0",
        "session_id": session_id,
        "client_proof": compute_client_proof(
            wrong_key,
            session_id=session_id,
            client_id="android-e2e",
            client_version="0.1.0",
        ),
    }
    wrong_password_status, _ = _https_json(
        port,
        ca_certificate_path,
        "POST",
        "/api/v1/pairing/claim",
        wrong_password_payload,
    )
    if wrong_password_status != 401:
        raise RuntimeError("wrong pairing password was not rejected")
    invalid_payload = {
        "client_id": "android-e2e",
        "client_version": "0.1.0",
        "session_id": session_id,
        "client_proof": "A" * 43,
    }
    invalid_status, _ = _https_json(
        port,
        ca_certificate_path,
        "POST",
        "/api/v1/pairing/claim",
        invalid_payload,
    )
    if invalid_status != 401:
        raise RuntimeError(f"invalid proof was not rejected: status={invalid_status}")
    proof = compute_client_proof(
        pairing_key,
        session_id=session_id,
        client_id="android-e2e",
        client_version="0.1.0",
    )
    valid_payload = {**invalid_payload, "client_proof": proof}
    valid_status, valid_body = _https_json(
        port,
        ca_certificate_path,
        "POST",
        "/api/v1/pairing/claim",
        valid_payload,
    )
    if valid_status != 200 or not valid_body.get("access_token"):
        raise RuntimeError("valid pairing claim failed")
    replay_status, _ = _https_json(
        port,
        ca_certificate_path,
        "POST",
        "/api/v1/pairing/claim",
        valid_payload,
    )
    if replay_status != 409:
        raise RuntimeError("pairing replay was not rejected")
    invalid_session = derive_session_id("B" * 26)
    unknown_status, _ = _https_json(
        port,
        ca_certificate_path,
        "GET",
        f"/api/v1/pairing/bootstrap?session_id={invalid_session}",
    )
    if unknown_status != 410:
        raise RuntimeError("unknown pairing session was not rejected")
    qr_uri = str(session["qr_uri"])
    if "streamdeck://pair/v1?" not in qr_uri or secret not in qr_uri:
        raise RuntimeError("server QR payload is invalid")


def _seed_visual_profile(database_path: Path, project_root: Path) -> None:
    """Seed an isolated two-page profile without changing shared fixtures."""
    fixture_path = (
        project_root / "shared" / "fixtures" / "essential-controls-profile.json"
    )
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
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get(
        "ANDROID_SDK_ROOT", ""
    )
    adb = Path(android_home) / "platform-tools" / "adb.exe"
    if not adb.is_file():
        raise RuntimeError("Android adb was not found")
    serial = os.environ.get("ANDROID_SERIAL", "").strip()
    adb_environment = _allowlisted_environment(ANDROID_ENVIRONMENT_KEYS)
    device_state = subprocess.run(
        _adb_command(adb, serial, "get-state"),
        capture_output=True,
        text=True,
        check=False,
        env=adb_environment,
        timeout=15,
    ).stdout.strip()
    if device_state != "device":
        raise RuntimeError("an online Android emulator/device is required")

    server_root = Path.cwd()
    project_root = server_root.parent
    android_root = project_root / "android"
    admin_code = secrets.token_urlsafe(24)
    port = 8765
    if not _port_is_released(port):
        raise RuntimeError("default Android pairing port 8765 is already in use")
    with tempfile.TemporaryDirectory(prefix="streamdeck-phase7-android-") as raw_root:
        root = Path(raw_root)
        tls_state_dir = root / "tls"
        database_path = root / "streamdeck.sqlite3"
        _seed_visual_profile(database_path, project_root)
        material = TlsMaterialStore(
            tls_state_dir,
            ("10.0.2.2", "localhost"),
        ).ensure()
        server_environment = _allowlisted_environment(COMMON_ENVIRONMENT_KEYS)
        server_environment.update(
            {
                # nosec B104: intentional 0.0.0.0 bind so the Android emulator
                # (10.0.2.2) can reach this disposable TLS test server.
                "STREAMDECK_HOST": "0.0.0.0",  # nosec B104
                "STREAMDECK_PORT": str(port),
                "STREAMDECK_DATABASE_PATH": str(database_path),
                "STREAMDECK_ADMIN_CODE": admin_code,
                "STREAMDECK_PAIRING_SERVER_IP": "10.0.2.2",
                "STREAMDECK_REQUIRE_AUTH": "true",
                "STREAMDECK_TLS_MODE": "required",
                "STREAMDECK_TLS_IDENTITIES": "10.0.2.2,localhost",
                "STREAMDECK_TLS_STATE_DIR": str(tls_state_dir),
                "STREAMDECK_DISCOVERY_ENABLED": "false",
                "STREAMDECK_ACTION_MODE": "recording",
                # Generous idle timeout: UI automation on a JIT-warmed emulator
                # can spend >60s between WebSocket messages, which the default
                # would otherwise treat as a dead session.
                "STREAMDECK_WEBSOCKET_IDLE_TIMEOUT": "300",
            }
        )
        server = subprocess.Popen(
            [sys.executable, "-m", "app.runner"],
            cwd=server_root,
            env=server_environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        fixture_name: str | None = None
        cleanup_errors: list[str] = []
        body_error: Exception | None = None
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

            _run_protocol_matrix(port, material.ca_certificate_path, admin_code)
            session = _create_local_session(
                port,
                material.ca_certificate_path,
                admin_code,
            )
            pairing_secret = session.get("pairing_code", "")
            server_ip = session.get("server_ip", "")
            if not pairing_secret or server_ip != "10.0.2.2":
                raise RuntimeError("local pairing session response is invalid")
            fixture_name = f"pairing-e2e-{secrets.token_hex(8)}.json"
            _push_instrumentation_fixture(
                adb,
                serial,
                fixture_name,
                {
                    "server_address": server_ip,
                    "pairing_secret": pairing_secret,
                    "pairing_qr_uri": str(session["qr_uri"]),
                },
                adb_environment,
                root,
            )
            gradle_environment = _allowlisted_environment(ANDROID_ENVIRONMENT_KEYS)
            command = [
                str(android_root / "gradlew.bat"),
                ":app:connectedDebugAndroidTest",
                f"-Pandroid.testInstrumentationRunnerArguments.class={','.join(EXPECTED_TEST_CLASSES)}",
                "-Pandroid.testInstrumentationRunnerArguments.pairingFixturePath="
                f"/data/local/tmp/{fixture_name}",
                "--console=plain",
                "--no-daemon",
            ]
            instrumentation_started_at = time.time()
            result = subprocess.run(
                command,
                cwd=android_root,
                env=gradle_environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Android HTTPS/WSS instrumentation failed: {result.returncode}"
                )
            _assert_instrumentation_executed(android_root, instrumentation_started_at)
        except Exception as exc:
            body_error = exc
        finally:
            try:
                _stop_process(server)
            except Exception as exc:
                cleanup_errors.append(f"server process: {exc}")
            try:
                if fixture_name is not None:
                    _remove_instrumentation_fixture(
                        adb,
                        serial,
                        fixture_name,
                        adb_environment,
                    )
            except Exception as exc:
                cleanup_errors.append(f"Android fixture: {exc}")
            try:
                _remove_android_artifacts(adb, serial, adb_environment)
            except Exception as exc:
                cleanup_errors.append(f"Android screenshots: {exc}")
            try:
                _assert_android_artifacts_removed(adb, serial, adb_environment)
            except Exception as exc:
                cleanup_errors.append(f"Android artifact verification: {exc}")
            if not _port_is_released(port):
                cleanup_errors.append("temporary HTTPS server port remained active")
    post_cleanup_errors = list(cleanup_errors)
    residual_paths = [
        path for path in (root, database_path, tls_state_dir) if path.exists()
    ]
    if residual_paths:
        post_cleanup_errors.append(
            "temporary E2E state remained: "
            + ", ".join(str(path) for path in residual_paths)
        )
    if not _port_is_released(port):
        post_cleanup_errors.append("temporary HTTPS server port remained active")
    if body_error is not None:
        if post_cleanup_errors:
            raise RuntimeError(
                "E2E body failed and cleanup was incomplete: "
                + "; ".join(post_cleanup_errors)
            ) from body_error
        raise body_error
    if post_cleanup_errors:
        raise RuntimeError("E2E cleanup failed: " + "; ".join(post_cleanup_errors))
    print("android_https_wss_e2e=ok; port_released=true; temporary_state_removed=true")


if __name__ == "__main__":
    main()
