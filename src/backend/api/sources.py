"""FastAPI router for multi-provider Fontes de Dados endpoints (ADR-012)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from src.backend.core.database import get_eztv_session, get_session
from src.backend.services.sources_registry import SourcesRegistryService

router = APIRouter(prefix="/sources", tags=["Fontes de Dados"])


@router.get("/summary")
def get_sources_summary(
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Return registry status and live release/title counts for every data source."""
    return SourcesRegistryService.get_summary(sources_session)


@router.get("/releases")
async def get_source_releases(
    imdb_id: str = Query(..., min_length=2, description="IMDb ID normalizado (ex: tt0944947)"),
    source: Optional[str] = Query(None, description="Filtrar provedor: eztv, yify, 1337x ou all"),
    limit: int = Query(100, ge=1, le=200),
    include_live: bool = Query(
        True, description="Consultar API remota quando cache local estiver vazio"
    ),
    sources_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve available releases/links for a title grouped by source provider."""
    return await SourcesRegistryService.get_releases_for_imdb(
        sources_session=sources_session,
        mainstream_session=session,
        imdb_id=imdb_id,
        source=source,
        limit=limit,
        include_live=include_live,
    )


@router.get("/catalog")
def list_sources_catalog(
    source: Optional[str] = Query(None, description="Provedor: all, eztv, yify, 1337x"),
    search: Optional[str] = Query(None, description="Filtrar por título ou IMDb ID"),
    genre: Optional[str] = Query(None, description="Filtrar por gênero"),
    min_seeds: int = Query(0, ge=0),
    sort_by: str = Query("seeds", description="Ordenação: seeds, date, torrents, rating, name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    sources_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List unified multi-source catalog items across registered external providers."""
    return SourcesRegistryService.list_catalog(
        sources_session=sources_session,
        mainstream_session=session,
        source=source,
        search=search,
        genre=genre,
        min_seeds=min_seeds,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.post("/sync")
async def sync_external_sources(
    source: str = Query("eztv", description="Fonte para sincronizar (eztv, yify, 1337x, all)"),
    pages: int = Query(5, ge=1, le=100),
    enrich: bool = Query(True),
    sources_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Trigger on-demand synchronization for one or all external source providers."""
    try:
        return await SourcesRegistryService.sync_source(
            sources_session=sources_session,
            mainstream_session=session,
            source_key=source,
            pages=pages,
            enrich=enrich,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
