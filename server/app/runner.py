import logging

import uvicorn

from app.config import Settings, default_log_dir
from app.discovery import DiscoveryError, DiscoveryPublisher
from app.logging_config import apply_logging_config
from app.main import create_app
from app.tls import TlsMaterialStore

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Run the server using the bind settings from the environment."""
    settings = Settings.from_env()
    apply_logging_config(
        log_dir=getattr(settings, "log_dir", None) or default_log_dir()
    )
    application = create_app(settings)
    tls_options: dict[str, str] = {}
    if settings.tls_required:
        material = TlsMaterialStore(
            state_dir=settings.tls_state_dir,
            identities=settings.tls_identities,
        ).ensure()
        tls_options = {
            "ssl_certfile": str(material.certificate_path),
            "ssl_keyfile": str(material.private_key_path),
        }
    discovery = DiscoveryPublisher(settings)
    try:
        discovery.start()
    except DiscoveryError:
        LOGGER.warning("LAN_DISCOVERY_UNAVAILABLE")
    try:
        uvicorn.run(
            application,
            host=settings.host,
            port=settings.port,
            log_config=None,
            **tls_options,
        )
    finally:
        discovery.stop()


if __name__ == "__main__":
    main()
