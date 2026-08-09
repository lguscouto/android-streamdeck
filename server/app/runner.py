import uvicorn

from app.config import Settings
from app.main import create_app


def main() -> None:
    """Run the server using the bind settings from the environment."""
    settings = Settings.from_env()
    application = create_app(settings)
    uvicorn.run(application, host=settings.host, port=settings.port)
