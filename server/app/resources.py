"""Single resource-root resolver shared by source runs and PyInstaller bundles.

The server reads immutable public contracts (shared JSON schemas and fixtures)
from a single location that works both when running from the checkout and when
frozen by PyInstaller. Mutable security state (database, TLS keys, CA, tokens,
logs, pairing/admin codes) must never live here: it stays in the user runtime
directory managed by :mod:`app.config`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ``server/app/resources.py`` -> parents[2] is the repository root in source mode.
_SOURCE_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    """Return the root that owns the immutable ``shared`` contract tree.

    In a PyInstaller one-file bundle, resources are extracted to
    ``sys._MEIPASS``; in source mode they live under the repository root.
    """
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return _SOURCE_REPO_ROOT


def shared_dir() -> Path:
    """Return the ``shared`` directory (schemas and fixtures)."""
    return repo_root() / "shared"


def protocol_dir() -> Path:
    """Return the ``shared/protocol`` directory (versioned JSON schemas)."""
    return shared_dir() / "protocol"


def fixtures_dir() -> Path:
    """Return the ``shared/fixtures`` directory (versioned JSON fixtures)."""
    return shared_dir() / "fixtures"


def essential_controls_profile_path() -> Path:
    """Return the immutable current essential-controls profile fixture."""
    return fixtures_dir() / "essential-controls-profile.json"


def essential_controls_profile_v1_path() -> Path:
    """Return the frozen v1 fixture used for non-destructive built-in upgrades."""
    return fixtures_dir() / "essential-controls-profile-v1.json"


def essential_controls_profile_v2_path() -> Path:
    """Return the frozen v2 fixture used for non-destructive v3 upgrades."""
    return fixtures_dir() / "essential-controls-profile-v2.json"


__all__ = [
    "essential_controls_profile_path",
    "essential_controls_profile_v1_path",
    "essential_controls_profile_v2_path",
    "fixtures_dir",
    "protocol_dir",
    "repo_root",
    "shared_dir",
]
