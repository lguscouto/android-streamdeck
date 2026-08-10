import logging

import uvicorn

from app.config import Settings
from app.discovery import DiscoveryError, DiscoveryPublisher
from app.main import create_app

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Run the server using the bind settings from the environment."""
    settings = Settings.from_env()
    application = create_app(settings)
    discovery = DiscoveryPublisher(settings)
    try:
        discovery.start()
    except DiscoveryError:
        LOGGER.warning("LAN_DISCOVERY_UNAVAILABLE")
    try:
        uvicorn.run(application, host=settings.host, port=settings.port)
    finally:
        discovery.stop()


if __name__ == "__main__":
    main()
