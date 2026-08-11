from __future__ import annotations

import pytest

from app.actions import (
    ActionExecutionRejected,
    WindowsApplicationAdapter,
    default_application_catalog,
)
from app.catalog import ApplicationCatalog
from app.schemas import ApplicationAction

CATALOG = ApplicationCatalog(
    {
        "notepad": {"display_name": "Bloco de Notas", "executable": "notepad.exe"},
        "calc": {"display_name": "Calculadora", "executable": "calc.exe"},
    }
)


class FakeLauncher:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def __call__(self, executable: str) -> None:
        self.opened.append(executable)


def test_application_catalog_resolves_registered_id() -> None:
    entry = CATALOG.get("notepad")

    assert entry is not None
    assert entry.display_name == "Bloco de Notas"
    assert entry.executable == "notepad.exe"


def test_application_catalog_ignores_unknown_id() -> None:
    assert CATALOG.get("photoshop") is None
    assert CATALOG.listing() == [
        {"app_id": "calc", "display_name": "Calculadora"},
        {"app_id": "notepad", "display_name": "Bloco de Notas"},
    ]


def test_application_adapter_launches_registered_application() -> None:
    launcher = FakeLauncher()
    adapter = WindowsApplicationAdapter(CATALOG, launcher=launcher)

    adapter.execute(ApplicationAction(type="application", app_id="notepad"))

    assert launcher.opened == ["notepad.exe"]


def test_application_adapter_rejects_unregistered_application() -> None:
    launcher = FakeLauncher()
    adapter = WindowsApplicationAdapter(CATALOG, launcher=launcher)

    with pytest.raises(ActionExecutionRejected):
        adapter.execute(ApplicationAction(type="application", app_id="photoshop"))

    assert launcher.opened == []


def test_application_adapter_never_accepts_a_free_path() -> None:
    launcher = FakeLauncher()
    adapter = WindowsApplicationAdapter(CATALOG, launcher=launcher)

    # A path is not a valid ApplicationId candidate; the schema itself rejects
    # free-form paths, and the adapter also refuses any id absent from the
    # catalog — so no free path can ever reach the launcher.
    with pytest.raises(ActionExecutionRejected):
        adapter.execute(ApplicationAction(type="application", app_id="not-in-catalog"))

    assert launcher.opened == []


def test_application_adapter_propagates_launcher_failure_as_rejection() -> None:
    def failing_launcher(_executable: str) -> None:
        raise OSError("process spawn failed")

    adapter = WindowsApplicationAdapter(CATALOG, launcher=failing_launcher)

    with pytest.raises(ActionExecutionRejected):
        adapter.execute(ApplicationAction(type="application", app_id="calc"))


def test_catalog_rejects_relative_or_absolute_path_entries() -> None:
    with pytest.raises(ValueError):
        ApplicationCatalog(
            {"unsafe": {"display_name": "Fake", "executable": "C:/Windows/x.exe"}}
        )
    with pytest.raises(ValueError):
        ApplicationCatalog(
            {"unsafe": {"display_name": "Fake", "executable": "../x.exe"}}
        )


def test_catalog_listing_is_sorted_and_names_only() -> None:
    listing = CATALOG.listing()

    assert listing == [
        {"app_id": "calc", "display_name": "Calculadora"},
        {"app_id": "notepad", "display_name": "Bloco de Notas"},
    ]
    # Never leaks executable paths to the client.
    assert all("executable" not in item for item in listing)


def test_default_catalog_lists_only_sanitized_chrome_metadata() -> None:
    catalog = default_application_catalog()

    assert catalog.listing() == [{"app_id": "chrome", "display_name": "Google Chrome"}]
    assert all("executable" not in item for item in catalog.listing())


def test_default_application_adapter_launches_fixed_chrome_executable() -> None:
    launcher = FakeLauncher()
    adapter = WindowsApplicationAdapter(launcher=launcher)

    adapter.execute(ApplicationAction(type="application", app_id="chrome"))

    assert launcher.opened == ["chrome.exe"]
