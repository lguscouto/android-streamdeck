from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.windows_packaging import build_pyinstaller_command

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / "build" / "phase6-pyinstaller"


def main() -> None:
    bridge_project = (
        ROOT / "native" / "gpu_telemetry_bridge" / "GpuTelemetryBridge.csproj"
    )
    subprocess.run(
        [
            "dotnet",
            "publish",
            str(bridge_project),
            "-c",
            "Release",
            "-r",
            "win-x64",
            "--self-contained",
            "true",
        ],
        cwd=ROOT,
        check=True,
        shell=False,
    )
    DIST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    bridge_binary = (
        ROOT
        / "native"
        / "gpu_telemetry_bridge"
        / "bin"
        / "Release"
        / "net8.0"
        / "win-x64"
        / "publish"
        / "streamdeck_gpu_bridge.dll"
    )
    monitor_binary = (
        Path.home()
        / ".nuget"
        / "packages"
        / "librehardwaremonitorlib"
        / "0.9.6"
        / "runtimes"
        / "win-x64"
        / "lib"
        / "net8.0"
        / "LibreHardwareMonitorLib.dll"
    )
    native_companions = tuple(
        path
        for path in (
            bridge_binary,
            monitor_binary,
            bridge_binary.parent / "MonoPosixHelper.dll",
            bridge_binary.parent / "libMonoPosixHelper.dll",
        )
        if path.is_file()
    )
    expected_native_binaries = (
        bridge_binary,
        monitor_binary,
        bridge_binary.parent / "MonoPosixHelper.dll",
        bridge_binary.parent / "libMonoPosixHelper.dll",
    )
    missing_native = [path for path in expected_native_binaries if not path.is_file()]
    if missing_native:
        raise FileNotFoundError(
            "NativeAOT/AMD bundle dependencies are missing: "
            + ", ".join(str(path) for path in missing_native)
        )
    for target, executable_name in (
        ("server", "streamdeck-server.exe"),
        ("tray", "streamdeck-tray.exe"),
    ):
        command = build_pyinstaller_command(
            target=target,  # type: ignore[arg-type]
            root=ROOT,
            executable=sys.executable,
            output_dir=DIST,
            work_dir=WORK / target,
            gpu_bridge=bridge_binary,
            librehardwaremonitor=monitor_binary,
            gpu_native_binaries=native_companions,
            third_party_notices=ROOT.parent / "THIRD-PARTY-NOTICES.md",
            mpl_license=ROOT.parent / "LICENSES" / "MPL-2.0.txt",
            dotnet_notices=ROOT.parent / "LICENSES" / "THIRD-PARTY-DOTNET.md",
            apache_license=ROOT.parent / "LICENSES" / "Apache-2.0.txt",
            mit_license=ROOT.parent / "LICENSES" / "MIT.txt",
        )
        subprocess.run(command, cwd=ROOT, check=True, shell=False)
        artifact = DIST / executable_name
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise RuntimeError(f"PyInstaller did not create {executable_name}")
        print(f"{executable_name}: {artifact.stat().st_size} bytes")


if __name__ == "__main__":
    main()
