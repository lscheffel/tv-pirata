"""Federated catalog ingestion and multi-source enrichment service (ADR-008)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlmodel import Session, col, func, select

from src.backend.core.canonical_taxonomy import (
    merge_canonical_genres,
    merge_canonical_providers,
)
from src.backend.models.catalog_domain import IMDbCatalogShow, IMDbEpisodeCatalog, MediaWork
from src.backend.models.db import CatalogShow, ShowRecord
from src.backend.models.eztv_db import EZTVShow
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

        # When the canonical 279k+ IMDb shows table is active in mainstream.db,
        # avoid full legacy bridging overhead on startup and mark engine as ready.
        try:
            imdb_count = int(session.exec(select(func.count(IMDbCatalogShow.imdb_id))).one() or 0)
        except Exception:
            imdb_count = 0
        if imdb_count > 0 and not force:
            _SEEDED_ENGINES.add(engine_id)
            return {
                "seeded_works": 0,
                "bridged_local_works": 0,
                "total_catalog_works": imdb_count,
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

    def get_mainstream_stats(self, session: Session) -> dict[str, int]:
        """Return canonical catalog statistics from data/mainstream.db."""
        try:
            total_titles = int(
                session.exec(select(func.count(IMDbCatalogShow.imdb_id))).one() or 0
            )
        except Exception:
            total_titles = 0

        if total_titles > 0:
            total_episodes = int(
                session.exec(select(func.count(IMDbEpisodeCatalog.episode_imdb_id))).one() or 0
            )
            hydrated_titles = int(
                session.exec(
                    select(func.count(IMDbCatalogShow.imdb_id)).where(
                        col(IMDbCatalogShow.tmdb_synced).in_([1, 2])
                    )
                ).one()
                or 0
            )
            eztv_badged_titles = int(
                session.exec(
                    select(func.count(IMDbCatalogShow.imdb_id)).where(
                        IMDbCatalogShow.has_eztv == 1
                    )
                ).one()
                or 0
            )
            return {
                "total_titles": total_titles,
                "total_episodes": total_episodes,
                "hydrated_titles": hydrated_titles,
                "eztv_badged_titles": eztv_badged_titles,
            }

        mw_count = int(session.exec(select(func.count(MediaWork.id))).one() or 0)
        return {
            "total_titles": mw_count,
            "total_episodes": 0,
            "hydrated_titles": mw_count,
            "eztv_badged_titles": 0,
        }

    async def update_mainstream_catalog(
        self,
        session: Session,
        eztv_session: Optional[Session] = None,
        mode: str = "delta",
        limit: int = 25,
    ) -> dict[str, Any]:
        """Synchronize canonical mainstream.db (EZTV badge cross-ref + TMDB/TVMaze hydration)."""
        badges_synced = 0
        titles_hydrated = 0

        try:
            imdb_count = int(
                session.exec(select(func.count(IMDbCatalogShow.imdb_id))).one() or 0
            )
        except Exception:
            imdb_count = 0

        if imdb_count > 0:
            # 1. Cross-reference EZTV badges and complementary status/providers from sources.db
            if eztv_session is not None and mode in ("delta", "badges", "hydrate"):
                ez_rows = list(
                    eztv_session.exec(
                        select(EZTVShow).where(col(EZTVShow.imdb_id).is_not(None))
                    ).all()
                )
                ez_by_imdb: dict[str, EZTVShow] = {}
                for ez in ez_rows:
                    if ez.imdb_id:
                        norm = EntityResolutionService.normalize_imdb_id(ez.imdb_id)
                        if norm and norm not in ez_by_imdb:
                            ez_by_imdb[norm] = ez

                if ez_by_imdb:
                    matched_shows = list(
                        session.exec(
                            select(IMDbCatalogShow).where(
                                col(IMDbCatalogShow.imdb_id).in_(list(ez_by_imdb.keys()))
                            )
                        ).all()
                    )
                    for m_show in matched_shows:
                        ez_src = ez_by_imdb.get(
                            EntityResolutionService.normalize_imdb_id(m_show.imdb_id)
                        )
                        if not ez_src:
                            continue
                        changed = False
                        if m_show.has_eztv != 1 or m_show.eztv_id != ez_src.id:
                            m_show.has_eztv = 1
                            m_show.eztv_id = ez_src.id
                            m_show.eztv_slug = ez_src.slug
                            m_show.eztv_match_type = "exact_imdb"
                            changed = True
                        if not m_show.status and ez_src.status:
                            m_show.status = ez_src.status
                            changed = True
                        if not m_show.tvmaze_id and ez_src.tvmaze_id:
                            m_show.tvmaze_id = ez_src.tvmaze_id
                            changed = True
                        if not m_show.streaming_providers and (
                            ez_src.streaming_providers or ez_src.network
                        ):
                            m_show.streaming_providers = (
                                ez_src.streaming_providers or ez_src.network
                            )
                            changed = True
                        if not m_show.network and ez_src.network:
                            m_show.network = ez_src.network
                            changed = True
                        merged_sp = merge_canonical_providers(
                            m_show.streaming_providers,
                            m_show.network,
                            ez_src.streaming_providers,
                            ez_src.network,
                        )
                        if merged_sp:
                            sp_csv = ", ".join(merged_sp)
                            if sp_csv != m_show.streaming_providers:
                                m_show.streaming_providers = sp_csv
                                changed = True
                        merged_gen = merge_canonical_genres(m_show.genres_ptbr, m_show.genres)
                        if merged_gen:
                            g_csv = ", ".join(merged_gen)
                            if g_csv != m_show.genres_ptbr:
                                m_show.genres_ptbr = g_csv
                                changed = True
                        if not m_show.poster_url and ez_src.poster_url:
                            m_show.poster_url = ez_src.poster_url
                            changed = True
                        if changed:
                            session.add(m_show)
                            badges_synced += 1
                    session.commit()

            # 2. Hydrate pending or incomplete popular titles via TVMaze/TMDB when requested
            if mode in ("delta", "hydrate") and limit > 0:
                pending_stmt = (
                    select(IMDbCatalogShow)
                    .where(
                        (col(IMDbCatalogShow.tmdb_synced) == 0)
                        | col(IMDbCatalogShow.poster_url).is_(None)
                        | col(IMDbCatalogShow.status).is_(None)
                    )
                    .order_by(
                        col(IMDbCatalogShow.has_eztv).desc(),
                        col(IMDbCatalogShow.rating_votes).desc(),
                    )
                    .limit(min(limit, 50))
                )
                candidates = list(session.exec(pending_stmt).all())
                for cand in candidates:
                    try:
                        info = None
                        if cand.title_type in ("tvSeries", "tvMiniSeries"):
                            info = await self.tvmaze.lookup_by_imdb(cand.imdb_id)
                        if info:
                            cand.poster_url = cand.poster_url or info.poster_url
                            cand.backdrop_url = cand.backdrop_url or info.backdrop_url
                            cand.synopsis = cand.synopsis or info.overview
                            cand.status = cand.status or info.status
                            cand.tvmaze_id = cand.tvmaze_id or info.tvmaze_id
                            merged_g = merge_canonical_genres(
                                cand.genres_ptbr,
                                cand.genres,
                                ", ".join(info.genres or []),
                            )
                            if merged_g:
                                cand.genres_ptbr = ", ".join(merged_g)
                            merged_p = merge_canonical_providers(
                                cand.streaming_providers,
                                cand.network,
                                info.network,
                                ", ".join(info.streaming_providers or []),
                            )
                            if merged_p:
                                cand.streaming_providers = ", ".join(merged_p)
                            if cand.tmdb_synced == 0:
                                cand.tmdb_synced = 2
                            session.add(cand)
                            titles_hydrated += 1
                    except Exception:
                        continue
                session.commit()

            from src.backend.repositories.discovery_engine import DiscoveryEngineRepository

            DiscoveryEngineRepository.refresh_global_facets_cache(
                session, eztv_session=eztv_session, persist_to_sync_state=(imdb_count >= 100)
            )
            stats = self.get_mainstream_stats(session)
            return {
                "status": "updated",
                "mode": mode,
                "badges_synced": badges_synced,
                "titles_hydrated": titles_hydrated,
                "stats": stats,
            }

        seed_stats = self.ensure_federated_catalog_seeded(session, force=True)
        return {
            "status": "updated",
            "mode": mode,
            "badges_synced": 0,
            "titles_hydrated": seed_stats.get("bridged_local_works", 0),
            "stats": self.get_mainstream_stats(session),
        }
