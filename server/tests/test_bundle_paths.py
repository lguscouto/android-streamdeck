from __future__ import annotations

from pathlib import Path

from app.main import default_profile_path


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
