"""Thread-safe TTL cache for sharing data across concurrent requests.

Multiple users asking about the same match reuse cached schedule, analysis,
search, and weather data — cutting redundant API calls to near zero.
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Callable


class TTLCache:
    """Thread-safe in-memory cache with per-key TTL."""

    def __init__(self, default_ttl: float = 300.0):
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts >= self._default_ttl:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def get_or_set(self, key: str, factory: Callable[[], Any]) -> Any:
        """Get cached value, or compute + cache if missing/expired.

        The factory runs OUTSIDE the lock so slow I/O doesn't block readers.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                ts, value = entry
                if time.time() - ts < self._default_ttl:
                    return value
        value = factory()
        with self._lock:
            self._store[key] = (time.time(), value)
        return value

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# ── shared caches ──

schedule_cache = TTLCache(default_ttl=300.0)     # 5 min
analysis_cache = TTLCache(default_ttl=600.0)     # 10 min
search_cache = TTLCache(default_ttl=900.0)       # 15 min
weather_cache = TTLCache(default_ttl=3600.0)     # 1 hour


def search_key(query: str) -> str:
    return f"sr:{hashlib.sha1(query.encode()).hexdigest()[:12]}"


def analysis_key(match_id: str) -> str:
    return f"an:{match_id}"


def weather_key(lat: float, lon: float, date: str) -> str:
    return f"wx:{lat:.2f}:{lon:.2f}:{date}"
