from __future__ import annotations

from pathlib import Path

from app.windows_packaging import build_pyinstaller_command


def test_server_bundle_command_is_console_and_contains_fixture_data() -> None:
    command = build_pyinstaller_command(
        target="server",
        root=Path("E:/project/server"),
        executable="python.exe",
        output_dir=Path("E:/project/server/dist"),
        work_dir=Path("E:/project/server/build"),
    )

    assert command[:3] == ("python.exe", "-m", "PyInstaller")
    assert "--onefile" in command
    assert "--console" in command
    assert "--name" in command
    assert "streamdeck-server" in command
    assert "--collect-all" in command
    assert "zeroconf" in command
    assert "E:/project/server/app/runner.py" in command
    assert "E:/project/shared/fixtures/default-profile.json;shared/fixtures" in command
    assert "--distpath" in command
    assert "E:/project/server/dist" in command
    assert "--workpath" in command
    assert "E:/project/server/build" in command


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
