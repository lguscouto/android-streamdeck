from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.repositories.profiles import (
    ProfileRepository,
    _insert_profile,
    _profile_from_snapshot,
    _replace_profile,
)
from app.resources import (
    essential_controls_profile_path,
    essential_controls_profile_v1_path,
    essential_controls_profile_v2_path,
)
from app.schemas import Profile

BUILTIN_PROFILE_ID = "essential-controls"
ESSENTIAL_CONTROLS_PROFILE_ID = BUILTIN_PROFILE_ID
BUILTIN_PROFILE_VERSION = 3


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


def load_essential_controls_profile_v1() -> Profile:
    """Load the immutable v1 built-in fixture for one-way v2 migration tests."""
    return load_essential_controls_profile(essential_controls_profile_v1_path())


def load_essential_controls_profile_v2() -> Profile:
    """Load the immutable v2 built-in fixture before GPU telemetry was added."""
    return load_essential_controls_profile(essential_controls_profile_v2_path())


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
            installed_version = int(marker["version"])
            current = _current_profile_or_none(connection, BUILTIN_PROFILE_ID)
            if installed_version >= BUILTIN_PROFILE_VERSION:
                return current
            return _upgrade_builtin_profile(
                connection,
                current=current,
                wire=wire,
                installed_version=installed_version,
            )

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


def _upgrade_builtin_profile(
    connection: Any,
    *,
    current: Profile | None,
    wire: dict[str, object],
    installed_version: int,
) -> Profile | None:
    """Advance only an untouched prior built-in profile to the current fixture.

    User-edited or deleted built-ins are deliberately never replaced. The marker
    is still advanced so a later startup cannot repeatedly reevaluate a user
    choice. A historical snapshot remains available because the repository's
    normal revision append path is used for the upgrade.
    """
    if current is None:
        _mark_builtin_version(connection)
        return None

    expected_prior = _builtin_profile_for_version(installed_version)
    if expected_prior is None or not _same_profile_content(current, expected_prior):
        _mark_builtin_version(connection)
        return current

    upgraded_wire = dict(wire)
    upgraded_wire["revision"] = current.revision + 1
    _replace_profile(
        connection,
        upgraded_wire,
        reason="builtin_upgrade",
        is_active=_profile_is_active(connection, BUILTIN_PROFILE_ID),
    )
    _mark_builtin_version(connection)
    return Profile.model_validate(upgraded_wire)


def _builtin_profile_for_version(version: int) -> Profile | None:
    if version == 1:
        return load_essential_controls_profile_v1()
    if version == 2:
        return load_essential_controls_profile_v2()
    if version == BUILTIN_PROFILE_VERSION:
        return load_essential_controls_profile()
    return None


def _same_profile_content(left: Profile, right: Profile) -> bool:
    left_wire = left.to_wire()
    right_wire = right.to_wire()
    left_wire.pop("revision", None)
    right_wire.pop("revision", None)
    return left_wire == right_wire


def _profile_is_active(connection: Any, profile_id: str) -> bool:
    row = connection.execute(
        "SELECT is_active FROM profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    return bool(row["is_active"]) if row is not None else False


def _mark_builtin_version(connection: Any) -> None:
    connection.execute(
        """
        UPDATE builtin_profile_installations
        SET version = ?
        WHERE builtin_id = ?
        """,
        (BUILTIN_PROFILE_VERSION, BUILTIN_PROFILE_ID),
    )


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
    "load_essential_controls_profile_v1",
    "load_essential_controls_profile_v2",
]
