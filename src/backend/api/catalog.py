"""FastAPI router for EZTV catalog endpoints backed by eztv_metadata.db."""

from __future__ import annotations

import math
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, col, select

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.database import get_eztv_session, get_session
from src.backend.models.db import CatalogRelease
from src.backend.models.eztv_db import EZTVEpisodeCatalog, EZTVShow
from src.backend.repositories.catalog import CatalogRepository
from src.backend.services.catalog_indexer import EZTVIndexerService
from src.backend.services.federated_catalog import FederatedCatalogService

router = APIRouter(prefix="/catalog", tags=["Catalog"])


class CatalogShowItem(BaseModel):
    eztv_show_id: int
    imdb_id: str
    slug: Optional[str] = None
    title: str
    original_title: Optional[str] = None
    overview: str = ""
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    rating: float = 0.0
    genres: str = ""
    first_air_date: Optional[str] = None
    status: Optional[str] = None
    network: Optional[str] = None
    streaming_providers: list[str] = []
    air_day_time: Optional[str] = None
    tvmaze_id: Optional[int] = None
    episodes_count: int = 0
    total_torrents: int = 0
    max_seeds: int = 0
    latest_season: int = 0
    latest_episode: int = 0
    latest_release_date: Optional[Any] = None
    is_enriched: bool = False


class CatalogPaginatedResponse(BaseModel):
    items: list[CatalogShowItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class CatalogShowDetailResponse(BaseModel):
    show: CatalogShowItem
    episodes: list[EZTVEpisodeCatalog]
    releases: list[CatalogRelease]


class CatalogGenreResponse(BaseModel):
    genre: str
    count: int


class CatalogSectionResponse(BaseModel):
    id: str
    title: str
    icon: str
    items: list[CatalogShowItem]


class CatalogSyncResponse(BaseModel):
    status: str
    telemetry: dict


@router.get("/shows", response_model=CatalogPaginatedResponse)
def list_catalog_shows(
    search: Optional[str] = Query(None, description="Filtrar por título ou IMDB ID"),
    genre: Optional[str] = Query(None, description="Filtrar por gênero"),
    min_seeds: int = Query(0, ge=0, description="Mínimo de seeds ativas"),
    sort_by: str = Query("seeds", description="Ordenação: seeds, date, torrents, rating, name"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Tamanho da página"),
    eztv_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
):
    """List TV shows from eztv_metadata.db with optional P2P seed telemetry."""
    items, total = CatalogRepository.list_shows(
        eztv_session=eztv_session,
        p2p_session=session,
        search=search,
        genre=genre,
        min_seeds=min_seeds,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return CatalogPaginatedResponse(
        items=[CatalogShowItem(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/shows/{identifier}", response_model=CatalogShowDetailResponse)
def get_catalog_show(
    identifier: str,
    eztv_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
):
    """Get EZTV show metadata, cataloged episodes, and indexed P2P releases."""
    detail = CatalogRepository.get_show_detail(eztv_session, session, identifier)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Série {identifier} não encontrada no catálogo EZTV.",
        )

    return CatalogShowDetailResponse(
        show=CatalogShowItem(**detail["show"]),
        episodes=detail["episodes"],
        releases=detail["releases"],
    )


@router.get("/genres", response_model=list[CatalogGenreResponse])
def get_catalog_genres(eztv_session: Session = Depends(get_eztv_session)):
    """List all available genres in eztv_metadata.db with show counts."""
    return CatalogRepository.get_genres_with_counts(eztv_session)


@router.get("/sections", response_model=list[CatalogSectionResponse])
def get_curated_sections(
    eztv_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
):
    """Get curated show sections from eztv_metadata.db."""
    return CatalogRepository.get_curated_sections(eztv_session, session)


@router.get("/stats")
def get_catalog_stats(
    eztv_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
):
    """Get global catalog metrics and statistics across eztv_metadata.db and P2P index."""
    return CatalogRepository.get_stats(eztv_session, session)


@router.post("/sync", response_model=CatalogSyncResponse)
async def sync_catalog(
    start_page: int = Query(1, ge=1, description="Página inicial do EZTV"),
    pages: int = Query(5, ge=1, le=100, description="Quantidade de páginas para ler"),
    enrich: bool = Query(True, description="Enriquecer metadados via TVMaze/TMDB"),
    eztv_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
):
    """Trigger on-demand synchronization of EZTV P2P releases into sources.db & mainstream.db."""
    indexer = EZTVIndexerService()
    # Sync into primary session and mirror into sources.db when separated
    telemetry = await indexer.sync_pages(
        session=session,
        start_page=start_page,
        max_pages=pages,
        enrich_metadata=enrich,
    )
    if eztv_session is not session:
        try:
            await indexer.sync_pages(
                session=eztv_session,
                start_page=start_page,
                max_pages=pages,
                enrich_metadata=False,
            )
            await FederatedCatalogService().update_mainstream_catalog(
                session=session,
                eztv_session=eztv_session,
                mode="badges",
                limit=0,
            )
        except Exception:
            pass
    catalog_cache.invalidate()
    discovery_cache.invalidate()
    return CatalogSyncResponse(status="success", telemetry=telemetry)


@router.post("/enrich-pending", response_model=dict)
async def enrich_pending_catalog(
    limit: int = Query(100, ge=1, le=500, description="Limite de séries a enriquecer"),
    eztv_session: Session = Depends(get_eztv_session),
):
    """Fill metadata gaps in eztv_metadata.db using TVMaze and TMDB providers."""
    indexer = EZTVIndexerService()
    pending = list(
        eztv_session.exec(
            select(EZTVShow)
            .where(
                col(EZTVShow.poster_url).is_(None)
                | (EZTVShow.poster_url == "")
                | col(EZTVShow.synopsis).is_(None)
                | (EZTVShow.synopsis == "")
            )
            .limit(limit)
        ).all()
    )
    enriched_count = 0
    for show in pending:
        metadata = None
        if show.imdb_id:
            metadata = await indexer.enrich_show_metadata(show.imdb_id)
        if not metadata and show.name:
            matches = await indexer.tvmaze.search_shows(show.name)
            if matches:
                top = matches[0]
                metadata = {
                    "title": top.title,
                    "overview": top.overview,
                    "poster_url": top.poster_url,
                    "rating": top.rating,
                    "genres": ", ".join(top.genres),
                    "first_air_date": top.first_air_date,
                    "status": top.status,
                    "imdb_id": top.imdb_id,
                    "tvmaze_id": top.tvmaze_id,
                }
        if metadata:
            show.poster_url = show.poster_url or metadata.get("poster_url")
            show.synopsis = show.synopsis or metadata.get("overview")
            show.genres = show.genres or metadata.get("genres")
            show.rating_score = show.rating_score or metadata.get("rating")
            show.premiered = show.premiered or metadata.get("first_air_date")
            if (not show.status or show.status == "Unknown") and metadata.get("status"):
                show.status = metadata["status"]
            if not show.imdb_id and metadata.get("imdb_id"):
                show.imdb_id = CatalogRepository.normalize_imdb_id(metadata["imdb_id"])
            if not show.tvmaze_id and metadata.get("tvmaze_id"):
                show.tvmaze_id = metadata["tvmaze_id"]
            eztv_session.add(show)
            enriched_count += 1

    eztv_session.commit()
    catalog_cache.invalidate()
    discovery_cache.invalidate()
    return {"status": "success", "shows_enriched": enriched_count}
