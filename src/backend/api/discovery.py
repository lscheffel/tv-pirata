"""API endpoints for online media discovery with fallback."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.backend.models.unified import UnifiedShow
from src.backend.providers.discovery_service import ResilientDiscoveryService
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider

router = APIRouter(prefix="/discovery", tags=["Discovery"])


def get_discovery_service() -> ResilientDiscoveryService:
    api_key = os.getenv("TMDB_API_KEY", "")
    tmdb = TMDBProvider(api_key=api_key)
    tvmaze = TVMazeProvider()
    return ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=2.0)


@router.get("/trending", response_model=list[UnifiedShow])
async def get_trending_shows() -> list[UnifiedShow]:
    """Fetch currently trending TV shows across discovery providers."""
    service = get_discovery_service()
    return await service.get_trending()


@router.get("/search", response_model=list[UnifiedShow])
async def search_shows(q: str = Query(..., min_length=1)) -> list[UnifiedShow]:
    """Search shows by title with automatic fallback."""
    service = get_discovery_service()
    return await service.search_shows(q)


@router.get("/shows/{show_id}", response_model=UnifiedShow)
async def get_show_details(
    show_id: int,
    provider: str = Query("tmdb", description="Source provider (tmdb or tvmaze)"),
    tvmaze_id: Optional[int] = None,
) -> UnifiedShow:
    """Fetch complete show metadata including seasons and episodes."""
    service = get_discovery_service()
    try:
        if provider == "tvmaze":
            return await service.get_show_details(tvmaze_id=show_id)
        return await service.get_show_details(tmdb_id=show_id, tvmaze_id=tvmaze_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Show not found: {exc}") from exc

