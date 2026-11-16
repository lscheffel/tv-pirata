"""Advanced Discovery Engine repository for filtering, facets, and similarity (ADR-008)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlmodel import Session, func, select

from src.backend.core.cache import discovery_cache
from src.backend.models.catalog_domain import (
    DataProvenance,
    ExternalIdentifier,
    MediaWork,
    PersonRecord,
    ReleaseCalendarEvent,
    StreamingAvailability,
    WorkCredit,
    WorkRelation,
)
from src.backend.models.db import CatalogShow, ShowRecord
from src.backend.models.eztv_db import EZTVShow
from src.backend.services.entity_resolution import EntityResolutionService


class DiscoveryEngineRepository:
    """Executes multi-dimensional queries, dynamic faceting, and similarity scoring."""

    @staticmethod
    def _parse_csv(raw: Optional[str]) -> list[str]:
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _slugify(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

    @classmethod
    def build_eztv_lookup_index(
        cls, eztv_session: Optional[Session]
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Load lightweight (imdb_id, slug/name) -> eztv_show_id index with scoped cache."""
        if eztv_session is None:
            return {}, {}

        scope = discovery_cache.session_scope(eztv_session)
        fp_row = eztv_session.exec(
            select(func.count(EZTVShow.id), func.max(EZTVShow.updated_at))
        ).one()
        fp = (int(fp_row[0] or 0), str(fp_row[1] or ""))

        def _compute() -> tuple[dict[str, int], dict[str, int]]:
            by_imdb: dict[str, int] = {}
            by_slug: dict[str, int] = {}
            rows = eztv_session.exec(
                select(EZTVShow.id, EZTVShow.imdb_id, EZTVShow.slug, EZTVShow.name)
            ).all()
            for show_id, raw_imdb, raw_slug, raw_name in rows:
                if show_id is None:
                    continue
                sid = int(show_id)
                if raw_imdb:
                    norm_imdb = EntityResolutionService.normalize_imdb_id(raw_imdb)
                    if norm_imdb and norm_imdb not in by_imdb:
                        by_imdb[norm_imdb] = sid
                if raw_slug:
                    norm_slug = cls._slugify(raw_slug)
                    if norm_slug and norm_slug not in by_slug:
                        by_slug[norm_slug] = sid
                if raw_name:
                    name_slug = cls._slugify(raw_name)
                    if name_slug and name_slug not in by_slug:
                        by_slug[name_slug] = sid
            return by_imdb, by_slug

        return discovery_cache.get_or_set(scope, "eztv_lookup", fp, _compute)

    @classmethod
    def _load_base_snapshot(
        cls, session: Session
    ) -> tuple[
        list[MediaWork],
        dict[int, list[dict[str, Any]]],
        dict[int, list[StreamingAvailability]],
        dict[str, int],
        dict[int, list[str]],
        dict[int, list[str]],
        dict[int, str],
    ]:
        """Load and cache detached discovery catalog snapshot keyed by table counts."""
        scope = discovery_cache.session_scope(session)
        w_cnt = int(session.exec(select(func.count(MediaWork.id))).one() or 0)
        p_cnt = int(session.exec(select(func.count(CatalogShow.imdb_id))).one() or 0)
        fp = (w_cnt, p_cnt)

        def _compute() -> tuple[
            list[MediaWork],
            dict[int, list[dict[str, Any]]],
            dict[int, list[StreamingAvailability]],
            dict[str, int],
            dict[int, list[str]],
            dict[int, list[str]],
            dict[int, str],
        ]:
            all_works = [
                MediaWork.model_validate(w.model_dump())
                for w in session.exec(select(MediaWork)).all()
            ]
            all_credits = list(session.exec(select(WorkCredit)).all())
            all_people = {
                p.id: p
                for p in session.exec(select(PersonRecord)).all()
                if p.id is not None
            }
            credits_by_work: dict[int, list[dict[str, Any]]] = {}
            for cr in all_credits:
                person = all_people.get(cr.person_id)
                if person:
                    credits_by_work.setdefault(cr.work_id, []).append(
                        {
                            "person_id": person.id,
                            "name": person.name,
                            "role_type": cr.role_type,
                            "character_name": cr.character_name,
                            "billing_order": cr.billing_order,
                        }
                    )

            avail_by_work: dict[int, list[StreamingAvailability]] = {}
            for av in session.exec(select(StreamingAvailability)).all():
                avail_by_work.setdefault(av.work_id, []).append(
                    StreamingAvailability.model_validate(av.model_dump())
                )

            p2p_seeds_by_imdb: dict[str, int] = {}
            for cs in session.exec(select(CatalogShow)).all():
                norm_imdb = EntityResolutionService.normalize_imdb_id(cs.imdb_id)
                if norm_imdb and cs.max_seeds > 0:
                    p2p_seeds_by_imdb[norm_imdb] = cs.max_seeds

            genres_raw_by_work: dict[int, list[str]] = {}
            genres_norm_by_work: dict[int, list[str]] = {}
            searchable_by_work: dict[int, str] = {}
            for w in all_works:
                if w.id is None:
                    continue
                raw_g = [g.strip() for g in (w.genres_csv or "").split(",") if g.strip()]
                genres_raw_by_work[w.id] = raw_g
                genres_norm_by_work[w.id] = [
                    EntityResolutionService.normalize_title_key(g) for g in raw_g
                ]
                w_creds = credits_by_work.get(w.id, [])
                blob = " ".join(
                    [
                        w.title or "",
                        w.original_title or "",
                        w.overview or "",
                        w.collection_name or "",
                        w.network_or_studio or "",
                        " ".join(c["name"] for c in w_creds),
                    ]
                )
                searchable_by_work[w.id] = EntityResolutionService.normalize_title_key(blob)

            return (
                all_works,
                credits_by_work,
                avail_by_work,
                p2p_seeds_by_imdb,
                genres_raw_by_work,
                genres_norm_by_work,
                searchable_by_work,
            )

        return discovery_cache.get_or_set(scope, "base_snapshot", fp, _compute)

    @classmethod
    def _resolve_eztv_match(
        cls,
        w: MediaWork,
        by_imdb: dict[str, int],
        by_slug: dict[str, int],
    ) -> tuple[bool, Optional[int]]:
        """Match MediaWork against eztv_metadata.db via IMDb ID or normalized title/slug."""
        norm_imdb = EntityResolutionService.normalize_imdb_id(w.imdb_id)
        if norm_imdb and norm_imdb in by_imdb:
            return True, by_imdb[norm_imdb]
        for candidate in (w.title, w.original_title):
            slug = cls._slugify(candidate)
            if slug and slug in by_slug:
                return True, by_slug[slug]
        return False, None

    @classmethod
    def query_works(
        cls,
        session: Session,
        eztv_session: Optional[Session] = None,
        q: Optional[str] = None,
        work_types: Optional[str] = None,
        genres_any: Optional[str] = None,
        genres_all: Optional[str] = None,
        genres_not: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        min_rating: Optional[float] = None,
        max_rating: Optional[float] = None,
        min_runtime: Optional[int] = None,
        max_runtime: Optional[int] = None,
        status: Optional[str] = None,
        streaming_providers: Optional[str] = None,
        territory: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        person_query: Optional[str] = None,
        role_type: Optional[str] = None,
        min_seasons: Optional[int] = None,
        exclude_watched: bool = False,
        only_with_p2p: bool = False,
        sort_by: str = "rating",
        page: int = 1,
        page_size: int = 24,
    ) -> dict[str, Any]:
        """Execute composite boolean/relational filtering and compute dynamic facets."""
        (
            all_works,
            credits_by_work,
            avail_by_work,
            p2p_seeds_by_imdb,
            genres_raw_by_work,
            genres_norm_by_work,
            searchable_by_work,
        ) = cls._load_base_snapshot(session)

        # Layer 2 Cross-Reference: Personal Library evaluated dynamically for real-time updates
        watched_imdb_ids: set[str] = set()
        watched_tmdb_ids: set[int] = set()
        saved_library_map: dict[str, str] = {}
        for sr in session.exec(select(ShowRecord)).all():
            if sr.imdb_id:
                norm_imdb = EntityResolutionService.normalize_imdb_id(sr.imdb_id)
                if norm_imdb:
                    saved_library_map[norm_imdb] = sr.user_status
                    if sr.user_status in ("completed", "watching"):
                        watched_imdb_ids.add(norm_imdb)
            if sr.tmdb_id and sr.user_status in ("completed", "watching"):
                watched_tmdb_ids.add(sr.tmdb_id)

        # Parse filter tokens
        type_list = [t.lower() for t in cls._parse_csv(work_types)]
        g_any = [EntityResolutionService.normalize_title_key(g) for g in cls._parse_csv(genres_any)]
        g_all = [EntityResolutionService.normalize_title_key(g) for g in cls._parse_csv(genres_all)]
        g_not = [EntityResolutionService.normalize_title_key(g) for g in cls._parse_csv(genres_not)]
        status_list = [s.lower() for s in cls._parse_csv(status)]
        provider_list = [p.lower() for p in cls._parse_csv(streaming_providers)]
        country_list = [c.upper() for c in cls._parse_csv(country)]
        lang_list = [lang.lower() for lang in cls._parse_csv(language)]
        q_norm = EntityResolutionService.normalize_title_key(q) if q else ""
        person_norm = (
            EntityResolutionService.normalize_title_key(person_query) if person_query else ""
        )

        filtered: list[MediaWork] = []

        for w in all_works:
            if w.id is None:
                continue

            # 1. Work Type Filter
            if type_list and w.work_type.lower() not in type_list:
                continue

            # 2. Year Range Filter
            if year_from is not None and (w.release_year is None or w.release_year < year_from):
                continue
            if year_to is not None and (w.release_year is None or w.release_year > year_to):
                continue

            # 3. Rating Filter
            if min_rating is not None and w.canonical_rating < min_rating:
                continue
            if max_rating is not None and w.canonical_rating > max_rating:
                continue

            # 4. Runtime Filter
            if min_runtime is not None and (
                w.runtime_minutes is None or w.runtime_minutes < min_runtime
            ):
                continue
            if max_runtime is not None and (
                w.runtime_minutes is None or w.runtime_minutes > max_runtime
            ):
                continue

            # 5. Status Filter
            if status_list and (w.status or "").lower() not in status_list:
                continue

            # 6. Country & Language Filter
            if country_list and (w.origin_country or "").upper() not in country_list:
                continue
            if lang_list and (w.original_language or "").lower() not in lang_list:
                continue

            # 7. Min Seasons Filter
            if min_seasons is not None and w.seasons_count < min_seasons:
                continue

            # 8. Boolean Genre Filters (OR / AND / NOT)
            work_genres_norm = genres_norm_by_work.get(w.id, [])

            if g_any:
                if not any(
                    any(target in wg or wg in target for wg in work_genres_norm) for target in g_any
                ):
                    continue

            if g_all:
                if not all(
                    any(target in wg or wg in target for wg in work_genres_norm) for target in g_all
                ):
                    continue

            if g_not:
                if any(
                    any(target in wg or wg in target for wg in work_genres_norm) for target in g_not
                ):
                    continue

            # 9. Streaming Provider & Territory Filter
            work_avails = avail_by_work.get(w.id, [])
            if territory:
                work_avails = [
                    a for a in work_avails if a.territory.upper() in (territory.upper(), "GLOBAL")
                ]
            if provider_list:
                avail_names_lower = [a.provider_name.lower() for a in work_avails]
                if not any(any(req_p in an for an in avail_names_lower) for req_p in provider_list):
                    continue

            # 10. Person / Cast / Director Filter
            work_credits = credits_by_work.get(w.id, [])
            if person_norm:
                matching_credits = [
                    c
                    for c in work_credits
                    if person_norm in EntityResolutionService.normalize_title_key(c["name"])
                    and (not role_type or c["role_type"].lower() == role_type.lower())
                ]
                if not matching_credits:
                    continue

            # 11. Exclude Watched (Layer 2 Cross-Reference)
            if exclude_watched:
                if (w.imdb_id and w.imdb_id in watched_imdb_ids) or (
                    w.tmdb_id and w.tmdb_id in watched_tmdb_ids
                ):
                    continue

            # 12. Only with P2P Seeds (Layer 2 Cross-Reference)
            if only_with_p2p:
                if not w.imdb_id or p2p_seeds_by_imdb.get(w.imdb_id, 0) <= 0:
                    continue

            # 13. Full-Text Search Query
            if q_norm:
                if q_norm not in searchable_by_work.get(w.id, ""):
                    continue

            filtered.append(w)

        # ------------------------------------------------------------------
        # Compute Dynamic Facets over Filtered Set
        # ------------------------------------------------------------------
        facet_types: dict[str, int] = {}
        facet_genres: dict[str, int] = {}
        facet_providers: dict[str, int] = {}
        facet_decades: dict[str, int] = {}
        facet_statuses: dict[str, int] = {}
        facet_countries: dict[str, int] = {}

        for w in filtered:
            assert w.id is not None
            facet_types[w.work_type] = facet_types.get(w.work_type, 0) + 1
            for g in genres_raw_by_work.get(w.id, []):
                facet_genres[g] = facet_genres.get(g, 0) + 1

            seen_prov: set[str] = set()
            for av in avail_by_work.get(w.id, []):
                if av.provider_name not in seen_prov:
                    seen_prov.add(av.provider_name)
                    facet_providers[av.provider_name] = facet_providers.get(av.provider_name, 0) + 1

            if w.release_year:
                decade = f"{(w.release_year // 10) * 10}s"
                facet_decades[decade] = facet_decades.get(decade, 0) + 1

            if w.status:
                facet_statuses[w.status] = facet_statuses.get(w.status, 0) + 1
            if w.origin_country:
                facet_countries[w.origin_country] = facet_countries.get(w.origin_country, 0) + 1

        # ------------------------------------------------------------------
        # Sorting
        # ------------------------------------------------------------------
        if sort_by == "rating":
            filtered.sort(key=lambda x: (x.canonical_rating, x.popularity_score), reverse=True)
        elif sort_by == "popularity":
            filtered.sort(key=lambda x: (x.popularity_score, x.canonical_rating), reverse=True)
        elif sort_by == "year_desc":
            filtered.sort(key=lambda x: (x.release_year or 0, x.canonical_rating), reverse=True)
        elif sort_by == "year_asc":
            filtered.sort(key=lambda x: (x.release_year or 9999, -x.canonical_rating))
        elif sort_by == "runtime":
            filtered.sort(key=lambda x: x.runtime_minutes or 0, reverse=True)
        elif sort_by == "title":
            filtered.sort(key=lambda x: (x.title or "").lower())
        else:
            filtered.sort(key=lambda x: (x.canonical_rating, x.popularity_score), reverse=True)

        total = len(filtered)
        offset = (page - 1) * page_size
        paginated = filtered[offset : offset + page_size]
        eztv_by_imdb, eztv_by_slug = cls.build_eztv_lookup_index(eztv_session)

        serialized_items = [
            cls._serialize_work_summary(
                w,
                credits_by_work.get(w.id or 0, []),
                avail_by_work.get(w.id or 0, []),
                saved_library_map,
                p2p_seeds_by_imdb,
                eztv_by_imdb,
                eztv_by_slug,
            )
            for w in paginated
        ]

        return {
            "items": serialized_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "facets": {
                "work_types": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_types.items(), key=lambda i: i[1], reverse=True)
                ],
                "genres": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_genres.items(), key=lambda i: i[1], reverse=True)
                ],
                "streaming_providers": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_providers.items(), key=lambda i: i[1], reverse=True)
                ],
                "decades": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_decades.items(), key=lambda i: i[0], reverse=True)
                ],
                "statuses": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_statuses.items(), key=lambda i: i[1], reverse=True)
                ],
                "countries": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_countries.items(), key=lambda i: i[1], reverse=True)
                ],
            },
        }

    @classmethod
    def _serialize_work_summary(
        cls,
        w: MediaWork,
        credits: list[dict[str, Any]],
        availabilities: list[StreamingAvailability],
        saved_library_map: dict[str, str],
        p2p_seeds_by_imdb: dict[str, int],
        eztv_by_imdb: Optional[dict[str, int]] = None,
        eztv_by_slug: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        try:
            ratings_map = json.loads(w.ratings_breakdown or "{}")
        except Exception:
            ratings_map = {}

        directors = [c["name"] for c in credits if c["role_type"] in ("director", "creator")]
        top_cast = [c["name"] for c in credits if c["role_type"] == "actor"][:4]
        providers = list(dict.fromkeys(a.provider_name for a in availabilities))

        norm_imdb = EntityResolutionService.normalize_imdb_id(w.imdb_id)
        user_lib_status = saved_library_map.get(norm_imdb) if norm_imdb else None
        p2p_seeds = p2p_seeds_by_imdb.get(norm_imdb, 0) if norm_imdb else 0
        eztv_available, eztv_show_id = cls._resolve_eztv_match(
            w, eztv_by_imdb or {}, eztv_by_slug or {}
        )

        return {
            "id": w.id,
            "work_type": w.work_type,
            "title": w.title,
            "original_title": w.original_title,
            "overview": w.overview,
            "tagline": w.tagline,
            "release_date": w.release_date,
            "release_year": w.release_year,
            "runtime_minutes": w.runtime_minutes,
            "status": w.status,
            "origin_country": w.origin_country,
            "original_language": w.original_language,
            "poster_url": w.poster_url,
            "backdrop_url": w.backdrop_url,
            "canonical_rating": w.canonical_rating,
            "rating_source": w.rating_source,
            "ratings_breakdown": ratings_map,
            "popularity_score": w.popularity_score,
            "vote_count": w.vote_count,
            "seasons_count": w.seasons_count,
            "episodes_count": w.episodes_count,
            "network_or_studio": w.network_or_studio,
            "collection_name": w.collection_name,
            "genres": [g.strip() for g in (w.genres_csv or "").split(",") if g.strip()],
            "directors": directors,
            "top_cast": top_cast,
            "streaming_providers": providers,
            "imdb_id": w.imdb_id,
            "tmdb_id": w.tmdb_id,
            "tvmaze_id": w.tvmaze_id,
            "wikidata_id": w.wikidata_id,
            "user_library_status": user_lib_status,
            "p2p_max_seeds": p2p_seeds,
            "eztv_available": eztv_available,
            "eztv_show_id": eztv_show_id,
        }

    @classmethod
    def get_work_dossier(
        cls,
        session: Session,
        work_id: int,
        eztv_session: Optional[Session] = None,
    ) -> Optional[dict[str, Any]]:
        """Build comprehensive canonical dossier for a MediaWork."""
        work = session.get(MediaWork, work_id)
        if not work or work.id is None:
            return None

        ext_ids = session.exec(
            select(ExternalIdentifier).where(ExternalIdentifier.work_id == work.id)
        ).all()
        provenance = session.exec(
            select(DataProvenance).where(DataProvenance.work_id == work.id)
        ).all()
        credits_raw = session.exec(select(WorkCredit).where(WorkCredit.work_id == work.id)).all()
        availabilities = session.exec(
            select(StreamingAvailability).where(StreamingAvailability.work_id == work.id)
        ).all()
        calendar_events = session.exec(
            select(ReleaseCalendarEvent).where(ReleaseCalendarEvent.work_id == work.id)
        ).all()

        credits_list = []
        for cr in sorted(credits_raw, key=lambda c: (c.billing_order, c.id or 0)):
            person = session.get(PersonRecord, cr.person_id)
            if person:
                credits_list.append(
                    {
                        "person_id": person.id,
                        "name": person.name,
                        "role_type": cr.role_type,
                        "character_name": cr.character_name,
                        "department": person.known_for_department,
                        "country": person.country,
                    }
                )

        # Explicit Work Relations
        rels_raw = session.exec(
            select(WorkRelation).where(WorkRelation.source_work_id == work.id)
        ).all()
        explicit_relations = []
        for rel in rels_raw:
            target = session.get(MediaWork, rel.target_work_id)
            if target:
                explicit_relations.append(
                    {
                        "work_id": target.id,
                        "title": target.title,
                        "work_type": target.work_type,
                        "release_year": target.release_year,
                        "poster_url": target.poster_url,
                        "canonical_rating": target.canonical_rating,
                        "relation_type": rel.relation_type,
                        "notes": rel.notes,
                    }
                )

        # Objective Multi-Criteria Similarity Engine
        similar_works = cls.compute_similar_works(session, work, limit=6)

        # Layer 2 Cross-reference
        saved_library_map: dict[str, str] = {}
        for sr in session.exec(select(ShowRecord)).all():
            if sr.imdb_id:
                norm_imdb = EntityResolutionService.normalize_imdb_id(sr.imdb_id)
                if norm_imdb:
                    saved_library_map[norm_imdb] = sr.user_status

        p2p_seeds_by_imdb: dict[str, int] = {}
        for cs in session.exec(select(CatalogShow)).all():
            norm_imdb = EntityResolutionService.normalize_imdb_id(cs.imdb_id)
            if norm_imdb and cs.max_seeds > 0:
                p2p_seeds_by_imdb[norm_imdb] = cs.max_seeds

        eztv_by_imdb, eztv_by_slug = cls.build_eztv_lookup_index(eztv_session)

        summary = cls._serialize_work_summary(
            work,
            credits_list,
            list(availabilities),
            saved_library_map,
            p2p_seeds_by_imdb,
            eztv_by_imdb,
            eztv_by_slug,
        )

        summary.update(
            {
                "external_identifiers": [
                    {
                        "provider": e.provider,
                        "external_id": e.external_id,
                        "confidence": e.confidence,
                    }
                    for e in ext_ids
                ],
                "provenance": [
                    {
                        "source_provider": p.source_provider,
                        "external_id": p.external_id,
                        "field_name": p.field_name,
                        "field_value": p.field_value,
                        "selection_reason": p.selection_reason,
                        "fetched_at": p.fetched_at.isoformat(),
                    }
                    for p in provenance
                ],
                "credits": credits_list,
                "availabilities": [
                    {
                        "provider_name": a.provider_name,
                        "territory": a.territory,
                        "monetization_type": a.monetization_type,
                        "source_provider": a.source_provider,
                    }
                    for a in availabilities
                ],
                "explicit_relations": explicit_relations,
                "similar_works": similar_works,
                "calendar_events": [
                    {
                        "id": ev.id,
                        "event_type": ev.event_type,
                        "event_date": ev.event_date,
                        "confidence_level": ev.confidence_level,
                        "territory": ev.territory,
                        "platform_or_network": ev.platform_or_network,
                        "season_number": ev.season_number,
                        "episode_number": ev.episode_number,
                        "event_title": ev.event_title,
                    }
                    for ev in calendar_events
                ],
            }
        )
        return summary

    @classmethod
    def compute_similar_works(
        cls, session: Session, target: MediaWork, limit: int = 6
    ) -> list[dict[str, Any]]:
        """Calculate objective multi-criteria similarity between target MediaWork and catalog."""
        if target.id is None:
            return []

        all_works = session.exec(select(MediaWork).where(MediaWork.id != target.id)).all()

        target_genres = {
            g.strip().lower() for g in (target.genres_csv or "").split(",") if g.strip()
        }
        target_credits = session.exec(
            select(WorkCredit).where(WorkCredit.work_id == target.id)
        ).all()
        target_directors = {
            c.person_id for c in target_credits if c.role_type in ("director", "creator")
        }
        target_actors = {c.person_id for c in target_credits if c.role_type == "actor"}
        target_words = {w for w in re.findall(r"[a-zA-ZÀ-ÿ]{5,}", (target.overview or "").lower())}

        all_people = {
            p.id: p.name for p in session.exec(select(PersonRecord)).all() if p.id is not None
        }
        all_credits_by_work: dict[int, list[WorkCredit]] = {}
        for cr in session.exec(select(WorkCredit)).all():
            all_credits_by_work.setdefault(cr.work_id, []).append(cr)

        scored: list[tuple[float, list[str], MediaWork]] = []

        for cand in all_works:
            if cand.id is None:
                continue
            score = 0.0
            reasons: list[str] = []

            # 1. Collection / Franchise affinity
            if (
                target.collection_name
                and cand.collection_name
                and target.collection_name == cand.collection_name
            ):
                score += 35.0
                reasons.append(f"Mesma franquia: {target.collection_name}")

            # 2. Shared Genres
            cand_genres = {
                g.strip().lower() for g in (cand.genres_csv or "").split(",") if g.strip()
            }
            shared_g = target_genres.intersection(cand_genres)
            if shared_g:
                score += min(30.0, len(shared_g) * 12.0)
                reasons.append(f"Gêneros em comum ({len(shared_g)})")

            # 3. Shared Directors / Creators & Cast
            cand_credits = all_credits_by_work.get(cand.id, [])
            cand_directors = {
                c.person_id for c in cand_credits if c.role_type in ("director", "creator")
            }
            cand_actors = {c.person_id for c in cand_credits if c.role_type == "actor"}

            shared_dirs = target_directors.intersection(cand_directors)
            if shared_dirs:
                score += 30.0
                dir_names = [all_people.get(pid, "") for pid in shared_dirs if pid in all_people]
                reasons.append(f"Mesma direção/criação: {', '.join(dir_names)}")

            shared_acts = target_actors.intersection(cand_actors)
            if shared_acts:
                score += min(24.0, len(shared_acts) * 12.0)
                act_names = [all_people.get(pid, "") for pid in shared_acts if pid in all_people]
                reasons.append(f"Elenco em comum: {', '.join(act_names[:2])}")

            # 4. Same Format & Era Proximity
            if cand.work_type == target.work_type:
                score += 6.0
            if target.release_year and cand.release_year:
                if abs(target.release_year - cand.release_year) <= 5:
                    score += 6.0

            # 5. Thematic / Synopsis Vocabulary Overlap
            cand_words = {w for w in re.findall(r"[a-zA-ZÀ-ÿ]{5,}", (cand.overview or "").lower())}
            shared_words = target_words.intersection(cand_words)
            if len(shared_words) >= 2:
                score += min(12.0, len(shared_words) * 3.0)

            if score >= 15.0:
                normalized_score = min(99.0, round(score, 1))
                scored.append((normalized_score, reasons, cand))

        scored.sort(key=lambda item: (item[0], item[2].canonical_rating), reverse=True)

        return [
            {
                "id": w.id,
                "title": w.title,
                "original_title": w.original_title,
                "work_type": w.work_type,
                "release_year": w.release_year,
                "poster_url": w.poster_url,
                "canonical_rating": w.canonical_rating,
                "genres": [g.strip() for g in (w.genres_csv or "").split(",") if g.strip()],
                "similarity_score": sc,
                "similarity_reasons": r[:3],
            }
            for sc, r, w in scored[:limit]
        ]

    @classmethod
    def list_people(
        cls,
        session: Session,
        q: Optional[str] = None,
        department: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List people (directors, creators, actors) with work counts."""
        people = list(session.exec(select(PersonRecord)).all())
        credits = list(session.exec(select(WorkCredit)).all())
        works_map = {w.id: w for w in session.exec(select(MediaWork)).all() if w.id is not None}

        credits_by_person: dict[int, list[WorkCredit]] = {}
        for c in credits:
            credits_by_person.setdefault(c.person_id, []).append(c)

        q_norm = EntityResolutionService.normalize_title_key(q) if q else ""

        results: list[dict[str, Any]] = []
        for p in people:
            if p.id is None:
                continue
            if q_norm and q_norm not in EntityResolutionService.normalize_title_key(p.name):
                continue
            if department and p.known_for_department.lower() != department.lower():
                continue

            p_credits = credits_by_person.get(p.id, [])
            unique_work_ids = list(dict.fromkeys(c.work_id for c in p_credits))
            p_works = [works_map[wid] for wid in unique_work_ids if wid in works_map]
            avg_rating = (
                round(
                    sum(w.canonical_rating for w in p_works if w.canonical_rating > 0)
                    / max(1, len([w for w in p_works if w.canonical_rating > 0])),
                    1,
                )
                if p_works
                else 0.0
            )
            roles = list(dict.fromkeys(c.role_type for c in p_credits))

            results.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "known_for_department": p.known_for_department,
                    "country": p.country,
                    "roles": roles,
                    "works_count": len(p_works),
                    "average_rating": avg_rating,
                    "notable_works": [w.title for w in p_works[:4]],
                }
            )

        results.sort(key=lambda x: (x["works_count"], x["average_rating"]), reverse=True)
        return results

    @classmethod
    def get_person_dossier(cls, session: Session, person_id: int) -> Optional[dict[str, Any]]:
        """Retrieve complete filmography and frequent collaborators for a PersonRecord."""
        person = session.get(PersonRecord, person_id)
        if not person or person.id is None:
            return None

        p_credits = list(
            session.exec(select(WorkCredit).where(WorkCredit.person_id == person.id)).all()
        )
        work_ids = list(dict.fromkeys(c.work_id for c in p_credits))

        filmography = []
        collaborator_counts: dict[int, dict[str, Any]] = {}

        for wid in work_ids:
            work = session.get(MediaWork, wid)
            if not work or work.id is None:
                continue
            roles_in_work = [c.role_type for c in p_credits if c.work_id == wid]
            chars_in_work = [
                c.character_name for c in p_credits if c.work_id == wid and c.character_name
            ]
            filmography.append(
                {
                    "work_id": work.id,
                    "title": work.title,
                    "original_title": work.original_title,
                    "work_type": work.work_type,
                    "release_year": work.release_year,
                    "canonical_rating": work.canonical_rating,
                    "poster_url": work.poster_url,
                    "status": work.status,
                    "roles": roles_in_work,
                    "character_name": ", ".join(chars_in_work) if chars_in_work else None,
                    "genres": [g.strip() for g in (work.genres_csv or "").split(",") if g.strip()],
                }
            )

            # Find co-workers in this work
            co_credits = session.exec(
                select(WorkCredit).where(
                    WorkCredit.work_id == wid, WorkCredit.person_id != person.id
                )
            ).all()
            for cc in co_credits:
                co_person = session.get(PersonRecord, cc.person_id)
                if not co_person or co_person.id is None:
                    continue
                entry = collaborator_counts.setdefault(
                    co_person.id,
                    {
                        "person_id": co_person.id,
                        "name": co_person.name,
                        "department": co_person.known_for_department,
                        "shared_works_count": 0,
                        "shared_titles": [],
                    },
                )
                if work.title not in entry["shared_titles"]:
                    entry["shared_titles"].append(work.title)
                    entry["shared_works_count"] += 1

        filmography.sort(
            key=lambda x: (x["release_year"] or 0, x["canonical_rating"]), reverse=True
        )
        collaborators = sorted(
            collaborator_counts.values(),
            key=lambda x: x["shared_works_count"],
            reverse=True,
        )

        return {
            "id": person.id,
            "name": person.name,
            "known_for_department": person.known_for_department,
            "country": person.country,
            "filmography": filmography,
            "frequent_collaborators": collaborators[:10],
        }

    @classmethod
    def find_shared_collaborations(
        cls, session: Session, person_a_query: str, person_b_query: str
    ) -> dict[str, Any]:
        """Find all audiovisual works where two people collaborated."""
        norm_a = EntityResolutionService.normalize_title_key(person_a_query)
        norm_b = EntityResolutionService.normalize_title_key(person_b_query)

        all_people = list(session.exec(select(PersonRecord)).all())
        person_a = next(
            (
                p
                for p in all_people
                if norm_a in EntityResolutionService.normalize_title_key(p.name)
            ),
            None,
        )
        person_b = next(
            (
                p
                for p in all_people
                if norm_b in EntityResolutionService.normalize_title_key(p.name)
            ),
            None,
        )

        if not person_a or not person_b or person_a.id is None or person_b.id is None:
            return {
                "person_a": person_a.name if person_a else person_a_query,
                "person_b": person_b.name if person_b else person_b_query,
                "shared_works": [],
            }

        credits_a = {
            c.work_id: c
            for c in session.exec(
                select(WorkCredit).where(WorkCredit.person_id == person_a.id)
            ).all()
        }
        credits_b = {
            c.work_id: c
            for c in session.exec(
                select(WorkCredit).where(WorkCredit.person_id == person_b.id)
            ).all()
        }

        common_work_ids = set(credits_a.keys()).intersection(set(credits_b.keys()))
        shared_works = []
        for wid in common_work_ids:
            w = session.get(MediaWork, wid)
            if w:
                shared_works.append(
                    {
                        "id": w.id,
                        "title": w.title,
                        "work_type": w.work_type,
                        "release_year": w.release_year,
                        "canonical_rating": w.canonical_rating,
                        "poster_url": w.poster_url,
                        "person_a_role": credits_a[wid].role_type,
                        "person_b_role": credits_b[wid].role_type,
                    }
                )

        shared_works.sort(key=lambda x: x["release_year"] or 0, reverse=True)
        return {
            "person_a": person_a.name,
            "person_b": person_b.name,
            "shared_works": shared_works,
        }

    @classmethod
    def get_calendar_events(
        cls,
        session: Session,
        work_type: Optional[str] = None,
        event_type: Optional[str] = None,
        confidence_level: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve unified audiovisual release and premiere calendar events."""
        events = list(session.exec(select(ReleaseCalendarEvent)).all())
        results: list[dict[str, Any]] = []

        for ev in events:
            work = session.get(MediaWork, ev.work_id)
            if not work:
                continue

            if work_type and work.work_type.lower() != work_type.lower():
                continue
            if event_type and ev.event_type.lower() != event_type.lower():
                continue
            if confidence_level and ev.confidence_level.lower() != confidence_level.lower():
                continue
            if platform and (
                not ev.platform_or_network or platform.lower() not in ev.platform_or_network.lower()
            ):
                continue

            results.append(
                {
                    "id": ev.id,
                    "work_id": work.id,
                    "work_title": work.title,
                    "work_type": work.work_type,
                    "poster_url": work.poster_url,
                    "genres": [g.strip() for g in (work.genres_csv or "").split(",") if g.strip()],
                    "event_type": ev.event_type,
                    "event_date": ev.event_date,
                    "confidence_level": ev.confidence_level,
                    "territory": ev.territory,
                    "platform_or_network": ev.platform_or_network,
                    "season_number": ev.season_number,
                    "episode_number": ev.episode_number,
                    "event_title": ev.event_title,
                    "source_provider": ev.source_provider,
                }
            )

        results.sort(key=lambda x: x["event_date"])
        return results

    @classmethod
    def get_rankings_perspectives(cls, session: Session) -> dict[str, Any]:
        """Generate multi-perspective discovery rankings with source provenance."""
        top_movies = cls.query_works(
            session, work_types="movie", min_rating=7.0, sort_by="rating", page_size=10
        )["items"]
        top_series = cls.query_works(
            session,
            work_types="tv_show,mini_series",
            min_rating=8.0,
            sort_by="rating",
            page_size=10,
        )["items"]
        currently_airing = cls.query_works(
            session, status="Returning Series", sort_by="popularity", page_size=10
        )["items"]
        upcoming = cls.query_works(
            session, status="In Production,Upcoming", sort_by="popularity", page_size=10
        )["items"]

        return {
            "top_movies": top_movies,
            "top_series": top_series,
            "currently_airing": currently_airing,
            "upcoming_productions": upcoming,
        }
