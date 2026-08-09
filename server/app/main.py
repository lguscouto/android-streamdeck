from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Settings

SERVICE_NAME = "android-streamdeck-server"
PROTOCOL_VERSION = "0.1"


class HealthResponse(BaseModel):
    status: str
    service: str
    protocol_version: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI application without exposing runtime secrets."""
    runtime_settings = settings or Settings.from_env()
    application = FastAPI(title=SERVICE_NAME, version=PROTOCOL_VERSION)
    application.state.settings = runtime_settings

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=SERVICE_NAME,
            protocol_version=PROTOCOL_VERSION,
        )

    return application


app = create_app()
