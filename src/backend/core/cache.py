"""Engine-scoped thread-safe TTL cache for high-performance dual-SQLite reads (ADR-010)."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

from sqlmodel import Session

T = TypeVar("T")


class EngineScopedCache:
    """Thread-safe in-memory TTL cache partitioned by SQLAlchemy Engine identity."""

    def __init__(self, default_ttl: float = 60.0) -> None:
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._store: dict[tuple[Any, ...], tuple[float, Any]] = {}

    @staticmethod
    def session_scope(*sessions: Session | None) -> tuple[int, ...]:
        """Return a deterministic tuple of engine memory IDs for the given sessions."""
        ids: list[int] = []
        for s in sessions:
            if s is not None:
                ids.append(id(s.get_bind()))
            else:
                ids.append(0)
        return tuple(ids)

    def get_or_set(
        self,
        scope: tuple[int, ...],
        namespace: str,
        key: Any,
        factory: Callable[[], T],
        ttl: float | None = None,
    ) -> T:
        """Fetch cached value or compute and store it under (scope, namespace, key)."""
        full_key = (scope, namespace, key)
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(full_key)
            if entry is not None and entry[0] > now:
                return entry[1]
        value = factory()
        expires_at = now + (ttl if ttl is not None else self._default_ttl)
        with self._lock:
            self._store[full_key] = (expires_at, value)
        return value

    def invalidate(self, namespace: str | None = None) -> None:
        """Clear all cached entries or only entries matching a specific namespace."""
        with self._lock:
            if namespace is None:
                self._store.clear()
                return
            to_remove = [k for k in self._store if k[1] == namespace]
            for k in to_remove:
                del self._store[k]


catalog_cache = EngineScopedCache(default_ttl=60.0)
discovery_cache = EngineScopedCache(default_ttl=60.0)
