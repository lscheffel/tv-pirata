"""Federated catalog ingestion and multi-source enrichment service (ADR-008)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlmodel import Session, func, select

from src.backend.models.catalog_domain import MediaWork
from src.backend.models.db import CatalogShow, ShowRecord
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider
from src.backend.services.entity_resolution import EntityResolutionService

logger = logging.getLogger(__name__)

SEED_FILE_PATH = Path(__file__).parent / "curated_catalog_seed.json"
_SEEDED_ENGINES: set[int] = set()


def _load_seed_dataset() -> tuple[list[dict[str, Any]], list[list[str]]]:
    """Load the federated seed dataset from JSON."""
    if not SEED_FILE_PATH.exists():
        return [], []
    data = json.loads(SEED_FILE_PATH.read_text(encoding="utf-8"))
    return data.get("works", []), data.get("relations", [])


class FederatedCatalogService:
    """Orchestrates multi-source catalog ingestion, seeding, and local ecosystem bridging."""

    def __init__(
        self,
        tmdb_provider: Optional[TMDBProvider] = None,
        tvmaze_provider: Optional[TVMazeProvider] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.tmdb = tmdb_provider or TMDBProvider()
        self.tvmaze = tvmaze_provider or TVMazeProvider()
        self._client = client

    def ensure_federated_catalog_seeded(
        self, session: Session, force: bool = False
    ) -> dict[str, int]:
        """Seed the Layer 1 Audiovisual Discovery Core and bridge existing Layer 2 records."""
        engine_id = id(session.get_bind())
        if not force and engine_id in _SEEDED_ENGINES:
            return {
                "seeded_works": 0,
                "bridged_local_works": 0,
                "total_catalog_works": -1,
            }

        existing_count = int(session.exec(select(func.count(MediaWork.id))).one() or 0)
        seeded_works = 0

        if existing_count == 0:
            works, relations = _load_seed_dataset()
            for item in works:
                EntityResolutionService.resolve_and_upsert_work(
                    session=session,
                    payload=item,
                    source_provider=item.get("rating_source", "tmdb"),
                )
                seeded_works += 1

            session.flush()

            for src_imdb, tgt_imdb, rel_type, notes in relations:
                src_work = session.exec(
                    select(MediaWork).where(MediaWork.imdb_id == src_imdb)
                ).first()
                tgt_work = session.exec(
                    select(MediaWork).where(MediaWork.imdb_id == tgt_imdb)
                ).first()
                if src_work and tgt_work and src_work.id and tgt_work.id:
                    EntityResolutionService.link_related_works(
                        session=session,
                        source_work_id=src_work.id,
                        target_work_id=tgt_work.id,
                        relation_type=rel_type,
                        notes=notes,
                    )

            session.commit()

        bridged = 0
        if force or existing_count <= 15:
            bridged = self.sync_from_local_ecosystem(session)
        _SEEDED_ENGINES.add(engine_id)
        return {
            "seeded_works": seeded_works,
            "bridged_local_works": bridged,
            "total_catalog_works": int(
                session.exec(select(func.count(MediaWork.id))).one() or 0
            ),
        }

    def sync_from_local_ecosystem(self, session: Session) -> int:
        """Bridge existing CatalogShow (EZTV) and ShowRecord (Personal Library) into MediaWork."""
        bridged_count = 0

        cat_shows = session.exec(select(CatalogShow)).all()
        for cs in cat_shows:
            if not cs.is_enriched and cs.rating == 0.0 and not cs.poster_url:
                continue
            payload = {
                "work_type": "tv_show",
                "title": cs.title,
                "original_title": cs.original_title or cs.title,
                "overview": cs.overview,
                "release_date": cs.first_air_date,
                "status": cs.status or "Returning Series",
                "poster_url": cs.poster_url,
                "backdrop_url": cs.backdrop_url,
                "rating": cs.rating,
                "rating_source": "tvmaze",
                "popularity_score": float(cs.max_seeds or 10),
                "seasons_count": cs.latest_season,
                "imdb_id": cs.imdb_id,
                "genres": [g.strip() for g in (cs.genres or "").split(",") if g.strip()],
            }
            EntityResolutionService.resolve_and_upsert_work(
                session=session,
                payload=payload,
                source_provider="eztv-catalog",
            )
            bridged_count += 1

        lib_shows = session.exec(select(ShowRecord)).all()
        for ls in lib_shows:
            payload = {
                "work_type": "tv_show",
                "title": ls.title,
                "original_title": ls.original_title or ls.title,
                "overview": ls.overview,
                "release_date": ls.first_air_date,
                "status": ls.status or "Returning Series",
                "poster_url": ls.poster_url,
                "backdrop_url": ls.backdrop_url,
                "rating": ls.rating,
                "rating_source": "tmdb",
                "imdb_id": ls.imdb_id,
                "tmdb_id": ls.tmdb_id,
                "tvmaze_id": ls.tvmaze_id,
                "genres": [g.strip() for g in (ls.genres or "").split(",") if g.strip()],
            }
            EntityResolutionService.resolve_and_upsert_work(
                session=session,
                payload=payload,
                source_provider="personal-library",
            )
            bridged_count += 1

        session.commit()
        return bridged_count

    async def federate_live_query(self, session: Session, query: str) -> int:
        """Query complementary external connectors (TVMaze & TMDB) and persist into MediaWork."""
        ingested = 0
        try:
            tvmaze_results = await self.tvmaze.search_shows(query)
            for u in tvmaze_results[:10]:
                payload = {
                    "work_type": "tv_show",
                    "title": u.title,
                    "original_title": u.original_title or u.title,
                    "overview": u.overview,
                    "release_date": u.first_air_date,
                    "status": u.status or "Released",
                    "poster_url": u.poster_url,
                    "backdrop_url": u.backdrop_url,
                    "rating": u.rating,
                    "rating_source": "tvmaze",
                    "imdb_id": u.imdb_id,
                    "tvmaze_id": u.tvmaze_id,
                    "genres": u.genres,
                }
                EntityResolutionService.resolve_and_upsert_work(
                    session=session,
                    payload=payload,
                    source_provider="tvmaze",
                )
                ingested += 1
        except Exception as exc:
            logger.debug("TVMaze federated query skipped for '%s': %s", query, exc)

        if self.tmdb.api_key:
            try:
                tmdb_results = await self.tmdb.search_shows(query)
                for u in tmdb_results[:10]:
                    payload = {
                        "work_type": "tv_show",
                        "title": u.title,
                        "original_title": u.original_title or u.title,
                        "overview": u.overview,
                        "release_date": u.first_air_date,
                        "status": u.status or "Released",
                        "poster_url": u.poster_url,
                        "backdrop_url": u.backdrop_url,
                        "rating": u.rating,
                        "rating_source": "tmdb",
                        "imdb_id": u.imdb_id,
                        "tmdb_id": u.tmdb_id,
                        "genres": u.genres,
                    }
                    EntityResolutionService.resolve_and_upsert_work(
                        session=session,
                        payload=payload,
                        source_provider="tmdb",
                    )
                    ingested += 1
            except Exception as exc:
                logger.debug("TMDB federated query skipped for '%s': %s", query, exc)

        session.commit()
        return ingested
