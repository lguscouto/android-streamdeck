from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from app.actions import ActionExecutor
from app.api import create_router, register_exception_handlers
from app.config import Settings
from app.db import Database
from app.pairing import PairingService
from app.repositories.profiles import ProfileNotFoundError, ProfileRepository
from app.schemas import Profile
from app.websocket import WebSocketManager, create_websocket_router

SERVICE_NAME = "android-streamdeck-server"
PROTOCOL_VERSION = "0.1"
DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "default-profile.json"
)


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
    register_exception_handlers(application)
    application.include_router(
        create_router(
            repository,
            active_websocket_manager,
            pairing_service,
        )
    )
    application.include_router(
        create_websocket_router(repository, active_websocket_manager)
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=SERVICE_NAME,
            protocol_version=PROTOCOL_VERSION,
        )

    return application


app = create_app()
