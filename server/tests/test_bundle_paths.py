from __future__ import annotations

from pathlib import Path

from app.main import default_profile_path
from app.profile_transfer import profile_schema_path


def test_default_profile_path_uses_pyinstaller_bundle_root(monkeypatch) -> None:
    monkeypatch.setattr("sys._MEIPASS", "C:/bundle", raising=False)

    assert (
        default_profile_path()
        == Path("C:/bundle") / "shared" / "fixtures" / "default-profile.json"
    )


def test_default_profile_path_uses_project_root_in_source_mode(monkeypatch) -> None:
    monkeypatch.delattr("sys._MEIPASS", raising=False)

    path = default_profile_path()

    assert path.name == "default-profile.json"
    assert path.parent.name == "fixtures"


def test_profile_schema_path_uses_pyinstaller_bundle_root(monkeypatch) -> None:
    monkeypatch.setattr("sys._MEIPASS", "C:/bundle", raising=False)

    assert (
        profile_schema_path()
        == Path("C:/bundle") / "shared" / "protocol" / "v1-profile.schema.json"
    )


def test_profile_schema_path_uses_project_root_in_source_mode(monkeypatch) -> None:
    monkeypatch.delattr("sys._MEIPASS", raising=False)

    assert profile_schema_path().name == "v1-profile.schema.json"
    assert profile_schema_path().parent.name == "protocol"
