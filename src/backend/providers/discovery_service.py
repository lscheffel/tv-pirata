"""Resilient discovery service orchestrating primary and fallback providers."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.backend.models.unified import UnifiedShow
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider

logger = logging.getLogger(__name__)


class ResilientDiscoveryService:
    """Orchestrates metadata providers enforcing circuit protection and fallback."""

    def __init__(
        self,
        primary: TMDBProvider,
        fallback: TVMazeProvider,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.timeout_seconds = timeout_seconds

    async def search_shows(self, query: str) -> list[UnifiedShow]:
        """Search shows with automatic fallback from TMDB to TVMaze."""
        try:
            return await asyncio.wait_for(
                self.primary.search_shows(query),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            logger.warning(
                "Primary provider (TMDB) failed for search '%s' (%s). Falling back to TVMaze.",
                query,
                exc,
            )
            return await self.fallback.search_shows(query)

    async def get_show_details(
        self,
        tmdb_id: Optional[int] = None,
        tvmaze_id: Optional[int] = None,
        query_fallback: Optional[str] = None,
    ) -> UnifiedShow:
        """Fetch show details using primary ID with seamless fallback."""
        if tmdb_id:
            try:
                return await asyncio.wait_for(
                    self.primary.get_show_details(tmdb_id),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "Primary provider (TMDB) failed for id=%s (%s). Engaging fallback.",
                    tmdb_id,
                    exc,
                )

        if tvmaze_id:
            return await self.fallback.get_show_details(tvmaze_id)

        if query_fallback:
            results = await self.fallback.search_shows(query_fallback)
            if results:
                return results[0]

        raise ValueError("Cannot fetch show details: all providers exhausted without valid ID.")

    async def get_trending(self) -> list[UnifiedShow]:
        """Fetch trending shows with fallback."""
        try:
            return await asyncio.wait_for(
                self.primary.get_trending(),
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            logger.warning(
                "Primary provider (TMDB) failed for trending (%s). Falling back to TVMaze.",
                exc,
            )
            return await self.fallback.get_trending()

