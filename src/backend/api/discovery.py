"""API endpoints for online media discovery with fallback."""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from src.backend.core.database import get_eztv_session, get_session
from src.backend.models.unified import UnifiedShow
from src.backend.providers.discovery_service import ResilientDiscoveryService
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider
from src.backend.repositories.catalog import CatalogRepository
from src.backend.repositories.discovery_engine import DiscoveryEngineRepository
from src.backend.services.entity_resolution import EntityResolutionService

router = APIRouter(prefix="/discovery", tags=["Discovery"])


def get_discovery_service() -> ResilientDiscoveryService:
    api_key = os.getenv("TMDB_API_KEY", "")
    tmdb = TMDBProvider(api_key=api_key)
    tvmaze = TVMazeProvider()
    return ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=2.0)


def _catalog_item_to_unified(
    item: dict[str, Any], override_id: Optional[int] = None
) -> UnifiedShow:
    """Convert serialized EZTV catalog show dict to UnifiedShow contract."""
    imdb_id = item.get("imdb_id") or ""
    raw_digits = imdb_id.replace("tt", "")
    fallback_id = int(raw_digits) if raw_digits.isdigit() else abs(hash(imdb_id)) % 1000000
    genres_raw = item.get("genres") or ""
    genres_list = [g.strip() for g in genres_raw.split(",") if g.strip()] if genres_raw else []
    network = item.get("network")
    providers = list(item.get("streaming_providers") or ([] if not network else [network]))
    return UnifiedShow(
        id=override_id if override_id is not None else fallback_id,
        imdb_id=imdb_id or None,
        tvmaze_id=item.get("tvmaze_id"),
        title=item["title"],
        original_title=item.get("original_title"),
        overview=item.get("overview") or "",
        poster_url=item.get("poster_url"),
        backdrop_url=item.get("backdrop_url"),
        rating=float(item.get("rating") or 0.0),
        genres=genres_list,
        first_air_date=item.get("first_air_date"),
        status=item.get("status"),
        network=network,
        streaming_providers=providers,
        eztv_available=True,
        source_provider="eztv-catalog",
        seasons=[],
    )


def _mark_eztv_availability(
    shows: list[UnifiedShow], eztv_session: Session
) -> list[UnifiedShow]:
    """Annotate online discovery shows with EZTV availability from eztv_metadata.db."""
    if not shows:
        return shows
    by_imdb, by_slug = DiscoveryEngineRepository.build_eztv_lookup_index(eztv_session)
    if not by_imdb and not by_slug:
        return shows
    for show in shows:
        norm_imdb = EntityResolutionService.normalize_imdb_id(show.imdb_id)
        if norm_imdb and norm_imdb in by_imdb:
            show.eztv_available = True
            continue
        slug = DiscoveryEngineRepository._slugify(show.title)
        if slug and slug in by_slug:
            show.eztv_available = True
    return shows


@router.get("/trending", response_model=list[UnifiedShow])
async def get_trending_shows(
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> list[UnifiedShow]:
    """Fetch currently trending TV shows across discovery providers with local catalog fallback."""
    service = get_discovery_service()
    results = await service.get_trending()
    if results:
        return _mark_eztv_availability(results, eztv_session)

    shows, _ = CatalogRepository.list_shows(
        eztv_session=eztv_session,
        p2p_session=session,
        min_seeds=1,
        sort_by="seeds",
        page_size=20,
    )
    return [_catalog_item_to_unified(s) for s in shows]


@router.get("/search", response_model=list[UnifiedShow])
async def search_shows(
    q: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> list[UnifiedShow]:
    """Search shows by title with automatic fallback to local catalog."""
    service = get_discovery_service()
    results = await service.search_shows(q)
    if results:
        return _mark_eztv_availability(results, eztv_session)

    shows, _ = CatalogRepository.list_shows(
        eztv_session=eztv_session,
        p2p_session=session,
        search=q,
        page_size=20,
    )
    return [_catalog_item_to_unified(s) for s in shows]


@router.get("/shows/{show_id}", response_model=UnifiedShow)
async def get_show_details(
    show_id: int,
    provider: str = Query("tmdb", description="Source provider (tmdb, tvmaze, or eztv-catalog)"),
    tvmaze_id: Optional[int] = None,
    imdb_id: Optional[str] = Query(None, description="Optional IMDB identifier"),
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> UnifiedShow:
    """Fetch complete show metadata including seasons and episodes."""
    service = get_discovery_service()

    effective_imdb = imdb_id
    if not effective_imdb and (provider == "eztv-catalog" or show_id > 1000):
        effective_imdb = CatalogRepository.normalize_imdb_id(str(show_id))

    if effective_imdb:
        detail = CatalogRepository.get_show_detail(eztv_session, session, effective_imdb)
        try:
            enriched = await service.get_show_details(imdb_id=effective_imdb)
            if enriched:
                return enriched
        except Exception:
            pass

        if detail:
            return _catalog_item_to_unified(detail["show"], override_id=show_id)

    try:
        if provider == "tvmaze":
            return await service.get_show_details(tvmaze_id=show_id)
        return await service.get_show_details(tmdb_id=show_id, tvmaze_id=tvmaze_id)
    except Exception as exc:
        candidate_imdb = CatalogRepository.normalize_imdb_id(str(show_id))
        detail = CatalogRepository.get_show_detail(eztv_session, session, candidate_imdb)
        if detail:
            return _catalog_item_to_unified(detail["show"], override_id=show_id)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve show details for ID {show_id}: {exc}",
        ) from exc
