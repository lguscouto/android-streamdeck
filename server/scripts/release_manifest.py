from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ReleaseArtifactMissingError(FileNotFoundError):
    """Raised when a required release artifact is absent or is a directory."""


def artifact_sha256(path: Path) -> str:
    """Return the lowercase hex SHA-256 of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(
    *,
    commit: str,
    server_version: str,
    android_version_name: str,
    android_version_code: int,
    artifacts: dict[str, Path],
) -> dict[str, Any]:
    """Build a deterministic release manifest with sizes and SHA-256 hashes.

    Rationale: a release is only reproducible if required artifacts are present
    and their content is pinned. The manifest intentionally carries no mutable
    runtime state (database, TLS, keys, tokens) and no timestamps; auditors can
    make it deterministic and compare bytes across identical artifacts.
    """
    resolved: dict[str, Any] = {}
    for logical_name, artifact in sorted(artifacts.items()):
        path = Path(artifact)
        if not path.is_file():
            raise ReleaseArtifactMissingError(
                f"release artifact missing: {logical_name} -> {path}"
            )
        resolved[logical_name] = {
            "path": path.as_posix(),
            "size": path.stat().st_size,
            "sha256": artifact_sha256(path),
        }
    return {
        "commit": commit,
        "server_version": server_version,
        "android_version_name": android_version_name,
        "android_version_code": android_version_code,
        "artifacts": resolved,
        "signed": None,
    }


def main() -> int:
    """Emit a JSON release manifest for the standard bundle + APK artifacts."""
    server_root = Path(__file__).resolve().parents[1]
    repo_root = server_root.parent
    artifacts = {
        "server": server_root / "dist" / "streamdeck-server.exe",
        "tray": server_root / "dist" / "streamdeck-tray.exe",
        "apk-release": repo_root
        / "android"
        / "app"
        / "build"
        / "outputs"
        / "apk"
        / "release"
        / "app-release-unsigned.apk",
    }
    manifest = build_release_manifest(
        commit="unknown",
        server_version="0.1.0",
        android_version_name="0.1.0",
        android_version_code=1,
        artifacts=artifacts,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ReleaseArtifactMissingError",
    "artifact_sha256",
    "build_release_manifest",
]
