from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.repositories.profiles import (
    ProfileConflictError,
    ProfileNotFoundError,
    ProfileRepository,
    ProfileRevisionNotFoundError,
)
from app.schemas import Profile, StableId

API_PREFIX = "/api/v1"
ACTION_TYPES = ("hotkey", "key", "media", "text", "url", "application")
ACTION_CATALOG = {"actions": [{"type": action_type} for action_type in ACTION_TYPES]}
LOGGER = logging.getLogger(__name__)


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


def create_router(
    repository: ProfileRepository,
    websocket_manager: Any = None,
) -> APIRouter:
    router = APIRouter(prefix=API_PREFIX, tags=["profiles"])

    @router.get("/profile")
    def get_active_profile() -> JSONResponse:
        profile = _safe_call(repository.get_active_profile)
        if profile is None:
            raise APIError(404, "PROFILE_NOT_FOUND", "Profile not found", False)
        return JSONResponse(content=profile.to_wire())

    @router.get("/profiles/{profile_id}/snapshot")
    def get_profile_snapshot(
        profile_id: StableId,
        revision: int | None = Query(default=None, ge=1),
    ) -> JSONResponse:
        profile = _safe_call(repository.get_profile, profile_id, revision)
        return JSONResponse(content=profile.to_wire())

    @router.get("/actions")
    def get_action_catalog() -> JSONResponse:
        return JSONResponse(content=ACTION_CATALOG)

    @router.put("/profiles/{profile_id}")
    async def put_profile(
        profile_id: StableId,
        profile: Profile,
        expected_revision: int = Query(..., ge=1),
    ) -> JSONResponse:
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
