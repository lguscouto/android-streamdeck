from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

PackagingTarget = Literal["server", "tray"]

_TARGETS: dict[PackagingTarget, tuple[str, str, str]] = {
    "server": ("streamdeck-server", "app/runner.py", "--console"),
    "tray": ("streamdeck-tray", "app/tray.py", "--windowed"),
}


def _portable_path(path: Path) -> str:
    """Use slash-separated paths accepted by Windows command-line tools."""
    return path.as_posix()


def build_pyinstaller_command(
    *,
    target: PackagingTarget,
    root: str | Path,
    executable: str,
    output_dir: str | Path,
    work_dir: str | Path,
) -> tuple[str, ...]:
    """Build a deterministic PyInstaller command for a fixed project target."""
    try:
        name, script, window_mode = _TARGETS[target]
    except KeyError as exc:
        raise ValueError("unknown Windows packaging target") from exc

    project_root = Path(root)
    dist_path = Path(output_dir)
    build_path = Path(work_dir)
    shared_dir = project_root.parent / "shared"
    protocol_dir = shared_dir / "protocol"
    fixtures_dir = shared_dir / "fixtures"
    command = [
        executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        window_mode,
        "--name",
        name,
        "--distpath",
        _portable_path(dist_path),
        "--workpath",
        _portable_path(build_path),
        "--specpath",
        _portable_path(build_path),
        "--add-data",
        (f"{_portable_path(protocol_dir)}{os.pathsep}shared/protocol"),
        "--add-data",
        (f"{_portable_path(fixtures_dir)}{os.pathsep}shared/fixtures"),
    ]
    if target == "server":
        command.extend(["--collect-all", "zeroconf"])
    if target == "tray":
        command.extend(
            [
                "--collect-all",
                "pystray",
                "--collect-all",
                "PIL",
                "--hidden-import",
                "pystray._win32",
            ]
        )
    command.append(_portable_path(project_root / script))
    return tuple(command)


__all__ = ["PackagingTarget", "build_pyinstaller_command"]
