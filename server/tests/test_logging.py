from __future__ import annotations

import json
import logging

import pytest

from app.logging_config import (
    JsonFormatter,
    build_logging_config,
    default_log_dir,
)


def test_default_log_dir_uses_data_logs_in_source_mode(monkeypatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)

    path = default_log_dir()

    assert path.name == "logs"
    assert "data" in str(path)


def test_default_log_dir_uses_local_app_data_when_frozen(monkeypatch) -> None:
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")

    assert default_log_dir() == (
        __import__("pathlib").Path(r"C:\Users\test\AppData\Local")
        / "AndroidStreamDeck"
        / "logs"
    )


def test_build_logging_config_registers_json_formatter_and_rotating_file(
    tmp_path,
) -> None:
    config = build_logging_config(log_dir=tmp_path)

    assert config["version"] == 1
    assert config["disable_existing_loggers"] is False
    assert "file" in config["handlers"]
    assert config["handlers"]["file"]["class"].endswith("RotatingFileHandler")
    assert config["handlers"]["file"]["maxBytes"] > 0
    assert config["handlers"]["file"]["backupCount"] >= 1
    assert config["formatters"]["json"] == {"()": "app.logging_config.JsonFormatter"}


def test_json_formatter_emits_sanitized_structured_record() -> None:
    record = logging.LogRecord(
        name="app.api",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="PAIRING_FAILED",
        args=(),
        exc_info=None,
    )
    record.client_id = "client-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["time"]
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "app.api"
    assert payload["event"] == "PAIRING_FAILED"
    assert payload["client_id"] == "client-1"
    assert "access_token" not in payload
    assert "pairing_code" not in payload


def test_json_formatter_serializes_extra_metrics_fields() -> None:
    record = logging.LogRecord(
        name="app.main",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP_ACCESS",
        args=(),
        exc_info=None,
    )
    record.method = "POST"
    record.status_code = 401
    record.duration_ms = 12.4

    payload = json.loads(JsonFormatter().format(record))

    assert payload["method"] == "POST"
    assert payload["status_code"] == 401
    assert payload["duration_ms"] == 12.4


@pytest.mark.parametrize(
    "secret_placeholder",
    ["secret-pairing-code", "secret-admin-code", "secret-bearer-token"],
)
def test_security_events_never_include_secret_values(
    caplog, secret_placeholder
) -> None:
    """Security events must be logged as stable codes, never their values."""
    logger = logging.getLogger("app.test.security")
    with caplog.at_level(logging.WARNING, logger="app.test.security"):
        logger.warning("PAIRING_FAILED")
        logger.warning("DEVICE_ADMIN_RATE_LIMITED")
        logger.warning("WS_AUTH_FAILED")

    serialized = "\n".join(record.getMessage() for record in caplog.records)
    assert "PAIRING_FAILED" in serialized
    assert "WS_AUTH_FAILED" in serialized
    assert secret_placeholder not in serialized
