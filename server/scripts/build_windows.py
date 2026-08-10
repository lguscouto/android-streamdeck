from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.windows_packaging import build_pyinstaller_command

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / "build" / "phase6-pyinstaller"


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
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
        )
        subprocess.run(command, cwd=ROOT, check=True, shell=False)
        artifact = DIST / executable_name
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise RuntimeError(f"PyInstaller did not create {executable_name}")
        print(f"{executable_name}: {artifact.stat().st_size} bytes")


if __name__ == "__main__":
    main()
