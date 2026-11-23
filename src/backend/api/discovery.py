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
from src.backend.repositories.library import LibraryRepository
from src.backend.services.entity_resolution import EntityResolutionService
from src.backend.services.sources_registry import SourcesRegistryService

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
        has_media=True,
        media_sources=["eztv"],
        sources_count=1,
        source_provider="eztv-catalog",
        seasons=[],
    )


def _mark_eztv_availability(
    shows: list[UnifiedShow], eztv_session: Session
) -> list[UnifiedShow]:
    """Annotate online discovery shows with multi-source media availability from sources.db."""
    if not shows:
        return shows
    by_imdb, by_slug = DiscoveryEngineRepository.build_eztv_lookup_index(eztv_session)
    media_by_imdb = SourcesRegistryService.get_media_index_by_imdb(eztv_session)
    if not by_imdb and not by_slug and not media_by_imdb:
        return shows
    for show in shows:
        norm_imdb = EntityResolutionService.normalize_imdb_id(show.imdb_id)
        sources = set(media_by_imdb.get(norm_imdb, [])) if norm_imdb else set()
        if norm_imdb and norm_imdb in by_imdb:
            sources.add("eztv")
            show.eztv_available = True
        else:
            slug = DiscoveryEngineRepository._slugify(show.title)
            if slug and slug in by_slug:
                sources.add("eztv")
                show.eztv_available = True
        if sources:
            sorted_sources = sorted(sources)
            show.has_media = True
            show.media_sources = sorted_sources
            show.sources_count = len(sorted_sources)
    return shows


@router.get("/trending", response_model=list[UnifiedShow])
async def get_trending_shows(
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> list[UnifiedShow]:
    """Fetch trending titles from canonical mainstream.db or online discovery providers."""
    if DiscoveryEngineRepository._has_imdb_catalog(session):
        local_trending = DiscoveryEngineRepository.get_trending_unified_shows(
            session, eztv_session, limit=24
        )
        if local_trending:
            return local_trending

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
    """Bilingual (PT-BR & EN-US) relevance-ranked search across mainstream.db and sources.db."""
    if DiscoveryEngineRepository._has_imdb_catalog(session):
        mainstream_hits = DiscoveryEngineRepository.search_unified_shows(
            session=session,
            eztv_session=eztv_session,
            q=q,
            limit=40,
        )
        if mainstream_hits:
            return mainstream_hits

    service = get_discovery_service()
    results = await service.search_shows(q)
    if results:
        marked = _mark_eztv_availability(results, eztv_session)
        q_norm = DiscoveryEngineRepository._normalize_search_text(q)
        q_core = DiscoveryEngineRepository._strip_leading_article(q_norm)
        q_tokens = [t for t in q_norm.split() if len(t) >= 2]
        marked.sort(
            key=lambda s: DiscoveryEngineRepository.score_title_pair_relevance(
                q_norm=q_norm,
                q_core=q_core,
                q_tokens=q_tokens,
                titles=[s.title, s.original_title],
                credit_blob="",
                votes=1000,
                rating=float(s.rating or 0.0),
            ),
            reverse=True,
        )
        return marked

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
    provider: str = Query(
        "tmdb", description="Source provider (imdb, tmdb, tvmaze, or eztv-catalog)"
    ),
    tvmaze_id: Optional[int] = None,
    imdb_id: Optional[str] = Query(None, description="Optional IMDB identifier"),
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> UnifiedShow:
    """Fetch complete show metadata with seasons and episodes from mainstream.db or providers."""
    lib_repo = LibraryRepository(session)
    if provider == "imdb" or DiscoveryEngineRepository._has_imdb_catalog(session):
        mainstream_show = DiscoveryEngineRepository.get_unified_show_from_mainstream(
            session=session,
            eztv_session=eztv_session,
            show_id=show_id,
            imdb_id=imdb_id,
        )
        if mainstream_show is not None:
            return lib_repo.attach_library_watch_state(mainstream_show)

    service = get_discovery_service()

    effective_imdb = imdb_id
    if not effective_imdb and (provider == "eztv-catalog" or show_id > 1000):
        effective_imdb = CatalogRepository.normalize_imdb_id(str(show_id))

    if effective_imdb:
        detail = CatalogRepository.get_show_detail(eztv_session, session, effective_imdb)
        try:
            enriched = await service.get_show_details(imdb_id=effective_imdb)
            if enriched:
                return lib_repo.attach_library_watch_state(enriched)
        except Exception:
            pass

        if detail:
            return lib_repo.attach_library_watch_state(
                _catalog_item_to_unified(detail["show"], override_id=show_id)
            )

    try:
        if provider == "tvmaze":
            return lib_repo.attach_library_watch_state(
                await service.get_show_details(tvmaze_id=show_id)
            )
        return lib_repo.attach_library_watch_state(
            await service.get_show_details(tmdb_id=show_id, tvmaze_id=tvmaze_id)
        )
    except Exception as exc:
        candidate_imdb = CatalogRepository.normalize_imdb_id(str(show_id))
        detail = CatalogRepository.get_show_detail(eztv_session, session, candidate_imdb)
        if detail:
            return lib_repo.attach_library_watch_state(
                _catalog_item_to_unified(detail["show"], override_id=show_id)
            )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve show details for ID {show_id}: {exc}",
        ) from exc
