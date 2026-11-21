"""Per-event-loop domain semaphore registry & shared Keep-Alive HTTP client (ADR-017)."""

from __future__ import annotations

import asyncio
import weakref
from typing import Optional

import httpx

DOMAIN_CONCURRENCY_LIMITS: dict[str, int] = {
    "tmdb": 8,
    "yify": 4,
    "tgx": 4,
    "glodls": 4,
    "sidecar": 4,
    "wikipedia": 4,
    "nyaasi": 1,
    "bitsearch": 1,
    "imdb": 2,
    "tvmaze": 2,
    "jikan": 2,
    "wikidata": 2,
}


class DomainSemaphoreRegistry:
    """Provides asyncio.Semaphore instances scoped per active event loop (WeakKeyDictionary)."""

    def __init__(self, limits: Optional[dict[str, int]] = None) -> None:
        self._limits = dict(limits or DOMAIN_CONCURRENCY_LIMITS)
        self._by_loop: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, dict[str, asyncio.Semaphore]
        ] = weakref.WeakKeyDictionary()

    def get(self, domain: str, *, default_limit: int = 3) -> asyncio.Semaphore:
        """Return or lazily create the semaphore for `domain` in the running event loop."""
        loop = asyncio.get_running_loop()
        loop_map = self._by_loop.get(loop)
        if loop_map is None:
            loop_map = {}
            self._by_loop[loop] = loop_map
        key = domain.strip().lower()
        sem = loop_map.get(key)
        if sem is None:
            limit = max(1, int(self._limits.get(key, default_limit)))
            sem = asyncio.Semaphore(limit)
            loop_map[key] = sem
        return sem


domain_semaphores = DomainSemaphoreRegistry()


def create_shared_http_client(
    *,
    timeout: float = 8.0,
    headers: Optional[dict[str, str]] = None,
) -> httpx.AsyncClient:
    """Create a Keep-Alive pooled httpx.AsyncClient for Fan-out HTTP stages."""
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
    )
