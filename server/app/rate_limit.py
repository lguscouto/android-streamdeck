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
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock or time.monotonic
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
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
