from __future__ import annotations

import os
from collections.abc import Sequence
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
    gpu_bridge: str | Path | None = None,
    librehardwaremonitor: str | Path | None = None,
    gpu_native_binaries: Sequence[str | Path] = (),
    third_party_notices: str | Path | None = None,
    mpl_license: str | Path | None = None,
    dotnet_notices: str | Path | None = None,
    apache_license: str | Path | None = None,
    mit_license: str | Path | None = None,
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
    notices_path = (
        Path(third_party_notices)
        if third_party_notices is not None
        else project_root.parent / "THIRD-PARTY-NOTICES.md"
    )
    mpl_path = (
        Path(mpl_license)
        if mpl_license is not None
        else project_root.parent / "LICENSES" / "MPL-2.0.txt"
    )
    dotnet_notices_path = (
        Path(dotnet_notices)
        if dotnet_notices is not None
        else project_root.parent / "LICENSES" / "THIRD-PARTY-DOTNET.md"
    )
    apache_path = (
        Path(apache_license)
        if apache_license is not None
        else project_root.parent / "LICENSES" / "Apache-2.0.txt"
    )
    mit_path = (
        Path(mit_license)
        if mit_license is not None
        else project_root.parent / "LICENSES" / "MIT.txt"
    )
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
        command.extend(
            [
                "--collect-all",
                "zeroconf",
                # win32com is imported lazily by the closed WMI adapter, so
                # PyInstaller needs an explicit collection for frozen builds.
                "--collect-all",
                "win32com",
                "--hidden-import",
                "pynvml",
            ]
        )
        native_binary_paths = tuple(
            dict.fromkeys(Path(binary) for binary in gpu_native_binaries)
        )
        for binary in native_binary_paths:
            binary_path = Path(binary)
            if not binary_path.is_file():
                raise FileNotFoundError(f"missing GPU bundle binary: {binary_path}")
            command.extend(
                [
                    "--add-binary",
                    f"{_portable_path(binary_path)}{os.pathsep}app/native",
                ]
            )
        for binary in (gpu_bridge, librehardwaremonitor):
            if binary is not None and Path(binary) not in native_binary_paths:
                binary_path = Path(binary)
                if not binary_path.is_file():
                    raise FileNotFoundError(f"missing GPU bundle binary: {binary_path}")
                command.extend(
                    [
                        "--add-binary",
                        f"{_portable_path(binary_path)}{os.pathsep}app/native",
                    ]
                )
        for source, destination in (
            (notices_path, "."),
            (mpl_path, "LICENSES"),
            (dotnet_notices_path, "LICENSES"),
            (apache_path, "LICENSES"),
            (mit_path, "LICENSES"),
        ):
            source_path = Path(source)
            if not source_path.is_file():
                raise FileNotFoundError(f"missing GPU bundle notice: {source_path}")
            command.extend(
                [
                    "--add-data",
                    f"{_portable_path(source_path)}{os.pathsep}{destination}",
                ]
            )
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
