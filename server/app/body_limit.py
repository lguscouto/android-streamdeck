from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Global cap for authenticated write routes. Import keeps its own tighter cap
# (MAX_PROFILE_IMPORT_BYTES); other profile/page writes share this larger bound.
MAX_WRITE_BODY_BYTES = 1024 * 1024  # 1 MiB


class RequestBodyTooLargeError(Exception):
    """Raised internally when a write body exceeds the global cap."""


def sanitized_payload_too_large_response() -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={
            "code": "PAYLOAD_TOO_LARGE",
            "message": "Request body is too large",
            "retryable": False,
        },
    )


def _content_length(request: Request) -> int | None:
    raw = request.headers.get("content-length")
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def register_body_limit(app: FastAPI, *, max_bytes: int = MAX_WRITE_BODY_BYTES) -> None:
    """Reject oversized request bodies on write methods with a sanitized 413.

    The limit is applied before Pydantic parsing so a compromised client token
    cannot force the server to materialize arbitrarily large JSON. Chunked
    bodies without Content-Length are capped while streaming.
    """

    @app.middleware("http")
    async def body_limit_middleware(request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        declared = _content_length(request)
        if declared is not None and declared > max_bytes:
            return sanitized_payload_too_large_response()

        # Wrap receive to cap streaming bodies that omit Content-Length.
        receive = request._receive

        async def capped_receive():
            message = await receive()
            if message["type"] == "http.request" and message.get("body"):
                accumulated = getattr(request.state, "_body_bytes", 0)
                accumulated += len(message.get("body", b""))
                request.state._body_bytes = accumulated
                if accumulated > max_bytes:
                    raise RequestBodyTooLargeError()
            return message

        request._receive = capped_receive
        try:
            response = await call_next(request)
        except RequestBodyTooLargeError:
            return sanitized_payload_too_large_response()
        return response
