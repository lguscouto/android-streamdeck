from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any, TypeAlias

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.pairing import (
    PairingCodeInvalidError,
    PairingService,
    PairingUnavailableError,
)
from app.profile_transfer import (
    ProfileTransferError,
    export_profile_data,
    import_profile,
)
from app.repositories.profiles import (
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileProtectedError,
    ProfileRepository,
    ProfileRevisionNotFoundError,
    ProfileValidationError,
)
from app.schemas import (
    AccessToken,
    NonNegativeInt,
    Page,
    Profile,
    StableId,
    StrictModel,
    Title,
    VersionString,
)

API_PREFIX = "/api/v1"
ACTION_TYPES = ("hotkey", "key", "media", "text", "url", "application")
ACTION_CATALOG = {"actions": [{"type": action_type} for action_type in ACTION_TYPES]}
LOGGER = logging.getLogger(__name__)
MAX_PROFILE_IMPORT_BYTES = 512 * 1024
PairingCode: TypeAlias = Annotated[
    str,
    Field(min_length=6, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{5,63}$"),
]


class PairingClaimRequest(StrictModel):
    client_id: StableId
    client_version: VersionString
    pairing_code: PairingCode


class PairingClaimResponse(StrictModel):
    client_id: StableId
    access_token: AccessToken


class ProfileSummary(StrictModel):
    id: StableId
    name: Title
    revision: int = Field(ge=1)
    active_page_id: StableId
    is_active: bool


class ProfileListResponse(StrictModel):
    profiles: list[ProfileSummary]


class ProfileRenameRequest(StrictModel):
    name: Title


class ProfileDuplicateRequest(StrictModel):
    id: StableId
    name: Title | None = None


class PageRenameRequest(StrictModel):
    title: Title


class PageReorderRequest(StrictModel):
    order: NonNegativeInt


class ProfileDeleteResponse(StrictModel):
    deleted_profile_id: StableId
    active_profile_id: StableId


class PageDeleteResponse(StrictModel):
    profile_id: StableId
    active_page_id: StableId
    revision: int = Field(ge=1)


class APIError(Exception):
    """An application error that is safe to expose at the HTTP boundary."""

    def __init__(
        self, status_code: int, code: str, message: str, retryable: bool
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def error_response(
    status_code: int, code: str, message: str, retryable: bool
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "retryable": retryable},
    )


def _internal_error() -> APIError:
    return APIError(500, "INTERNAL_ERROR", "Internal server error", False)


def _not_found(error: ProfileNotFoundError) -> APIError:
    if isinstance(error, ProfileRevisionNotFoundError):
        return APIError(
            404,
            "PROFILE_REVISION_NOT_FOUND",
            "Profile revision not found",
            False,
        )
    return APIError(404, "PROFILE_NOT_FOUND", "Profile not found", False)


def _conflict() -> APIError:
    return APIError(
        409,
        "PROFILE_REVISION_CONFLICT",
        "Profile revision conflict",
        True,
    )


def _protected(error: ProfileProtectedError) -> APIError:
    if "page" in str(error).lower():
        return APIError(
            409,
            "PAGE_DELETE_PROTECTED",
            "Page deletion requires a valid replacement",
            False,
        )
    return APIError(
        409,
        "PROFILE_DELETE_PROTECTED",
        "Profile deletion requires a valid replacement",
        False,
    )


def _validation() -> APIError:
    return APIError(422, "VALIDATION_ERROR", "Request validation failed", False)


def _safe_call(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return function(*args, **kwargs)
    except ProfileProtectedError as exc:
        raise _protected(exc) from None
    except ProfileNotFoundError as exc:
        raise _not_found(exc) from None
    except ProfileConflictError:
        raise _conflict() from None
    except (ProfileTransferError, ProfileValidationError, ValidationError):
        raise _validation() from None
    except Exception as exc:
        raise _internal_error() from exc


def _require_http_auth(
    request: Request,
    pairing_service: PairingService | None,
    *,
    required: bool,
) -> None:
    if not required:
        return
    if pairing_service is None:
        raise APIError(503, "AUTH_UNAVAILABLE", "Authentication unavailable", True)

    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    client_id = request.headers.get("x-streamdeck-client-id", "")
    if (
        scheme.lower() != "bearer"
        or not separator
        or not token
        or token != token.strip()
        or any(character.isspace() for character in token)
        or not client_id
    ):
        raise APIError(401, "AUTH_REQUIRED", "Authentication required", False)
    try:
        authenticated = pairing_service.authenticate(client_id, token)
    except Exception as exc:
        raise _internal_error() from exc
    if not authenticated:
        raise APIError(401, "AUTH_REQUIRED", "Authentication required", False)


def create_router(
    repository: ProfileRepository,
    websocket_manager: Any = None,
    pairing_service: PairingService | None = None,
    require_auth: bool = False,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["profiles"])

    async def broadcast_event(
        profile_id: str,
        revision: int,
        *,
        reason: str = "updated",
    ) -> None:
        if websocket_manager is None:
            return
        broadcaster = getattr(websocket_manager, "broadcast_profile_changed", None)
        if broadcaster is None:
            return
        try:
            await broadcaster(profile_id, revision, reason=reason)
        except Exception:
            LOGGER.warning(
                "profile change broadcast failed for profile %s revision %s",
                profile_id,
                revision,
            )

    async def broadcast(profile: Profile, *, reason: str = "updated") -> None:
        await broadcast_event(profile.id, profile.revision, reason=reason)

    def current_profile_or_none(profile_id: str) -> Profile | None:
        try:
            return repository.get_profile(profile_id)
        except ProfileNotFoundError:
            return None

    @router.get("/profiles")
    def list_profiles(request: Request) -> JSONResponse:
        """List profile metadata; use the snapshot route for full content."""
        _require_http_auth(request, pairing_service, required=require_auth)
        profiles = _safe_call(repository.list_profiles)
        active = _safe_call(repository.get_active_profile)
        active_id = active.id if active is not None else None
        response = ProfileListResponse(
            profiles=[
                ProfileSummary(
                    id=profile.id,
                    name=profile.name,
                    revision=profile.revision,
                    active_page_id=profile.active_page_id,
                    is_active=profile.id == active_id,
                )
                for profile in profiles
            ]
        )
        return JSONResponse(content=response.to_wire())

    @router.post("/profiles")
    async def create_profile(request: Request, profile: Profile) -> JSONResponse:
        """Create a revision-one profile; an existing ID is never overwritten."""
        _require_http_auth(request, pairing_service, required=require_auth)
        created = await run_in_threadpool(
            _safe_call, repository.create_profile, profile
        )
        await broadcast(created, reason="created")
        return JSONResponse(content=created.to_wire())

    @router.get("/profiles/{profile_id}")
    def get_profile(request: Request, profile_id: StableId) -> JSONResponse:
        """Read the current full snapshot for one profile."""
        _require_http_auth(request, pairing_service, required=require_auth)
        profile = _safe_call(repository.get_profile, profile_id)
        return JSONResponse(content=profile.to_wire())

    @router.patch("/profiles/{profile_id}")
    async def rename_profile(
        request: Request,
        profile_id: StableId,
        payload: ProfileRenameRequest,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        """Rename a profile with an atomic expected-revision check."""
        _require_http_auth(request, pairing_service, required=require_auth)
        renamed = await run_in_threadpool(
            _safe_call,
            repository.rename_profile,
            profile_id,
            payload.name,
            expected_revision=expected_revision,
        )
        await broadcast(renamed)
        return JSONResponse(content=renamed.to_wire())

    @router.post("/profiles/{profile_id}/duplicate")
    async def duplicate_profile(
        request: Request,
        profile_id: StableId,
        payload: ProfileDuplicateRequest,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        """Duplicate a profile into a new ID without copying active selection."""
        _require_http_auth(request, pairing_service, required=require_auth)
        duplicate = await run_in_threadpool(
            _safe_call,
            repository.duplicate_profile,
            profile_id,
            payload.id,
            expected_revision=expected_revision,
            name=payload.name,
        )
        await broadcast(duplicate, reason="created")
        return JSONResponse(content=duplicate.to_wire())

    @router.post("/profiles/{profile_id}/activate")
    async def activate_profile(
        request: Request,
        profile_id: StableId,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        """Activate a profile only from the caller's current revision."""
        _require_http_auth(request, pairing_service, required=require_auth)
        activated = await run_in_threadpool(
            _safe_call,
            repository.activate_profile,
            profile_id,
            expected_revision=expected_revision,
        )
        await broadcast(activated)
        return JSONResponse(content=activated.to_wire())

    @router.delete("/profiles/{profile_id}")
    async def delete_profile(
        request: Request,
        profile_id: StableId,
        expected_revision: int = Query(..., ge=1),
        replacement_profile_id: StableId | None = Query(default=None),
    ) -> JSONResponse:
        """Delete a profile; active/last deletion requires a valid replacement."""
        _require_http_auth(request, pairing_service, required=require_auth)
        deleted_profile = await run_in_threadpool(
            _safe_call,
            repository.get_profile,
            profile_id,
        )
        deleted_id = await run_in_threadpool(
            _safe_call,
            repository.delete_profile,
            profile_id,
            expected_revision=expected_revision,
            replacement_profile_id=replacement_profile_id,
        )
        await broadcast_event(
            deleted_profile.id,
            deleted_profile.revision,
            reason="deleted",
        )
        active = await run_in_threadpool(_safe_call, repository.get_active_profile)
        if active is None:
            raise APIError(500, "INTERNAL_ERROR", "Internal server error", False)
        await broadcast(active)
        response = ProfileDeleteResponse(
            deleted_profile_id=deleted_id,
            active_profile_id=active.id,
        )
        return JSONResponse(content=response.to_wire())

    @router.post("/profiles/{profile_id}/pages")
    async def create_page(
        request: Request,
        profile_id: StableId,
        payload: Page,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        """Create a page at its validated zero-based order position."""
        _require_http_auth(request, pairing_service, required=require_auth)
        created = await run_in_threadpool(
            _safe_call,
            repository.create_page,
            profile_id,
            payload,
            expected_revision=expected_revision,
        )
        await broadcast(created)
        return JSONResponse(content=created.to_wire())

    @router.patch("/profiles/{profile_id}/pages/{page_id}")
    async def rename_page(
        request: Request,
        profile_id: StableId,
        page_id: StableId,
        payload: PageRenameRequest,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        """Rename a page with an atomic expected-revision check."""
        _require_http_auth(request, pairing_service, required=require_auth)
        renamed = await run_in_threadpool(
            _safe_call,
            repository.rename_page,
            profile_id,
            page_id,
            payload.title,
            expected_revision=expected_revision,
        )
        await broadcast(renamed)
        return JSONResponse(content=renamed.to_wire())

    @router.post("/profiles/{profile_id}/pages/{page_id}/reorder")
    async def reorder_page(
        request: Request,
        profile_id: StableId,
        page_id: StableId,
        payload: PageReorderRequest,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        """Move a page and normalize all page orders without silent overwrite."""
        _require_http_auth(request, pairing_service, required=require_auth)
        reordered = await run_in_threadpool(
            _safe_call,
            repository.reorder_page,
            profile_id,
            page_id,
            payload.order,
            expected_revision=expected_revision,
        )
        await broadcast(reordered)
        return JSONResponse(content=reordered.to_wire())

    @router.delete("/profiles/{profile_id}/pages/{page_id}")
    async def delete_page(
        request: Request,
        profile_id: StableId,
        page_id: StableId,
        expected_revision: int = Query(..., ge=1),
        replacement_page_id: StableId | None = Query(default=None),
    ) -> JSONResponse:
        """Delete a page; the active/last page requires a valid replacement."""
        _require_http_auth(request, pairing_service, required=require_auth)
        deleted = await run_in_threadpool(
            _safe_call,
            repository.delete_page,
            profile_id,
            page_id,
            expected_revision=expected_revision,
            replacement_page_id=replacement_page_id,
        )
        await broadcast(deleted)
        response = PageDeleteResponse(
            profile_id=deleted.id,
            active_page_id=deleted.active_page_id,
            revision=deleted.revision,
        )
        return JSONResponse(content=response.to_wire())

    @router.get("/profile")
    def get_active_profile(request: Request) -> JSONResponse:
        _require_http_auth(request, pairing_service, required=require_auth)
        profile = _safe_call(repository.get_active_profile)
        if profile is None:
            raise APIError(404, "PROFILE_NOT_FOUND", "Profile not found", False)
        return JSONResponse(content=profile.to_wire())

    @router.get("/profiles/{profile_id}/snapshot")
    def get_profile_snapshot(
        request: Request,
        profile_id: StableId,
        revision: int | None = Query(default=None, ge=1),
    ) -> JSONResponse:
        _require_http_auth(request, pairing_service, required=require_auth)
        profile = _safe_call(repository.get_profile, profile_id, revision)
        return JSONResponse(content=profile.to_wire())

    @router.get("/profiles/{profile_id}/export")
    def export_profile_route(request: Request, profile_id: StableId) -> JSONResponse:
        """Return the current validated profile snapshot without secrets."""
        _require_http_auth(request, pairing_service, required=require_auth)
        profile = _safe_call(repository.get_profile, profile_id)
        exported = _safe_call(export_profile_data, profile)
        return JSONResponse(content=exported, media_type="application/json")

    @router.post("/profiles/import")
    async def import_profile_route(
        request: Request,
        expected_revision: int | None = Query(default=None, ge=1),
    ) -> JSONResponse:
        """Validate and persist an imported profile with atomic revision checks."""
        _require_http_auth(request, pairing_service, required=require_auth)
        payload = await request.body()
        if len(payload) > MAX_PROFILE_IMPORT_BYTES:
            raise APIError(
                413,
                "PAYLOAD_TOO_LARGE",
                "Profile payload is too large",
                False,
            )

        imported = await run_in_threadpool(_safe_call, import_profile, payload)
        current = await run_in_threadpool(
            _safe_call, current_profile_or_none, imported.id
        )
        if current is None:
            target_revision = 1
        else:
            if expected_revision is None:
                raise _conflict()
            target_revision = current.revision + 1

        wire = imported.to_wire()
        wire["revision"] = target_revision
        normalized = _safe_call(Profile.model_validate, wire)
        saved = await run_in_threadpool(
            _safe_call,
            repository.save_profile,
            normalized,
            expected_revision=expected_revision,
            reason="updated",
        )
        await broadcast(saved)
        return JSONResponse(content=saved.to_wire())

    @router.get("/actions")
    def get_action_catalog() -> JSONResponse:
        return JSONResponse(content=ACTION_CATALOG)

    @router.get("/profiles/{profile_id}/audit")
    def get_profile_audit(
        request: Request,
        profile_id: StableId,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> JSONResponse:
        _require_http_auth(request, pairing_service, required=require_auth)
        entries = _safe_call(repository.list_audit, profile_id, limit=limit)
        return JSONResponse(content={"profile_id": profile_id, "entries": entries})

    @router.post("/pairing/claim")
    async def claim_pairing(payload: PairingClaimRequest) -> JSONResponse:
        if pairing_service is None:
            raise APIError(
                503,
                "PAIRING_UNAVAILABLE",
                "Pairing is unavailable",
                True,
            )
        try:
            token = await run_in_threadpool(
                pairing_service.claim_token,
                payload.client_id,
                payload.client_version,
                payload.pairing_code,
            )
        except PairingCodeInvalidError:
            raise APIError(
                401,
                "PAIRING_CODE_INVALID",
                "Pairing code is invalid",
                False,
            ) from None
        except PairingUnavailableError:
            raise APIError(
                503,
                "PAIRING_UNAVAILABLE",
                "Pairing is unavailable",
                True,
            ) from None
        except Exception as exc:
            raise _internal_error() from exc
        response = PairingClaimResponse(
            client_id=payload.client_id,
            access_token=token,
        )
        return JSONResponse(content=response.to_wire())

    @router.put("/profiles/{profile_id}")
    async def put_profile(
        request: Request,
        profile_id: StableId,
        profile: Profile,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
        _require_http_auth(request, pairing_service, required=require_auth)
        if profile.id != profile_id:
            raise APIError(
                422,
                "VALIDATION_ERROR",
                "Request validation failed",
                False,
            )
        saved = await run_in_threadpool(
            _safe_call,
            repository.save_profile,
            profile,
            expected_revision=expected_revision,
            reason="updated",
        )
        if websocket_manager is not None:
            broadcaster = getattr(websocket_manager, "broadcast_profile_changed", None)
            if broadcaster is not None:
                try:
                    await broadcaster(saved.id, saved.revision, reason="updated")
                except Exception:
                    LOGGER.warning(
                        "profile change broadcast failed for profile %s revision %s",
                        saved.id,
                        saved.revision,
                    )
        return JSONResponse(content=saved.to_wire())

    return router


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(APIError)
    async def handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.retryable)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            False,
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 500
        if status_code == 404:
            return error_response(404, "NOT_FOUND", "Resource not found", False)
        return error_response(status_code, "HTTP_ERROR", "Request failed", False)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(
        _request: Request, _exc: Exception
    ) -> JSONResponse:
        return error_response(500, "INTERNAL_ERROR", "Internal server error", False)
