from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from referencing import Registry, Resource

from app.resources import protocol_dir
from app.schemas import Profile


def profile_schema_path() -> Path:
    """Return the shared v1 profile schema, resolving source and bundle roots."""
    return protocol_dir() / "v1-profile.schema.json"


class ProfileTransferError(ValueError):
    """Base error raised when a profile cannot cross the JSON transfer boundary."""


class ProfileRevisionError(ProfileTransferError):
    """Raised when an imported profile has an unacceptable revision."""


def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProfileTransferError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _reject_non_json_number(value: str) -> None:
    raise ProfileTransferError(f"non-standard JSON number: {value}")


def _decode_payload(payload: str | bytes) -> dict[str, Any]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    except UnicodeDecodeError as exc:
        raise ProfileTransferError("profile JSON must be valid UTF-8") from exc

    try:
        value = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_non_json_number,
        )
    except ProfileTransferError:
        raise
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProfileTransferError("profile payload is not valid JSON") from exc

    if not isinstance(value, dict):
        raise ProfileTransferError("profile JSON must contain an object")
    return value


def _copy_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        copied = copy.deepcopy(dict(payload))
    except (TypeError, ValueError) as exc:
        raise ProfileTransferError("profile payload cannot be copied safely") from exc
    return copied


@lru_cache(maxsize=1)
def _profile_schema_validator() -> Draft202012Validator:
    try:
        schema = json.loads(profile_schema_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileTransferError("profile schema is unavailable") from exc

    try:
        registry = Registry().with_resources(
            [(schema["$id"], Resource.from_contents(schema))]
        )
        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
            registry=registry,
        )
        validator.check_schema(schema)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProfileTransferError("profile schema is invalid") from exc
    return validator


def _validate_profile_data(data: Mapping[str, Any]) -> Profile:
    try:
        profile = Profile.model_validate(data)
    except ValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise ProfileTransferError("profile payload is invalid") from exc

    wire = profile.to_wire()
    if next(_profile_schema_validator().iter_errors(wire), None) is not None:
        raise ProfileTransferError("profile payload does not conform to v1 schema")
    return profile


def _validated_profile(payload: Profile | Mapping[str, Any] | str | bytes) -> Profile:
    if isinstance(payload, Profile):
        # Re-validate through the explicit wire API so model_copy(update=...) cannot
        # smuggle an invalid or unset value across the transfer boundary.
        data = payload.to_wire()
    elif isinstance(payload, (str, bytes)):
        data = _decode_payload(payload)
    elif isinstance(payload, Mapping):
        data = _copy_mapping(payload)
    else:
        raise ProfileTransferError(
            "profile payload must be a Profile, mapping, or JSON"
        )
    return _validate_profile_data(data)


def import_profile(
    payload: Profile | Mapping[str, Any] | str | bytes,
    *,
    expected_revision: int | None = None,
) -> Profile:
    """Import and validate one v1 profile from a mapping or JSON document.

    The payload is parsed strictly, checked against the local Draft 2020-12 schema,
    and then checked against the server's relational Pydantic invariants. The
    optional ``expected_revision`` is an exact-match guard for callers importing
    into an already-known revision stream.
    """
    if expected_revision is not None:
        if isinstance(expected_revision, bool) or not isinstance(
            expected_revision, int
        ):
            raise ProfileRevisionError("expected revision must be a positive integer")
        if expected_revision < 1:
            raise ProfileRevisionError("expected revision must be a positive integer")

    profile = _validated_profile(payload)
    if expected_revision is not None and profile.revision != expected_revision:
        raise ProfileRevisionError("profile revision does not match expected revision")
    return profile


def export_profile(
    profile: Profile | Mapping[str, Any],
) -> str:
    """Export a sanitized profile as deterministic canonical JSON."""
    validated = _validated_profile(profile)
    wire = validated.to_wire()
    return json.dumps(
        wire,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def export_profile_json(profile: Profile | Mapping[str, Any]) -> str:
    """Explicit JSON-named alias for :func:`export_profile`."""
    return export_profile(profile)


def export_profile_data(profile: Profile | Mapping[str, Any]) -> dict[str, object]:
    """Return the sanitized wire mapping used by the deterministic exporter."""
    return json.loads(export_profile(profile))


@dataclass(frozen=True)
class ProfileTransfer:
    """Small integration seam for controllers without coupling to HTTP routes."""

    expected_revision: int | None = None

    def import_json(
        self, payload: Profile | Mapping[str, Any] | str | bytes
    ) -> Profile:
        return import_profile(payload, expected_revision=self.expected_revision)

    def export_json(self, profile: Profile | Mapping[str, Any]) -> str:
        return export_profile(profile)


__all__ = [
    "ProfileRevisionError",
    "ProfileTransfer",
    "ProfileTransferError",
    "export_profile",
    "export_profile_data",
    "export_profile_json",
    "import_profile",
    "profile_schema_path",
]
