"""API endpoints for online media discovery with fallback."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from src.backend.core.database import get_session
from src.backend.models.unified import UnifiedShow
from src.backend.providers.discovery_service import ResilientDiscoveryService
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider
from src.backend.repositories.catalog import CatalogRepository

router = APIRouter(prefix="/discovery", tags=["Discovery"])


def get_discovery_service() -> ResilientDiscoveryService:
    api_key = os.getenv("TMDB_API_KEY", "")
    tmdb = TMDBProvider(api_key=api_key)
    tvmaze = TVMazeProvider()
    return ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=2.0)


@router.get("/trending", response_model=list[UnifiedShow])
async def get_trending_shows(session: Session = Depends(get_session)) -> list[UnifiedShow]:
    """Fetch currently trending TV shows across discovery providers with local catalog fallback."""
    service = get_discovery_service()
    results = await service.get_trending()
    if results:
        return results

    # Resilient fallback: If external providers fail or timeout,
    # supply top seeded shows from local catalog
    shows, _ = CatalogRepository.list_shows(session, min_seeds=1, sort_by="seeds", page_size=20)
    unified_list: list[UnifiedShow] = []
    for s in shows:
        genres_list = [g.strip() for g in s.genres.split(",") if g.strip()] if s.genres else []
        unified_list.append(
            UnifiedShow(
                id=int(s.imdb_id.replace("tt", ""))
                if s.imdb_id.replace("tt", "").isdigit()
                else abs(hash(s.imdb_id)) % 1000000,
                imdb_id=s.imdb_id,
                title=s.title,
                original_title=s.original_title,
                overview=s.overview,
                poster_url=s.poster_url,
                backdrop_url=s.backdrop_url,
                rating=s.rating,
                genres=genres_list,
                first_air_date=s.first_air_date,
                status=s.status,
                source_provider="eztv-catalog",
                seasons=[],
            )
        )
    return unified_list


@router.get("/search", response_model=list[UnifiedShow])
async def search_shows(
    q: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
) -> list[UnifiedShow]:
    """Search shows by title with automatic fallback to local catalog."""
    service = get_discovery_service()
    results = await service.search_shows(q)
    if results:
        return results

    # Fallback to local catalog
    shows, _ = CatalogRepository.list_shows(session, search=q, page_size=20)
    unified_list: list[UnifiedShow] = []
    for s in shows:
        genres_list = [g.strip() for g in s.genres.split(",") if g.strip()] if s.genres else []
        unified_list.append(
            UnifiedShow(
                id=int(s.imdb_id.replace("tt", ""))
                if s.imdb_id.replace("tt", "").isdigit()
                else abs(hash(s.imdb_id)) % 1000000,
                imdb_id=s.imdb_id,
                title=s.title,
                original_title=s.original_title,
                overview=s.overview,
                poster_url=s.poster_url,
                backdrop_url=s.backdrop_url,
                rating=s.rating,
                genres=genres_list,
                first_air_date=s.first_air_date,
                status=s.status,
                source_provider="eztv-catalog",
                seasons=[],
            )
        )
    return unified_list


@router.get("/shows/{show_id}", response_model=UnifiedShow)
async def get_show_details(
    show_id: int,
    provider: str = Query("tmdb", description="Source provider (tmdb, tvmaze, or eztv-catalog)"),
    tvmaze_id: Optional[int] = None,
    imdb_id: Optional[str] = Query(None, description="Optional IMDB identifier"),
    session: Session = Depends(get_session),
) -> UnifiedShow:
    """Fetch complete show metadata including seasons and episodes."""
    service = get_discovery_service()

    # Determine effective IMDB ID
    effective_imdb = imdb_id
    if not effective_imdb and (provider == "eztv-catalog" or show_id > 1000):
        effective_imdb = CatalogRepository.normalize_imdb_id(str(show_id))

    # If IMDB is available, attempt enrichment through TVMaze/TMDB or local catalog
    if effective_imdb:
        cat_show = CatalogRepository.get_show(session, effective_imdb)
        try:
            enriched = await service.get_show_details(imdb_id=effective_imdb)
            if enriched:
                return enriched
        except Exception:
            pass

        if cat_show:
            genres_list = (
                [g.strip() for g in cat_show.genres.split(",") if g.strip()]
                if cat_show.genres
                else []
            )
            return UnifiedShow(
                id=show_id,
                imdb_id=cat_show.imdb_id,
                title=cat_show.title,
                original_title=cat_show.original_title,
                overview=cat_show.overview,
                poster_url=cat_show.poster_url,
                backdrop_url=cat_show.backdrop_url,
                rating=cat_show.rating,
                genres=genres_list,
                first_air_date=cat_show.first_air_date,
                status=cat_show.status,
                source_provider="eztv-catalog",
                seasons=[],
            )

    try:
        if provider == "tvmaze":
            return await service.get_show_details(tvmaze_id=show_id)
        return await service.get_show_details(tmdb_id=show_id, tvmaze_id=tvmaze_id)
    except Exception as exc:
        # Final fallback check: is show_id an IMDB ID in catalog?
        candidate_imdb = CatalogRepository.normalize_imdb_id(str(show_id))
        cat_show = CatalogRepository.get_show(session, candidate_imdb)
        if cat_show:
            genres_list = (
                [g.strip() for g in cat_show.genres.split(",") if g.strip()]
                if cat_show.genres
                else []
            )
            return UnifiedShow(
                id=show_id,
                imdb_id=cat_show.imdb_id,
                title=cat_show.title,
                original_title=cat_show.original_title,
                overview=cat_show.overview,
                poster_url=cat_show.poster_url,
                backdrop_url=cat_show.backdrop_url,
                rating=cat_show.rating,
                genres=genres_list,
                first_air_date=cat_show.first_air_date,
                status=cat_show.status,
                source_provider="eztv-catalog",
                seasons=[],
            )
        raise HTTPException(status_code=404, detail=f"Show not found: {exc}") from exc
