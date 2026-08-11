import logging
import os

import uvicorn

from app.actions import RecordingActionExecutor
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
    tls_options: dict[str, str] = {}
    ca_certificate_pem: str | None = None
    if settings.tls_required:
        material = TlsMaterialStore(
            state_dir=settings.tls_state_dir,
            identities=settings.tls_identities,
        ).ensure()
        ca_certificate_pem = material.ca_certificate_path.read_text(encoding="ascii")
        tls_options = {
            "ssl_certfile": str(material.certificate_path),
            "ssl_keyfile": str(material.private_key_path),
        }
    action_executor = None
    if os.environ.get("STREAMDECK_ACTION_MODE", "").strip().lower() == "recording":
        action_executor = RecordingActionExecutor()
    app_kwargs: dict[str, object] = {}
    if ca_certificate_pem is not None:
        app_kwargs["ca_certificate_pem"] = ca_certificate_pem
    if action_executor is not None:
        app_kwargs["action_executor"] = action_executor
    application = create_app(settings, **app_kwargs)
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
