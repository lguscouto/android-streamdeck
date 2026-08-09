from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.db import Database
from app.schemas import Profile


class ProfileRepositoryError(RuntimeError):
    """Base class for safe profile persistence errors."""


class ProfileConflictError(ProfileRepositoryError):
    """Raised when a profile revision is stale or not the required successor."""


class ProfileNotFoundError(ProfileRepositoryError):
    """Raised when a requested profile or revision does not exist."""


class ProfileRevisionNotFoundError(ProfileNotFoundError):
    """Raised when a profile exists but the requested revision does not."""


class ProfileRepository:
    """Transactional persistence for validated profiles and revision snapshots."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def initialize(self) -> None:
        self.database.initialize()

    migrate = initialize

    def seed_profile(self, profile: Profile | Mapping[str, Any]) -> Profile:
        """Insert a profile once, treating an identical subsequent seed as a no-op."""
        wire = _validated_wire(profile)
        if wire["revision"] != 1:
            raise ProfileConflictError("seed profiles must start at revision 1")
        reason = "created"
        try:
            with self.database.transaction() as connection:
                current = connection.execute(
                    "SELECT revision FROM profiles WHERE id = ?", (wire["id"],)
                ).fetchone()
                if current is not None:
                    snapshot = _snapshot_for_revision(
                        connection, wire["id"], int(current["revision"])
                    )
                    if snapshot == wire:
                        return Profile.model_validate(snapshot)
                    raise ProfileConflictError(
                        "profile already exists with different content"
                    )

                active = (
                    connection.execute(
                        "SELECT 1 FROM profiles WHERE is_active = 1 LIMIT 1"
                    ).fetchone()
                    is None
                )
                _insert_profile(
                    connection,
                    wire,
                    reason=reason,
                    is_active=active,
                )
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile persistence failed") from exc
        return Profile.model_validate(wire)

    def get_active_profile(self) -> Profile | None:
        """Return the active profile without changing schema or data."""
        connection = self.database.connect()
        try:
            row = connection.execute(
                """
                SELECT r.snapshot_json
                FROM profiles AS p
                JOIN profile_revisions AS r
                  ON r.profile_id = p.id AND r.revision = p.revision
                WHERE p.is_active = 1
                """
            ).fetchone()
            if row is None:
                return None
            return _profile_from_snapshot(row["snapshot_json"])
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile lookup failed") from exc
        finally:
            connection.close()

    def get_profile(self, profile_id: str, revision: int | None = None) -> Profile:
        """Return the current or exact historical revision of a profile."""
        connection = self.database.connect()
        try:
            if revision is None:
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
                    raise ProfileNotFoundError("profile not found")
            else:
                row = connection.execute(
                    """
                    SELECT snapshot_json
                    FROM profile_revisions
                    WHERE profile_id = ? AND revision = ?
                    """,
                    (profile_id, revision),
                ).fetchone()
                if row is None:
                    raise ProfileRevisionNotFoundError("profile revision not found")
            return _profile_from_snapshot(row["snapshot_json"])
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile lookup failed") from exc
        finally:
            connection.close()

    def save_profile(
        self,
        profile: Profile | Mapping[str, Any],
        expected_revision: int | None = None,
        *,
        reason: str = "updated",
    ) -> Profile:
        """Save the next revision atomically with optimistic concurrency checks."""
        wire = _validated_wire(profile)
        normalized_reason = _validated_reason(reason)
        try:
            with self.database.transaction() as connection:
                current = connection.execute(
                    """
                    SELECT revision, is_active
                    FROM profiles
                    WHERE id = ?
                    """,
                    (wire["id"],),
                ).fetchone()
                if current is None:
                    if expected_revision is not None:
                        raise ProfileConflictError("profile revision conflict")
                    if wire["revision"] != 1:
                        raise ProfileConflictError(
                            "new profiles must start at revision 1"
                        )
                    active = (
                        connection.execute(
                            "SELECT 1 FROM profiles WHERE is_active = 1 LIMIT 1"
                        ).fetchone()
                        is None
                    )
                    _insert_profile(
                        connection,
                        wire,
                        reason=normalized_reason,
                        is_active=active,
                    )
                else:
                    current_revision = int(current["revision"])
                    if (
                        expected_revision is not None
                        and expected_revision != current_revision
                    ):
                        raise ProfileConflictError("profile revision conflict")
                    if wire["revision"] != current_revision + 1:
                        raise ProfileConflictError(
                            "profile revision must be the next revision"
                        )
                    _replace_profile(
                        connection,
                        wire,
                        reason=normalized_reason,
                        is_active=bool(current["is_active"]),
                    )
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile persistence failed") from exc
        return Profile.model_validate(wire)

    def list_audit(
        self,
        profile_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """Return revision metadata without exposing stored profile snapshots."""
        if not 1 <= limit <= 100:
            raise ProfileRepositoryError("audit limit is invalid")
        connection = self.database.connect()
        try:
            exists = connection.execute(
                "SELECT 1 FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            if exists is None:
                raise ProfileNotFoundError("profile not found")
            rows = connection.execute(
                """
                SELECT revision, reason, created_at
                FROM profile_revisions
                WHERE profile_id = ?
                ORDER BY revision ASC
                LIMIT ?
                """,
                (profile_id, limit),
            ).fetchall()
            return [
                {
                    "revision": int(row["revision"]),
                    "reason": str(row["reason"]),
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile audit lookup failed") from exc
        finally:
            connection.close()

    def set_active_profile(self, profile_id: str) -> None:
        """Select exactly one existing profile as active."""
        try:
            with self.database.transaction() as connection:
                exists = connection.execute(
                    "SELECT 1 FROM profiles WHERE id = ?", (profile_id,)
                ).fetchone()
                if exists is None:
                    raise ProfileNotFoundError("profile not found")
                connection.execute("UPDATE profiles SET is_active = 0")
                connection.execute(
                    "UPDATE profiles SET is_active = 1 WHERE id = ?", (profile_id,)
                )
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("active profile update failed") from exc


def _validated_wire(profile: Profile | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(profile, Profile):
        validated = Profile.model_validate(profile.to_wire())
    else:
        validated = Profile.model_validate(profile)
    return validated.to_wire()


def _validated_reason(reason: str) -> str:
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ProfileRepositoryError("revision reason is invalid")
    return reason.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_for_revision(
    connection: sqlite3.Connection, profile_id: str, revision: int
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT snapshot_json
        FROM profile_revisions
        WHERE profile_id = ? AND revision = ?
        """,
        (profile_id, revision),
    ).fetchone()
    if row is None:
        raise ProfileRepositoryError("stored profile revision is missing")
    try:
        snapshot = json.loads(row["snapshot_json"])
        return Profile.model_validate(snapshot).to_wire()
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise ProfileRepositoryError("stored profile snapshot is invalid") from exc


def _profile_from_snapshot(snapshot_json: str) -> Profile:
    try:
        snapshot = json.loads(snapshot_json)
        return Profile.model_validate(snapshot)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise ProfileRepositoryError("stored profile snapshot is invalid") from exc


def _insert_profile(
    connection: sqlite3.Connection,
    wire: dict[str, Any],
    *,
    reason: str,
    is_active: bool,
) -> None:
    timestamp = _now()
    connection.execute(
        """
        INSERT INTO profiles(
            id, protocol_version, name, revision, active_page_id,
            is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wire["id"],
            wire["protocol_version"],
            wire["name"],
            wire["revision"],
            wire["active_page_id"],
            int(is_active),
            timestamp,
            timestamp,
        ),
    )
    _insert_pages_and_children(connection, wire)
    _insert_revision(connection, wire, reason=reason, created_at=timestamp)


def _replace_profile(
    connection: sqlite3.Connection,
    wire: dict[str, Any],
    *,
    reason: str,
    is_active: bool,
) -> None:
    timestamp = _now()
    connection.execute(
        """
        UPDATE profiles
        SET protocol_version = ?, name = ?, revision = ?, active_page_id = ?,
            is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            wire["protocol_version"],
            wire["name"],
            wire["revision"],
            wire["active_page_id"],
            int(is_active),
            timestamp,
            wire["id"],
        ),
    )
    connection.execute("DELETE FROM pages WHERE profile_id = ?", (wire["id"],))
    _insert_pages_and_children(connection, wire)
    _insert_revision(connection, wire, reason=reason, created_at=timestamp)


def _insert_pages_and_children(
    connection: sqlite3.Connection, wire: dict[str, Any]
) -> None:
    for page in wire["pages"]:
        connection.execute(
            """
            INSERT INTO pages(profile_id, id, title, order_index, rows, columns)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                wire["id"],
                page["id"],
                page["title"],
                page["order"],
                page["rows"],
                page["columns"],
            ),
        )
        for button in page["buttons"]:
            connection.execute(
                """
                INSERT INTO buttons(
                    profile_id, page_id, id, row_index, column_index,
                    title, icon, color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wire["id"],
                    page["id"],
                    button["id"],
                    button["row"],
                    button["column"],
                    button["title"],
                    button.get("icon"),
                    button.get("color"),
                ),
            )
            action = button["action"]
            connection.execute(
                """
                INSERT INTO actions(
                    profile_id, page_id, button_id, action_type, payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    wire["id"],
                    page["id"],
                    button["id"],
                    action["type"],
                    json.dumps(
                        action,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )


def _insert_revision(
    connection: sqlite3.Connection,
    wire: dict[str, Any],
    *,
    reason: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO profile_revisions(
            profile_id, revision, snapshot_json, reason, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            wire["id"],
            wire["revision"],
            json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            reason,
            created_at,
        ),
    )
