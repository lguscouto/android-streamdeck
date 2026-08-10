from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.actions import ActionExecutor
from app.api import create_router, register_exception_handlers
from app.body_limit import register_body_limit
from app.config import Settings
from app.db import Database
from app.pairing import PairingService
from app.repositories.profiles import ProfileNotFoundError, ProfileRepository
from app.resources import fixtures_dir
from app.schemas import Profile
from app.websocket import WebSocketManager, create_websocket_router

SERVICE_NAME = "android-streamdeck-server"
PROTOCOL_VERSION = "0.1"
LOGGER = logging.getLogger(__name__)


def default_profile_path() -> Path:
    """Locate the seed profile both from source and a PyInstaller bundle."""
    return fixtures_dir() / "default-profile.json"


DEFAULT_PROFILE_PATH = default_profile_path()


class HealthResponse(BaseModel):
    status: str
    service: str
    protocol_version: str


def _load_default_profile() -> Profile:
    payload = json.loads(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    return Profile.model_validate(payload)


def create_app(
    settings: Settings | None = None,
    repository: ProfileRepository | None = None,
    websocket_manager: Any = None,
    action_executor: ActionExecutor | None = None,
) -> FastAPI:
    """Create the FastAPI application with optional persistence dependencies."""
    runtime_settings = settings or Settings.from_env()
    database: Database | None

    if repository is None:
        database = Database(runtime_settings.database_path)
        repository = ProfileRepository(database)
        repository.initialize()
        try:
            repository.get_profile("default")
        except ProfileNotFoundError:
            repository.seed_profile(_load_default_profile())
    else:
        database = getattr(repository, "database", None)

    if database is None:
        raise RuntimeError("pairing requires a database-backed repository")
    pairing_service = PairingService(database, runtime_settings.pairing_code)
    active_websocket_manager = websocket_manager or WebSocketManager(
        repository,
        pairing_service=pairing_service,
        require_auth=runtime_settings.require_auth,
        action_executor=action_executor,
    )
    application = FastAPI(title=SERVICE_NAME, version=PROTOCOL_VERSION)
    application.state.settings = runtime_settings
    application.state.database = database
    application.state.profile_repository = repository
    application.state.pairing_service = pairing_service
    application.state.websocket_manager = active_websocket_manager
    register_body_limit(application)
    register_exception_handlers(application)
    application.include_router(
        create_router(
            repository,
            active_websocket_manager,
            pairing_service,
            require_auth=runtime_settings.require_auth,
            admin_code=runtime_settings.admin_code,
        )
    )
    application.include_router(
        create_websocket_router(repository, active_websocket_manager)
    )

    @application.middleware("http")
    async def sanitized_access_log(request: Request, call_next):
        """Log sanitized HTTP access without any header, token, or body value."""
        import time

        started = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - started) * 1000.0
        origin = request.client.host if request.client is not None else None
        LOGGER.info(
            "HTTP_ACCESS",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
                "origin": origin,
            },
        )
        return response

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=SERVICE_NAME,
            protocol_version=PROTOCOL_VERSION,
        )

    return application
