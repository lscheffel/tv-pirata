"""FastAPI router for the Layer 1 Audiovisual Discovery Core (ADR-008)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.database import get_eztv_session, get_session
from src.backend.repositories.discovery_engine import DiscoveryEngineRepository
from src.backend.repositories.preferences import (
    ExplorePreferencesRepository,
    UserExplorePreferences,
)
from src.backend.services.federated_catalog import FederatedCatalogService
from src.backend.services.hydration_orchestrator import (
    HydrationPipelineStatus,
    hydration_orchestrator,
)

router = APIRouter(prefix="/explore", tags=["Audiovisual Discovery Engine"])


def _ensure_seeded(session: Session) -> None:
    """Ensure the federated catalog is seeded in the active session."""
    FederatedCatalogService().ensure_federated_catalog_seeded(session)


@router.get("/works")
def explore_works(
    q: Optional[str] = Query(
        None, description="Busca textual em títulos, sinopses, franquias e elenco"
    ),
    work_types: Optional[str] = Query(
        None,
        description="Tipos separados por vírgula: movie,tv_show,mini_series,documentary,animation",
    ),
    genres_any: Optional[str] = Query(None, description="Gêneros com operador OR"),
    genres_all: Optional[str] = Query(None, description="Gêneros com operador AND"),
    genres_not: Optional[str] = Query(None, description="Gêneros excluídos com operador NOT"),
    year_from: Optional[int] = Query(None, description="Ano inicial de lançamento"),
    year_to: Optional[int] = Query(None, description="Ano final de lançamento"),
    min_rating: Optional[float] = Query(None, ge=0.0, le=10.0, description="Nota canônica mínima"),
    max_rating: Optional[float] = Query(None, ge=0.0, le=10.0, description="Nota canônica máxima"),
    min_runtime: Optional[int] = Query(None, ge=0, description="Duração mínima em minutos"),
    max_runtime: Optional[int] = Query(None, ge=0, description="Duração máxima em minutos"),
    status: Optional[str] = Query(None, description="Status de produção ou exibição"),
    streaming_providers: Optional[str] = Query(
        None,
        description="Plataformas de streaming (Netflix, Prime Video, Max, Apple TV+, MUBI)",
    ),
    territory: Optional[str] = Query(None, description="Território de disponibilidade (BR, US)"),
    country: Optional[str] = Query(None, description="País de origem (US, GB, KR, DE, BR)"),
    language: Optional[str] = Query(None, description="Idioma original (en, ko, de, pt)"),
    person_query: Optional[str] = Query(
        None, description="Nome de ator, diretor, roteirista ou criador"
    ),
    role_type: Optional[str] = Query(
        None, description="Papel da pessoa: director, actor, writer, creator"
    ),
    min_seasons: Optional[int] = Query(None, ge=0, description="Quantidade mínima de temporadas"),
    exclude_watched: bool = Query(
        False, description="Ocultar obras já assistidas ou em acompanhamento"
    ),
    only_with_p2p: bool = Query(False, description="Restringir a obras com seeds P2P ativos"),
    data_sources: Optional[str] = Query(
        None,
        description=(
            "Fontes de dados: eztv,p2p_active,imdb,tmdb,tvmaze,ptbr,"
            "youtube_trailer,personal_library"
        ),
    ),
    sort_by: str = Query(
        "rating", description="Ordenação: rating, popularity, year_desc, year_asc, runtime, title"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Query the unified audiovisual catalog with boolean/relational filters and dynamic facets."""
    _ensure_seeded(session)
    return DiscoveryEngineRepository.query_works(
        session=session,
        eztv_session=eztv_session,
        q=q,
        work_types=work_types,
        genres_any=genres_any,
        genres_all=genres_all,
        genres_not=genres_not,
        year_from=year_from,
        year_to=year_to,
        min_rating=min_rating,
        max_rating=max_rating,
        min_runtime=min_runtime,
        max_runtime=max_runtime,
        status=status,
        streaming_providers=streaming_providers,
        territory=territory,
        country=country,
        language=language,
        person_query=person_query,
        role_type=role_type,
        min_seasons=min_seasons,
        exclude_watched=exclude_watched,
        only_with_p2p=only_with_p2p,
        data_sources=data_sources,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


@router.get("/works/{work_id}")
def get_work_dossier(
    work_id: str,
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Retrieve complete canonical dossier for an audiovisual work (numeric ID or ttXXXXXXX)."""
    _ensure_seeded(session)
    parsed_id: int | str = int(work_id) if work_id.isdigit() else work_id
    dossier = DiscoveryEngineRepository.get_work_dossier(
        session, parsed_id, eztv_session=eztv_session
    )
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Obra canônica #{work_id} não encontrada.")
    return dossier


@router.get("/people")
def list_people(
    q: Optional[str] = Query(None, description="Filtrar por nome da pessoa"),
    department: Optional[str] = Query(None, description="Departamento: Directing, Acting, Writing"),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """List directors, creators, writers, and actors indexed in the discovery engine."""
    _ensure_seeded(session)
    return DiscoveryEngineRepository.list_people(session, q=q, department=department)


@router.get("/people/collaborations")
def find_collaborations(
    person_a: str = Query(..., min_length=2, description="Primeira pessoa (ex: Denis Villeneuve)"),
    person_b: str = Query(..., min_length=2, description="Segunda pessoa (ex: Rebecca Ferguson)"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Find all works in which two professionals collaborated."""
    _ensure_seeded(session)
    return DiscoveryEngineRepository.find_shared_collaborations(session, person_a, person_b)


@router.get("/people/{person_id}")
def get_person_dossier(
    person_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve complete filmography and frequent collaborators for a person."""
    _ensure_seeded(session)
    dossier = DiscoveryEngineRepository.get_person_dossier(session, person_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Pessoa #{person_id} não encontrada.")
    return dossier


@router.get("/calendar")
def get_release_calendar(
    work_type: Optional[str] = Query(None, description="Filtrar por tipo de obra"),
    event_type: Optional[str] = Query(None, description="Filtrar por tipo de evento"),
    confidence_level: Optional[str] = Query(
        None, description="Filtrar por nível de confiança: confirmed, estimated, announced"
    ),
    platform: Optional[str] = Query(None, description="Filtrar por plataforma ou cinema"),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Retrieve unified audiovisual release and premiere calendar."""
    _ensure_seeded(session)
    return DiscoveryEngineRepository.get_calendar_events(
        session=session,
        work_type=work_type,
        event_type=event_type,
        confidence_level=confidence_level,
        platform=platform,
    )


@router.get("/rankings")
def get_discovery_rankings(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve multi-perspective rankings and highlights."""
    _ensure_seeded(session)
    return DiscoveryEngineRepository.get_rankings_perspectives(session)


@router.post("/federate")
async def federate_catalog(
    q: Optional[str] = Query(None, description="Termo opcional para ingestão federada externa"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Synchronize local ecosystem into canonical catalog and ingest external connectors."""
    service = FederatedCatalogService()
    seed_stats = service.ensure_federated_catalog_seeded(session, force=True)
    live_ingested = 0
    if q:
        live_ingested = await service.federate_live_query(session, q)
    discovery_cache.invalidate()
    return {
        "status": "federated",
        "seed_telemetry": seed_stats,
        "live_ingested": live_ingested,
    }


@router.get("/mainstream-stats")
def get_mainstream_stats(
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Retrieve statistics for the canonical database (data/mainstream.db)."""
    return FederatedCatalogService().get_mainstream_stats(session)


@router.post("/update-mainstream")
async def update_mainstream_database(
    mode: str = Query(
        "delta", description="Modo de atualização: delta, hydrate ou badges"
    ),
    limit: int = Query(25, ge=1, le=200, description="Lote de títulos para hidratação"),
    session: Session = Depends(get_session),
    eztv_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Update canonical database (data/mainstream.db): cross-ref EZTV badges & hydrate metadata."""
    service = FederatedCatalogService()
    result = await service.update_mainstream_catalog(
        session=session,
        eztv_session=eztv_session,
        mode=mode,
        limit=limit,
    )
    discovery_cache.invalidate()
    catalog_cache.invalidate()
    return result


@router.get("/preferences", response_model=UserExplorePreferences)
def get_explore_preferences(
    session: Session = Depends(get_session),
) -> UserExplorePreferences:
    """Retrieve persisted UI/interaction preferences from data/mainstream.db sync_state."""
    return ExplorePreferencesRepository.get_preferences(session)


@router.put("/preferences", response_model=UserExplorePreferences)
def update_explore_preferences(
    prefs: UserExplorePreferences,
    session: Session = Depends(get_session),
) -> UserExplorePreferences:
    """Validate and persist UI/interaction preferences into data/mainstream.db sync_state."""
    return ExplorePreferencesRepository.save_preferences(session, prefs)


@router.get("/hydration/status", response_model=HydrationPipelineStatus)
def get_hydration_status(
    session: Session = Depends(get_session),
    sources_session: Session = Depends(get_eztv_session),
) -> HydrationPipelineStatus:
    """Return real-time 3-pillar maturity, cursor checkpoints and 6-tier provenance."""
    return hydration_orchestrator.get_status(session, sources_session)


@router.post("/hydration/start", response_model=HydrationPipelineStatus)
async def start_hydration_pipeline(
    scope: Literal["all", "sources", "metadata"] = Query(
        "all", description="Escopo do motor unificado: all, sources ou metadata"
    ),
    session: Session = Depends(get_session),
    sources_session: Session = Depends(get_eztv_session),
) -> HydrationPipelineStatus:
    """Start or resume the cooperative background 3-pillar hydration pipeline."""
    return hydration_orchestrator.start(session, sources_session, scope=scope)


@router.post("/hydration/pause", response_model=HydrationPipelineStatus)
async def pause_hydration_pipeline(
    session: Session = Depends(get_session),
    sources_session: Session = Depends(get_eztv_session),
) -> HydrationPipelineStatus:
    """Pause background hydration cleanly while keeping resumable checkpoints intact."""
    return await hydration_orchestrator.pause(session, sources_session)


@router.post("/hydration/step")
async def step_hydration_pipeline(
    scope: Literal["all", "sources", "metadata"] = Query("all"),
    yts_pages: int = Query(6, ge=1, le=20),
    sidecar_pages: int = Query(2, ge=1, le=5),
    sweep_batch: int = Query(12, ge=1, le=25),
    meta_batch: int = Query(60, ge=1, le=100),
    session: Session = Depends(get_session),
    sources_session: Session = Depends(get_eztv_session),
) -> dict[str, Any]:
    """Execute one bounded, checkpointed step across the 3 hydration pillars."""
    return await hydration_orchestrator.run_single_step(
        session,
        sources_session,
        scope=scope,
        yts_pages=yts_pages,
        sidecar_pages=sidecar_pages,
        sweep_batch=sweep_batch,
        meta_batch=meta_batch,
    )


@router.post("/hydration/reset-cursor", response_model=HydrationPipelineStatus)
def reset_hydration_cursor(
    target: str = Query(
        "all",
        description="Alvo do reset: all, yify, tgx, nyaasi, bitsearch, glodls",
    ),
    session: Session = Depends(get_session),
    sources_session: Session = Depends(get_eztv_session),
) -> HydrationPipelineStatus:
    """Reset persisted checkpoints back to BOOTSTRAP page 1 / offset 0."""
    return hydration_orchestrator.reset_cursor(session, sources_session, target=target)

