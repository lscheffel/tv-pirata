"""FastAPI router for multi-provider Fontes de Dados & dynamic plugin management (ADR-013)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlmodel import Session

from src.backend.core.database import get_eztv_session, get_session
from src.backend.services.sources_registry import SourcesRegistryService

router = APIRouter(prefix="/sources", tags=["Fontes de Dados & Plugins"])


@router.get("/adapters")
def list_source_adapters() -> dict[str, Any]:
    """Return autodiscovered BaseSourceAdapter definitions and their dynamic JSON schemas."""
    return SourcesRegistryService.list_adapters_metadata()


@router.get("/summary")
def get_sources_summary(
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Return registry status, masked configs, and live release/title counts for every source."""
    return SourcesRegistryService.get_summary(sources_session)


@router.post("")
def create_source_instance(
    payload: dict[str, Any] = Body(...),
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Create a new configured external source instance from a registered adapter."""
    try:
        return SourcesRegistryService.create_instance(sources_session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{source_key}")
def update_source_instance(
    source_key: str,
    payload: dict[str, Any] = Body(...),
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Update an external source instance (preserving masked secret fields)."""
    try:
        return SourcesRegistryService.update_instance(sources_session, source_key, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{source_key}")
def delete_source_instance(
    source_key: str,
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Delete a custom external source instance and its cached releases."""
    try:
        return SourcesRegistryService.delete_instance(sources_session, source_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{source_key}/test")
async def test_source_instance(
    source_key: str,
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Execute on-demand connectivity/healthcheck for a configured source instance."""
    try:
        return await SourcesRegistryService.test_instance(sources_session, source_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/releases")
async def get_source_releases(
    imdb_id: str = Query(..., min_length=2, description="IMDb ID normalizado (ex: tt0944947)"),
    source: Optional[str] = Query(None, description="Filtrar provedor ou all"),
    limit: int = Query(100, ge=1, le=200),
    include_live: bool = Query(
        True, description="Consultar adaptadores quando cache local estiver vazio ou expirado"
    ),
    live: Optional[str] = Query(
        None, description="Modo Lazy-Cache: auto, cache ou force"
    ),
    q_override: Optional[str] = Query(
        None, description="Termo manual de busca para refinar resultados na fonte"
    ),
    title: Optional[str] = Query(None, description="Título opcional da obra"),
    year: Optional[int] = Query(None, description="Ano opcional da obra"),
    sources_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve available releases/links with Lazy-Cache (TTL 24h) and source diagnostics."""
    return await SourcesRegistryService.get_releases_for_imdb(
        sources_session=sources_session,
        mainstream_session=session,
        imdb_id=imdb_id,
        source=source,
        limit=limit,
        include_live=include_live,
        live_mode=live,
        q_override=q_override,
        title=title,
        year=year,
    )


@router.get("/catalog")
def list_sources_catalog(
    source: Optional[str] = Query(None, description="Provedor: all, eztv, yify, 1337x..."),
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
    source: str = Query("eztv", description="Fonte para sincronizar (eztv, yify, all, etc.)"),
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
