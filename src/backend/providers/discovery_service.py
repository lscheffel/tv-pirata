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
            try:
                return await asyncio.wait_for(
                    self.fallback.search_shows(query),
                    timeout=self.timeout_seconds,
                )
            except Exception as fallback_exc:
                logger.error(
                    "Fallback provider (TVMaze) failed for search '%s': %s", query, fallback_exc
                )
                return []

    async def get_show_details(
        self,
        tmdb_id: Optional[int] = None,
        tvmaze_id: Optional[int] = None,
        imdb_id: Optional[str] = None,
        query_fallback: Optional[str] = None,
    ) -> UnifiedShow:
        """Fetch show details using primary ID with seamless fallback."""
        if imdb_id:
            try:
                enriched = await asyncio.wait_for(
                    self.fallback.lookup_by_imdb(imdb_id),
                    timeout=self.timeout_seconds,
                )
                if enriched:
                    return enriched
            except Exception as exc:
                logger.warning("TVMaze lookup_by_imdb failed for %s: %s", imdb_id, exc)

            try:
                enriched_tmdb = await asyncio.wait_for(
                    self.primary.lookup_by_imdb(imdb_id),
                    timeout=self.timeout_seconds,
                )
                if enriched_tmdb:
                    return enriched_tmdb
            except Exception as exc:
                logger.warning("TMDB lookup_by_imdb failed for %s: %s", imdb_id, exc)

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
            try:
                return await asyncio.wait_for(
                    self.fallback.get_show_details(tvmaze_id),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:
                logger.warning("TVMaze get_show_details failed for id=%s: %s", tvmaze_id, exc)

        if query_fallback:
            try:
                results = await self.fallback.search_shows(query_fallback)
                if results:
                    return results[0]
            except Exception:
                pass

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
            try:
                return await asyncio.wait_for(
                    self.fallback.get_trending(),
                    timeout=self.timeout_seconds,
                )
            except Exception as fallback_exc:
                logger.error("Fallback provider (TVMaze) failed for trending: %s", fallback_exc)
                return []
