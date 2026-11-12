"""FastAPI router for EZTV catalog endpoints."""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from src.backend.core.database import get_session
from src.backend.models.db import CatalogRelease, CatalogShow
from src.backend.repositories.catalog import CatalogRepository
from src.backend.services.catalog_indexer import EZTVIndexerService

router = APIRouter(prefix="/catalog", tags=["Catalog"])


class CatalogPaginatedResponse(BaseModel):
    items: list[CatalogShow]
    total: int
    page: int
    page_size: int
    total_pages: int


class CatalogShowDetailResponse(BaseModel):
    show: CatalogShow
    releases: list[CatalogRelease]


class CatalogGenreResponse(BaseModel):
    genre: str
    count: int


class CatalogSectionResponse(BaseModel):
    id: str
    title: str
    icon: str
    items: list[CatalogShow]


class CatalogSyncResponse(BaseModel):
    status: str
    telemetry: dict


@router.get("/shows", response_model=CatalogPaginatedResponse)
def list_catalog_shows(
    search: Optional[str] = Query(None, description="Filtrar por título ou IMDB ID"),
    genre: Optional[str] = Query(None, description="Filtrar por gênero"),
    min_seeds: int = Query(0, ge=0, description="Mínimo de seeds ativas"),
    sort_by: str = Query("seeds", description="Ordenação: seeds, date, torrents, rating"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Tamanho da página"),
    session: Session = Depends(get_session),
):
    """List TV shows with real torrents available on EZTV."""
    items, total = CatalogRepository.list_shows(
        session=session,
        search=search,
        genre=genre,
        min_seeds=min_seeds,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return CatalogPaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/shows/{imdb_id}", response_model=CatalogShowDetailResponse)
def get_catalog_show(
    imdb_id: str,
    session: Session = Depends(get_session),
):
    """Get catalog show metadata and all indexed releases."""
    show = CatalogRepository.get_show(session, imdb_id)
    if not show:
        raise HTTPException(status_code=404, detail=f"Série {imdb_id} não encontrada no catálogo.")

    releases = CatalogRepository.get_show_releases(session, imdb_id)
    return CatalogShowDetailResponse(show=show, releases=releases)


@router.get("/genres", response_model=list[CatalogGenreResponse])
def get_catalog_genres(session: Session = Depends(get_session)):
    """List all available genres in the catalog with show counts."""
    return CatalogRepository.get_genres_with_counts(session)


@router.get("/sections", response_model=list[CatalogSectionResponse])
def get_curated_sections(session: Session = Depends(get_session)):
    """Get curated show sections for the streaming dashboard."""
    return CatalogRepository.get_curated_sections(session)


@router.get("/stats")
def get_catalog_stats(session: Session = Depends(get_session)):
    """Get global catalog metrics and statistics."""
    return CatalogRepository.get_stats(session)


@router.post("/sync", response_model=CatalogSyncResponse)
async def sync_catalog(
    start_page: int = Query(1, ge=1, description="Página inicial do EZTV"),
    pages: int = Query(5, ge=1, le=100, description="Quantidade de páginas para ler"),
    enrich: bool = Query(True, description="Enriquecer metadados via TVMaze/TMDB"),
    session: Session = Depends(get_session),
):
    """Trigger on-demand synchronization of EZTV releases into the local catalog."""
    indexer = EZTVIndexerService()
    telemetry = await indexer.sync_pages(
        session=session,
        start_page=start_page,
        max_pages=pages,
        enrich_metadata=enrich,
    )
    return CatalogSyncResponse(status="success", telemetry=telemetry)


@router.post("/enrich-pending", response_model=dict)
async def enrich_pending_catalog(
    limit: int = Query(100, ge=1, le=500, description="Limite de séries a enriquecer"),
    session: Session = Depends(get_session),
):
    """Enrich shows in the catalog that are missing posters or metadata."""
    indexer = EZTVIndexerService()
    enriched_count = await indexer.enrich_pending_shows(session=session, limit=limit)
    return {"status": "success", "shows_enriched": enriched_count}
