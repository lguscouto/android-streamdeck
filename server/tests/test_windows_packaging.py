from __future__ import annotations

import os
from pathlib import Path

from app.windows_packaging import build_pyinstaller_command

PATHSEP = os.pathsep
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = PROJECT_ROOT / "server"


def _licenses(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    paths = tuple(
        tmp_path / name
        for name in (
            "THIRD-PARTY-NOTICES.md",
            "MPL-2.0.txt",
            "THIRD-PARTY-DOTNET.md",
            "Apache-2.0.txt",
            "MIT.txt",
        )
    )
    for path in paths:
        path.write_text("notice", encoding="utf-8")
    return paths  # type: ignore[return-value]


def test_server_bundle_command_is_console_and_contains_fixture_data() -> None:
    command = build_pyinstaller_command(
        target="server",
        root=SERVER_ROOT,
        executable="python.exe",
        output_dir=SERVER_ROOT / "dist",
        work_dir=SERVER_ROOT / "build",
    )

    assert command[:3] == ("python.exe", "-m", "PyInstaller")
    assert "--onefile" in command
    assert "--console" in command
    assert "--name" in command
    assert "streamdeck-server" in command
    assert "--collect-all" in command
    assert "zeroconf" in command
    assert "win32com" in command
    assert "--hidden-import" in command
    assert "pynvml" in command
    assert f"{SERVER_ROOT.as_posix()}/app/runner.py" in command
    assert (
        f"{PROJECT_ROOT.as_posix()}/shared/fixtures{PATHSEP}shared/fixtures" in command
    )
    assert (
        f"{PROJECT_ROOT.as_posix()}/shared/protocol{PATHSEP}shared/protocol" in command
    )
    assert "--distpath" in command
    assert SERVER_ROOT.as_posix() + "/dist" in command
    assert "--workpath" in command
    assert SERVER_ROOT.as_posix() + "/build" in command
    for filename, destination in (
        ("THIRD-PARTY-NOTICES.md", "."),
        ("MPL-2.0.txt", "LICENSES"),
        ("THIRD-PARTY-DOTNET.md", "LICENSES"),
        ("Apache-2.0.txt", "LICENSES"),
        ("MIT.txt", "LICENSES"),
    ):
        assert (
            f"{PROJECT_ROOT.as_posix()}/LICENSES/{filename}{PATHSEP}{destination}"
            in command
            or filename == "THIRD-PARTY-NOTICES.md"
        )


def test_server_bundle_command_bundles_every_shared_fixture() -> None:
    command = build_pyinstaller_command(
        target="server",
        root=SERVER_ROOT,
        executable="python.exe",
        output_dir=SERVER_ROOT / "dist",
        work_dir=SERVER_ROOT / "build",
    )
    fixture_data = [arg for arg in command if arg.endswith(f"{PATHSEP}shared/fixtures")]
    protocol_data = [
        arg for arg in command if arg.endswith(f"{PATHSEP}shared/protocol")
    ]

    assert fixture_data
    assert protocol_data


def test_tray_bundle_is_windowed_and_collects_optional_gui_dependencies() -> None:
    command = build_pyinstaller_command(
        target="tray",
        root=Path("E:/project/server"),
        executable="python.exe",
        output_dir=Path("E:/project/server/dist"),
        work_dir=Path("E:/project/server/build"),
    )

    assert "--windowed" in command
    assert "streamdeck-tray" in command
    assert "E:/project/server/app/tray.py" in command
    assert "--collect-all" in command
    assert "pystray" in command
    assert "PIL" in command
    assert "--hidden-import" in command
    assert "pystray._win32" in command


def test_server_bundle_places_gpu_binaries_and_notices_under_fixed_directories(
    tmp_path: Path,
) -> None:
    bridge = tmp_path / "streamdeck_gpu_bridge.dll"
    monitor = tmp_path / "LibreHardwareMonitorLib.dll"
    bridge.write_bytes(b"bridge")
    monitor.write_bytes(b"monitor")
    companions = []
    for name in ("MonoPosixHelper.dll", "libMonoPosixHelper.dll"):
        companion = tmp_path / name
        companion.write_bytes(b"companion")
        companions.append(companion)
    notices = _licenses(tmp_path)

    command = build_pyinstaller_command(
        target="server",
        root=Path("E:/project/server"),
        executable="python.exe",
        output_dir=Path("E:/project/server/dist"),
        work_dir=Path("E:/project/server/build"),
        gpu_bridge=bridge,
        librehardwaremonitor=monitor,
        gpu_native_binaries=companions,
        third_party_notices=notices[0],
        mpl_license=notices[1],
        dotnet_notices=notices[2],
        apache_license=notices[3],
        mit_license=notices[4],
    )

    assert f"{bridge.as_posix()}{PATHSEP}app/native" in command
    assert f"{monitor.as_posix()}{PATHSEP}app/native" in command
    for companion in companions:
        assert f"{companion.as_posix()}{PATHSEP}app/native" in command
    for notice in notices:
        assert any(notice.as_posix() in arg for arg in command)
