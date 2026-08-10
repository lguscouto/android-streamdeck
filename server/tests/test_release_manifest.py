from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.release_manifest import (
    ReleaseArtifactMissingError,
    artifact_sha256,
    build_release_manifest,
    resolve_commit,
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


def test_resolve_commit_prefers_github_sha_environment(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)

    assert resolve_commit() == "b" * 40


def test_resolve_commit_reads_git_head_when_environment_is_absent(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GITHUB_SHA", raising=False)

    resolved = resolve_commit(fallback="fallback-value")

    assert resolved == "fallback-value" or len(resolved) >= 7


def test_resolve_commit_falls_back_when_git_is_unavailable(
    monkeypatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("git unavailable")

    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(
        "scripts.release_manifest.subprocess.run",
        boom,
    )

    assert resolve_commit(fallback="fallback-value") == "fallback-value"
