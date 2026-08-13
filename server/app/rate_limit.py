from __future__ import annotations

import threading
import time
from collections.abc import Callable


class AttemptRateLimiter:
    """Bound online attempts per origin without storing request secrets."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: float = 60.0,
        max_origins: int = 4096,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if max_origins < 1:
            raise ValueError("max_origins must be positive")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_origins = max_origins
        self._clock = clock or time.monotonic
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            expired_keys = [
                stored_key
                for stored_key, timestamps in self._attempts.items()
                if not timestamps or now - timestamps[-1] >= self.window_seconds
            ]
            for expired_key in expired_keys:
                self._attempts.pop(expired_key, None)
            if key not in self._attempts and len(self._attempts) >= self.max_origins:
                return False
            recent = [
                timestamp
                for timestamp in self._attempts.get(key, [])
                if now - timestamp < self.window_seconds
            ]
            if len(recent) >= self.max_attempts:
                self._attempts[key] = recent
                return False
            recent.append(now)
            self._attempts[key] = recent
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


__all__ = ["AttemptRateLimiter"]
