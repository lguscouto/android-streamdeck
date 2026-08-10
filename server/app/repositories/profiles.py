from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import ValidationError

from app.db import Database
from app.schemas import Page, Profile


class ProfileRepositoryError(RuntimeError):
    """Base class for safe profile persistence errors."""


class ProfileConflictError(ProfileRepositoryError):
    """Raised when a profile revision is stale or not the required successor."""


class ProfileValidationError(ProfileRepositoryError):
    """Raised when an operation's relational input is not valid."""


class ProfileProtectedError(ProfileConflictError):
    """Raised when deletion would violate a required active-resource invariant."""


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

    def create_profile(self, profile: Profile | Mapping[str, Any]) -> Profile:
        """Create a new profile at revision one, without replacing an existing ID."""
        wire = _validated_wire(profile)
        if wire["revision"] != 1:
            raise ProfileConflictError("new profiles must start at revision 1")
        try:
            with self.database.transaction() as connection:
                current = connection.execute(
                    "SELECT 1 FROM profiles WHERE id = ?", (wire["id"],)
                ).fetchone()
                if current is not None:
                    raise ProfileConflictError("profile already exists")
                active = (
                    connection.execute(
                        "SELECT 1 FROM profiles WHERE is_active = 1 LIMIT 1"
                    ).fetchone()
                    is None
                )
                _insert_profile(connection, wire, reason="created", is_active=active)
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile persistence failed") from exc
        return Profile.model_validate(wire)

    def list_profiles(self) -> list[Profile]:
        """Return current profile snapshots in deterministic active-first order."""
        connection = self.database.connect()
        try:
            rows = connection.execute(
                """
                SELECT r.snapshot_json
                FROM profiles AS p
                JOIN profile_revisions AS r
                  ON r.profile_id = p.id AND r.revision = p.revision
                ORDER BY p.is_active DESC, p.id ASC
                """
            ).fetchall()
            return [_profile_from_snapshot(row["snapshot_json"]) for row in rows]
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile list failed") from exc
        finally:
            connection.close()

    def duplicate_profile(
        self,
        source_profile_id: str,
        new_profile_id: str,
        *,
        expected_revision: int | None = None,
        name: str | None = None,
    ) -> Profile:
        """Clone a current profile into a new revision-one profile atomically."""
        try:
            with self.database.transaction() as connection:
                source = _current_profile_row(connection, source_profile_id)
                _check_expected_revision(source, expected_revision)
                if connection.execute(
                    "SELECT 1 FROM profiles WHERE id = ?", (new_profile_id,)
                ).fetchone():
                    raise ProfileConflictError("profile already exists")
                wire = source["profile"].to_wire()
                wire["id"] = new_profile_id
                wire["revision"] = 1
                if name is not None:
                    wire["name"] = name
                wire = _validated_wire(wire)
                active = (
                    connection.execute(
                        "SELECT 1 FROM profiles WHERE is_active = 1 LIMIT 1"
                    ).fetchone()
                    is None
                )
                _insert_profile(connection, wire, reason="created", is_active=active)
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile persistence failed") from exc
        return Profile.model_validate(wire)

    def rename_profile(
        self, profile_id: str, name: str, *, expected_revision: int
    ) -> Profile:
        """Rename a profile by committing a guarded next revision."""
        return self._mutate_profile(
            profile_id,
            expected_revision=expected_revision,
            reason="updated",
            mutate=lambda wire: {**wire, "name": name},
        )

    def activate_profile(self, profile_id: str, *, expected_revision: int) -> Profile:
        """Activate a profile and record a monotonic selection revision."""
        try:
            with self.database.transaction() as connection:
                current = _current_profile_row(connection, profile_id)
                _check_expected_revision(current, expected_revision)
                if bool(current["is_active"]):
                    return current["profile"]
                wire = current["profile"].to_wire()
                wire["revision"] = int(current["revision"]) + 1
                activated = Profile.model_validate(wire)
                connection.execute("UPDATE profiles SET is_active = 0")
                _replace_profile(
                    connection,
                    activated.to_wire(),
                    reason="activated",
                    is_active=True,
                )
                return activated
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("active profile update failed") from exc

    def delete_profile(
        self,
        profile_id: str,
        *,
        expected_revision: int,
        replacement_profile_id: str | None = None,
    ) -> str:
        """Delete a profile, requiring a valid replacement when it is active."""
        try:
            with self.database.transaction() as connection:
                current = _current_profile_row(connection, profile_id)
                _check_expected_revision(current, expected_revision)
                profile_count = int(
                    connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
                )
                if profile_count <= 1:
                    raise ProfileProtectedError("cannot delete the last profile")
                if replacement_profile_id == profile_id:
                    raise ProfileProtectedError("replacement profile must differ")
                replacement_row = None
                if replacement_profile_id is not None:
                    try:
                        replacement_row = _current_profile_row(
                            connection,
                            replacement_profile_id,
                        )
                    except ProfileNotFoundError:
                        raise ProfileNotFoundError(
                            "replacement profile not found"
                        ) from None
                if bool(current["is_active"]):
                    if replacement_profile_id is None or replacement_row is None:
                        raise ProfileProtectedError(
                            "active profile deletion requires a replacement"
                        )
                    connection.execute("UPDATE profiles SET is_active = 0")
                    replacement_wire = replacement_row["profile"].to_wire()
                    replacement_wire["revision"] = int(replacement_row["revision"]) + 1
                    replacement_profile = Profile.model_validate(replacement_wire)
                    _replace_profile(
                        connection,
                        replacement_profile.to_wire(),
                        reason="updated",
                        is_active=True,
                    )
                connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
                return profile_id
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile deletion failed") from exc

    def create_page(
        self, profile_id: str, page: Page | Mapping[str, Any], *, expected_revision: int
    ) -> Profile:
        """Insert a page at an order position and commit the next profile revision."""
        validated_page = _validated_page(page)

        def mutate(wire: dict[str, Any]) -> dict[str, Any]:
            pages = wire["pages"]
            if not 0 <= validated_page.order <= len(pages):
                raise ProfileValidationError("page order is invalid")
            if any(item["id"] == validated_page.id for item in pages):
                candidate = {**wire, "pages": pages + [validated_page.to_wire()]}
                Profile.model_validate(candidate)
            for item in pages:
                if item["order"] >= validated_page.order:
                    item["order"] += 1
            pages.append(validated_page.to_wire())
            return wire

        return self._mutate_profile(
            profile_id,
            expected_revision=expected_revision,
            reason="updated",
            mutate=mutate,
        )

    def rename_page(
        self,
        profile_id: str,
        page_id: str,
        title: str,
        *,
        expected_revision: int,
    ) -> Profile:
        """Rename a page by committing a guarded next profile revision."""

        def mutate(wire: dict[str, Any]) -> dict[str, Any]:
            for page in wire["pages"]:
                if page["id"] == page_id:
                    page["title"] = title
                    return wire
            raise ProfileNotFoundError("page not found")

        return self._mutate_profile(
            profile_id,
            expected_revision=expected_revision,
            reason="updated",
            mutate=mutate,
        )

    def reorder_page(
        self,
        profile_id: str,
        page_id: str,
        order: int,
        *,
        expected_revision: int,
    ) -> Profile:
        """Move a page to a zero-based position, normalizing all page orders."""

        def mutate(wire: dict[str, Any]) -> dict[str, Any]:
            pages = sorted(wire["pages"], key=lambda item: item["order"])
            if not 0 <= order < len(pages):
                raise ProfileValidationError("page order is invalid")
            selected = next((item for item in pages if item["id"] == page_id), None)
            if selected is None:
                raise ProfileNotFoundError("page not found")
            pages.remove(selected)
            pages.insert(order, selected)
            for index, item in enumerate(pages):
                item["order"] = index
            wire["pages"] = pages
            return wire

        return self._mutate_profile(
            profile_id,
            expected_revision=expected_revision,
            reason="updated",
            mutate=mutate,
        )

    def delete_page(
        self,
        profile_id: str,
        page_id: str,
        *,
        expected_revision: int,
        replacement_page_id: str | None = None,
    ) -> Profile:
        """Delete a page, requiring a valid replacement for the active page."""

        def mutate(wire: dict[str, Any]) -> dict[str, Any]:
            pages = wire["pages"]
            selected = next((item for item in pages if item["id"] == page_id), None)
            if selected is None:
                raise ProfileNotFoundError("page not found")
            if len(pages) <= 1:
                raise ProfileProtectedError("cannot delete the last page")
            if page_id == wire["active_page_id"]:
                if replacement_page_id is None or replacement_page_id == page_id:
                    raise ProfileProtectedError(
                        "active page deletion requires a replacement"
                    )
                if not any(item["id"] == replacement_page_id for item in pages):
                    raise ProfileNotFoundError("replacement page not found")
                wire["active_page_id"] = replacement_page_id
            pages.remove(selected)
            for index, item in enumerate(sorted(pages, key=lambda item: item["order"])):
                item["order"] = index
            wire["pages"] = pages
            return wire

        return self._mutate_profile(
            profile_id,
            expected_revision=expected_revision,
            reason="updated",
            mutate=mutate,
        )

    def _mutate_profile(
        self,
        profile_id: str,
        *,
        expected_revision: int,
        reason: str,
        mutate: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> Profile:
        """Apply one validated snapshot mutation under one SQLite write lock."""
        try:
            with self.database.transaction() as connection:
                current = _current_profile_row(connection, profile_id)
                _check_expected_revision(current, expected_revision)
                wire = current["profile"].to_wire()
                updated = mutate(wire)
                updated["revision"] = int(current["revision"]) + 1
                validated = Profile.model_validate(updated)
                _replace_profile(
                    connection,
                    validated.to_wire(),
                    reason=reason,
                    is_active=bool(current["is_active"]),
                )
                return validated
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as exc:
            raise ProfileRepositoryError("profile persistence failed") from exc

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


def _current_profile_row(
    connection: sqlite3.Connection, profile_id: str
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT p.revision, p.is_active, r.snapshot_json
        FROM profiles AS p
        JOIN profile_revisions AS r
          ON r.profile_id = p.id AND r.revision = p.revision
        WHERE p.id = ?
        """,
        (profile_id,),
    ).fetchone()
    if row is None:
        raise ProfileNotFoundError("profile not found")
    return {
        "revision": int(row["revision"]),
        "is_active": int(row["is_active"]),
        "profile": _profile_from_snapshot(row["snapshot_json"]),
    }


def _check_expected_revision(
    current: dict[str, Any], expected_revision: int | None
) -> None:
    if expected_revision is not None and expected_revision != current["revision"]:
        raise ProfileConflictError("profile revision conflict")


def _validated_page(page: Page | Mapping[str, Any]) -> Page:
    if isinstance(page, Page):
        return Page.model_validate(page.to_wire())
    return Page.model_validate(page)


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
