from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque


class RateLimiter(ABC):
    """Abstraction the Gateway depends on. Swappable later for a
    RedisRateLimiter (or any distributed implementation) without touching
    routes.py or controller.py.
    """

    @abstractmethod
    def allow(self, user_id: str) -> bool:
        """Return True if this request should be allowed, False if the
        caller has exceeded their rate limit."""
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    """MVP fixed-window-ish rate limiter: allows up to `max_requests` per
    `window_seconds` per user_id, tracked with a sliding deque of
    timestamps. Process-local only (does not survive a restart and is not
    shared across multiple Gateway instances) - intentionally simple until a
    RedisRateLimiter replaces it.
    """

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, user_id: str) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = self._hits.setdefault(user_id, deque())

            while timestamps and now - timestamps[0] > self._window_seconds:
                timestamps.popleft()

            if len(timestamps) >= self._max_requests:
                return False

            timestamps.append(now)
            return True
