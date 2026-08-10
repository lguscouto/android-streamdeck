"""Structured JSON logging with no secrets.

The server writes JSON log records (time, level, logger, event and safe extra
fields) to both the console and a rotating file under the mutable runtime state
directory. Authorization headers, pairing codes, admin codes and tokens must
never be attached to records; security events are logged as stable codes (for
example ``PAIRING_FAILED``) without their values.
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Any

LOG_FILE_NAME = "server.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

_SAFE_EXTRA_FIELDS = (
    "client_id",
    "duration_ms",
    "method",
    "origin",
    "path",
    "profile_id",
    "reason",
    "status_code",
)


def default_log_dir() -> Path:
    """Keep log files with the mutable runtime state, never in the bundle."""
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA")
        root = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / "AppData" / "Local"
        )
        return root / "AndroidStreamDeck" / "logs"
    return Path(__file__).resolve().parents[1] / "data" / "logs"


class JsonFormatter(logging.Formatter):
    """Serialize sanitized log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in _SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def build_logging_config(*, log_dir: str | Path) -> dict[str, Any]:
    """Return a ``dictConfig`` schema with console + rotating JSON handlers."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": "app.logging_config.JsonFormatter"}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": str(log_path / LOG_FILE_NAME),
                "maxBytes": MAX_BYTES,
                "backupCount": BACKUP_COUNT,
                "encoding": "utf-8",
            },
        },
        "root": {"handlers": ["console", "file"], "level": "INFO"},
    }


def apply_logging_config(*, log_dir: str | Path) -> None:
    """Apply the JSON logging configuration for the running process."""
    config = build_logging_config(log_dir=log_dir)
    logging.config.dictConfig(config)


__all__ = [
    "BACKUP_COUNT",
    "JsonFormatter",
    "LOG_FILE_NAME",
    "MAX_BYTES",
    "apply_logging_config",
    "build_logging_config",
    "default_log_dir",
]
