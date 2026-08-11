from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.repositories.profiles import (
    ProfileRepository,
    _insert_profile,
    _profile_from_snapshot,
)
from app.resources import essential_controls_profile_path
from app.schemas import Profile

BUILTIN_PROFILE_ID = "essential-controls"
ESSENTIAL_CONTROLS_PROFILE_ID = BUILTIN_PROFILE_ID
BUILTIN_PROFILE_VERSION = 1


def load_essential_controls_profile(path: Path | None = None) -> Profile:
    """Load and validate the immutable essential-controls fixture."""
    fixture_path = path or essential_controls_profile_path()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    profile = Profile.model_validate(payload)
    if profile.id != BUILTIN_PROFILE_ID:
        raise ValueError("essential-controls fixture has an unexpected profile id")
    if profile.revision != 1:
        raise ValueError("essential-controls fixture must start at revision 1")
    return profile


def install_builtin_profiles(repository: ProfileRepository) -> Profile | None:
    """Install the essential profile once without replacing user data.

    The installation marker and the profile rows are committed in the same
    SQLite transaction. A marker remains after a user deletes the profile, so a
    later server start does not silently recreate a user choice.
    """
    profile = load_essential_controls_profile()
    wire = profile.to_wire()
    database = repository.database

    with database.transaction() as connection:
        marker = connection.execute(
            """
            SELECT version
            FROM builtin_profile_installations
            WHERE builtin_id = ?
            """,
            (BUILTIN_PROFILE_ID,),
        ).fetchone()
        if marker is not None:
            return _current_profile_or_none(connection, BUILTIN_PROFILE_ID)

        current = _current_profile_or_none(connection, BUILTIN_PROFILE_ID)
        if current is None:
            active = (
                connection.execute(
                    "SELECT 1 FROM profiles WHERE is_active = 1 LIMIT 1"
                ).fetchone()
                is None
            )
            _insert_profile(
                connection,
                wire,
                reason="builtin",
                is_active=active,
            )
            installed: Profile | None = profile
        else:
            # A colliding ID belongs to the user; never compare-and-replace it.
            installed = current if current.to_wire() == wire else None

        connection.execute(
            """
            INSERT INTO builtin_profile_installations(builtin_id, version, installed_at)
            VALUES (?, ?, ?)
            """,
            (
                BUILTIN_PROFILE_ID,
                BUILTIN_PROFILE_VERSION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return installed


def _current_profile_or_none(
    connection: Any,
    profile_id: str,
) -> Profile | None:
    row = connection.execute(
        """
        SELECT r.snapshot_json
        FROM profiles AS p
        JOIN profile_revisions AS r
          ON r.profile_id = p.id AND r.revision = p.revision
        WHERE p.id = ?
        """,
        (profile_id,),
    ).fetchone()
    if row is None:
        return None
    return _profile_from_snapshot(row["snapshot_json"])


install_builtin_profile = install_builtin_profiles


__all__ = [
    "BUILTIN_PROFILE_ID",
    "BUILTIN_PROFILE_VERSION",
    "ESSENTIAL_CONTROLS_PROFILE_ID",
    "install_builtin_profile",
    "install_builtin_profiles",
    "load_essential_controls_profile",
]
