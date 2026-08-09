from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any, TypeAlias

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.pairing import (
    PairingCodeInvalidError,
    PairingService,
    PairingUnavailableError,
)
from app.repositories.profiles import (
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileRepository,
    ProfileRevisionNotFoundError,
)
from app.schemas import AccessToken, Profile, StableId, StrictModel, VersionString

API_PREFIX = "/api/v1"
ACTION_TYPES = ("hotkey", "key", "media", "text", "url", "application")
ACTION_CATALOG = {"actions": [{"type": action_type} for action_type in ACTION_TYPES]}
LOGGER = logging.getLogger(__name__)
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


def _safe_call(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return function(*args, **kwargs)
    except ProfileNotFoundError as exc:
        raise _not_found(exc) from None
    except ProfileConflictError:
        raise _conflict() from None
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
