"""Closed catalog of applications the server may launch.

Every entry maps a stable application id (the only value the Android client can
send) to a fixed display name and an executable that is launched directly via
the OS shell-open API. The catalog never accepts a client-provided path, and
entries with paths are rejected at construction time.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping

# Executables are Windows binaries (optional .exe) or commands on PATH. Path
# separators/`..`/drive letters are rejected at the boundary.
_EXECUTABLE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+\-]*(?:\.exe)?$", re.ASCII)


@dataclass(frozen=True, slots=True)
class ApplicationEntry:
    display_name: str
    executable: str


class ApplicationCatalog:
    """Provide/validate the fixed application map for ``application`` actions."""

    def __init__(self, entries: Mapping[str, Mapping[str, str]]) -> None:
        normalized: dict[str, ApplicationEntry] = {}
        for application_id, values in entries.items():
            display_name = str(values["display_name"]).strip()
            executable = str(values["executable"]).strip()
            if not display_name:
                raise ValueError("application display_name must not be empty")
            if not _EXECUTABLE_PATTERN.fullmatch(executable):
                raise ValueError(
                    f"executable must be a bare binary name, got: {executable!r}"
                )
            if os.path.sep in executable or "\\" in executable or ".." in executable:
                raise ValueError("executable must not contain path separators")
            normalized[application_id] = ApplicationEntry(
                display_name=display_name,
                executable=executable,
            )
        self._entries = normalized

    def get(self, application_id: str) -> ApplicationEntry | None:
        return self._entries.get(application_id)

    def listing(self) -> list[dict[str, str]]:
        """Public, non-secret inventory of available applications."""
        return sorted(
            (
                {"app_id": application_id, "display_name": entry.display_name}
                for application_id, entry in self._entries.items()
            ),
            key=lambda item: item["app_id"],
        )


__all__ = ["ApplicationCatalog", "ApplicationEntry"]
