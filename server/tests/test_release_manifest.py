from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.release_manifest import (
    ReleaseArtifactMissingError,
    artifact_sha256,
    build_release_manifest,
)


def test_artifact_sha256_matches_content(tmp_path: Path) -> None:
    artifact = tmp_path / "file.bin"
    artifact.write_bytes(b"streamdeck-release-content")

    expected = hashlib.sha256(b"streamdeck-release-content").hexdigest()

    assert artifact_sha256(artifact) == expected


def test_build_release_manifest_reports_size_and_hash(tmp_path: Path) -> None:
    artifact = tmp_path / "server.exe"
    artifact.write_bytes(b"0123456789")

    manifest = build_release_manifest(
        commit="a" * 40,
        server_version="0.1.0",
        android_version_name="0.1.0",
        android_version_code=1,
        artifacts={"server": artifact},
    )

    assert manifest["artifacts"]["server"]["size"] == 10
    assert (
        manifest["artifacts"]["server"]["sha256"]
        == hashlib.sha256(b"0123456789").hexdigest()
    )
    assert manifest["commit"] == "a" * 40


def test_build_release_manifest_rejects_missing_artifact(tmp_path: Path) -> None:
    with pytest.raises(ReleaseArtifactMissingError):
        build_release_manifest(
            commit="a" * 40,
            server_version="0.1.0",
            android_version_name="0.1.0",
            android_version_code=1,
            artifacts={"missing": tmp_path / "does-not-exist.exe"},
        )


def test_build_release_manifest_output_is_serializable(tmp_path: Path) -> None:
    artifact = tmp_path / "server.exe"
    artifact.write_bytes(b"data")

    manifest = build_release_manifest(
        commit="a" * 40,
        server_version="0.1.0",
        android_version_name="0.1.0",
        android_version_code=1,
        artifacts={"server": artifact},
    )

    json.dumps(manifest)  # must not raise
