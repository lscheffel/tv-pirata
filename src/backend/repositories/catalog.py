"""Catalog repository querying dedicated eztv_metadata.db with optional P2P telemetry (ADR-010)."""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy import text
from sqlmodel import Session, col, func, or_, select

from src.backend.core.cache import catalog_cache
from src.backend.models.db import CatalogRelease, CatalogShow
from src.backend.models.eztv_db import EZTVEpisodeCatalog, EZTVShow

_GENRE_SYNONYMS: dict[str, list[str]] = {
    "sci-fi": ["science-fiction", "sci-fi", "fantasy", "space"],
    "scifi": ["science-fiction", "sci-fi", "fantasy", "space"],
    "ficcao": ["science-fiction", "sci-fi", "fantasy", "space"],
    "ficção": ["science-fiction", "sci-fi", "fantasy", "space"],
    "science-fiction": ["science-fiction", "sci-fi", "fantasy", "space"],
    "acao": ["action", "adventure"],
    "ação": ["action", "adventure"],
    "action": ["action", "adventure"],
    "crime": ["crime", "mystery", "legal"],
    "policial": ["crime", "mystery", "legal"],
    "comedia": ["comedy"],
    "comédia": ["comedy"],
    "comedy": ["comedy"],
    "animacao": ["animation", "anime"],
    "animação": ["animation", "anime"],
    "animation": ["animation", "anime"],
    "documentario": ["documentary", "history", "nature"],
    "documentário": ["documentary", "history", "nature"],
    "documentary": ["documentary", "history", "nature"],
    "suspense": ["thriller", "mystery"],
    "thriller": ["thriller", "mystery"],
}


class CatalogRepository:
    """Repository managing EZTV catalog queries over eztv_metadata.db and P2P telemetry."""

    @staticmethod
    def normalize_imdb_id(imdb_id: str) -> str:
        """Normalize IMDB ID into canonical 'tt1234567' format."""
        clean = imdb_id.strip().lower()
        digits = clean[2:] if clean.startswith("tt") else clean
        if digits.isdigit():
            return f"tt{digits.zfill(7)}"
        return clean

    @staticmethod
    def _fingerprint(
        eztv_session: Session, p2p_session: Optional[Session] = None
    ) -> tuple[Any, ...]:
        """Compute an ultra-fast (<0.2ms) version fingerprint for cache coherence."""
        row = eztv_session.exec(
            select(
                func.count(EZTVShow.id),
                func.max(EZTVShow.updated_at),
                func.coalesce(func.sum(EZTVShow.episodes_count), 0),
            )
        ).one()
        p2p_sig: tuple[Any, ...] = (0, 0)
        try:
            src_p2p = eztv_session.exec(
                select(
                    func.count(CatalogShow.imdb_id),
                    func.coalesce(func.max(CatalogShow.max_seeds), 0),
                )
            ).one()
            p2p_sig = (int(src_p2p[0] or 0), int(src_p2p[1] or 0))
        except Exception:
            p2p_sig = (0, 0)
        if p2p_sig == (0, 0) and p2p_session is not None:
            p2p_row = p2p_session.exec(
                select(
                    func.count(CatalogShow.imdb_id),
                    func.coalesce(func.max(CatalogShow.max_seeds), 0),
                )
            ).one()
            p2p_sig = (int(p2p_row[0] or 0), int(p2p_row[1] or 0))
        return (int(row[0] or 0), str(row[1] or ""), int(row[2] or 0)) + p2p_sig

    @staticmethod
    def _build_p2p_map(
        p2p_session: Optional[Session], fallback_session: Optional[Session] = None
    ) -> dict[str, CatalogShow]:
        """Load P2P seed telemetry indexed by normalized IMDb ID (sources.db primary)."""
        rows: list[CatalogShow] = []
        if p2p_session is not None:
            try:
                rows = list(p2p_session.exec(select(CatalogShow)).all())
            except Exception:
                rows = []
        if not rows and fallback_session is not None and fallback_session is not p2p_session:
            try:
                rows = list(fallback_session.exec(select(CatalogShow)).all())
            except Exception:
                rows = []
        return {CatalogRepository.normalize_imdb_id(r.imdb_id): r for r in rows if r.imdb_id}

    @staticmethod
    def _build_episode_stats_map(
        eztv_session: Session, show_ids: list[int]
    ) -> dict[int, tuple[int, int, int]]:
        """Bulk fetch (episode_count, max_season, max_episode) for a small batch of show IDs."""
        if not show_ids:
            return {}
        stmt = (
            select(
                EZTVEpisodeCatalog.show_id,
                func.count(EZTVEpisodeCatalog.id),
                func.max(EZTVEpisodeCatalog.season),
                func.max(EZTVEpisodeCatalog.episode),
            )
            .where(col(EZTVEpisodeCatalog.show_id).in_(show_ids))
            .group_by(EZTVEpisodeCatalog.show_id)
        )
        rows = eztv_session.exec(stmt).all()
        return {int(r[0]): (int(r[1] or 0), int(r[2] or 0), int(r[3] or 0)) for r in rows}

    @staticmethod
    def _resolve_episode_stats(
        eztv_session: Session, shows: list[EZTVShow]
    ) -> dict[int, tuple[int, int, int]]:
        """Use materialized episode stats in O(1), with fallback only for unmaterialized IDs."""
        stats: dict[int, tuple[int, int, int]] = {}
        missing_ids: list[int] = []
        for s in shows:
            if s.id is None:
                continue
            sid = int(s.id)
            if (s.episodes_count or 0) > 0:
                stats[sid] = (
                    int(s.episodes_count or 0),
                    int(s.max_season or 0),
                    int(s.max_episode or 0),
                )
            else:
                missing_ids.append(sid)
        if missing_ids and len(missing_ids) <= 50:
            fallback = CatalogRepository._build_episode_stats_map(eztv_session, missing_ids)
            for sid in missing_ids:
                stats[sid] = fallback.get(sid, (0, 0, 0))
        return stats

    @staticmethod
    def _serialize_eztv_show(
        show: EZTVShow,
        ep_stats: tuple[int, int, int],
        p2p_info: Optional[CatalogShow] = None,
    ) -> dict[str, Any]:
        """Serialize an EZTVShow row into the unified CatalogShow API contract."""
        ep_count, max_season, max_episode = ep_stats
        show_id = int(show.id or 0)
        imdb_id = (
            CatalogRepository.normalize_imdb_id(show.imdb_id)
            if show.imdb_id
            else f"eztv-{show_id}"
        )
        return {
            "eztv_show_id": show_id,
            "imdb_id": imdb_id,
            "slug": show.slug,
            "title": show.name,
            "original_title": None,
            "overview": show.synopsis or "",
            "poster_url": show.poster_url,
            "backdrop_url": None,
            "rating": float(show.rating_score or 0.0),
            "genres": show.genres or "",
            "first_air_date": show.premiered,
            "status": show.status,
            "network": show.network,
            "streaming_providers": (
                [p.strip() for p in show.streaming_providers.split(",") if p.strip()]
                if show.streaming_providers
                else ([show.network] if show.network else [])
            ),
            "air_day_time": show.air_day_time,
            "tvmaze_id": show.tvmaze_id,
            "episodes_count": ep_count,
            "total_torrents": p2p_info.total_torrents if p2p_info else 0,
            "max_seeds": p2p_info.max_seeds if p2p_info else 0,
            "latest_season": p2p_info.latest_season if p2p_info else max_season,
            "latest_episode": p2p_info.latest_episode if p2p_info else max_episode,
            "latest_release_date": (
                p2p_info.latest_release_date.isoformat()
                if p2p_info and p2p_info.latest_release_date
                else show.updated_at
            ),
            "is_enriched": bool(show.poster_url and show.synopsis),
        }

    @staticmethod
    def _fts_search_ids(eztv_session: Session, raw_search: str) -> Optional[list[int]]:
        """Query shows_fts virtual index when available; return None to fall back to ILIKE."""
        tokens = re.findall(r"[a-zA-Z0-9]+", raw_search.lower())
        if not tokens:
            return None
        fts_expr = " AND ".join(f'"{t}"*' for t in tokens)
        try:
            rows = eztv_session.exec(
                text("SELECT rowid FROM shows_fts WHERE shows_fts MATCH :expr"),
                params={"expr": fts_expr},
            ).all()
            ids = [int(r[0]) for r in rows if r[0] is not None]
            return ids if ids else None
        except Exception:
            return None

    @staticmethod
    def _apply_genre_filter(query, genre: str):
        raw_tokens = [t.strip().lower() for t in genre.split(",") if t.strip()]
        genre_clauses = []
        for token in raw_tokens:
            terms = _GENRE_SYNONYMS.get(token, [token])
            for term in terms:
                genre_clauses.append(col(EZTVShow.genres).ilike(f"%{term}%"))
        if genre_clauses:
            query = query.where(or_(*genre_clauses))
        return query

    @staticmethod
    def _matches_genre_in_memory(genres_str: str, genre_filter: Optional[str]) -> bool:
        """Evaluate genre filter against an in-memory show genre CSV string."""
        if not genre_filter:
            return True
        if not genres_str:
            return False
        lower_genres = genres_str.lower()
        raw_tokens = [t.strip().lower() for t in genre_filter.split(",") if t.strip()]
        for token in raw_tokens:
            terms = _GENRE_SYNONYMS.get(token, [token])
            for term in terms:
                if term in lower_genres:
                    return True
        return False

    @staticmethod
    def _get_all_serialized_shows(
        eztv_session: Session, p2p_session: Optional[Session] = None
    ) -> list[dict[str, Any]]:
        """Load and cache all serialized EZTVShow items keyed by database fingerprint."""
        scope = catalog_cache.session_scope(eztv_session, p2p_session)
        fp = CatalogRepository._fingerprint(eztv_session, p2p_session)

        def _compute() -> list[dict[str, Any]]:
            all_shows = list(eztv_session.exec(select(EZTVShow)).all())
            if not all_shows:
                return []
            p2p_map = CatalogRepository._build_p2p_map(eztv_session, p2p_session)
            ep_map = CatalogRepository._resolve_episode_stats(eztv_session, all_shows)
            return [
                CatalogRepository._serialize_eztv_show(
                    s,
                    ep_map.get(
                        int(s.id or 0),
                        (
                            int(s.episodes_count or 0),
                            int(s.max_season or 0),
                            int(s.max_episode or 0),
                        ),
                    ),
                    p2p_map.get(CatalogRepository.normalize_imdb_id(s.imdb_id))
                    if s.imdb_id
                    else None,
                )
                for s in all_shows
            ]

        return catalog_cache.get_or_set(scope, "all_serialized", fp, _compute)

    @staticmethod
    def list_shows(
        eztv_session: Session,
        p2p_session: Optional[Session] = None,
        search: Optional[str] = None,
        genre: Optional[str] = None,
        min_seeds: int = 0,
        sort_by: str = "seeds",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query EZTV shows from eztv_metadata.db with O(1) materialized stats, FTS5, and cache."""
        fts_id_set: Optional[set[int]] = None
        search_lower: Optional[str] = None
        if search:
            fts_ids = CatalogRepository._fts_search_ids(eztv_session, search)
            if fts_ids is not None:
                fts_id_set = set(fts_ids)
            else:
                search_lower = search.strip().lower()

        all_items = CatalogRepository._get_all_serialized_shows(eztv_session, p2p_session)
        filtered: list[dict[str, Any]] = []
        for item in all_items:
            if fts_id_set is not None and item["eztv_show_id"] not in fts_id_set:
                continue
            if search_lower is not None:
                if (
                    search_lower not in (item["title"] or "").lower()
                    and search_lower not in (item["imdb_id"] or "").lower()
                    and search_lower not in (item["slug"] or "").lower()
                ):
                    continue
            if genre and not CatalogRepository._matches_genre_in_memory(item["genres"], genre):
                continue
            if min_seeds > 0 and item["max_seeds"] < min_seeds:
                continue
            filtered.append(item)

        total_count = len(filtered)
        if sort_by == "seeds":
            filtered.sort(
                key=lambda x: (x["max_seeds"], x["rating"], x["episodes_count"]),
                reverse=True,
            )
        elif sort_by == "torrents":
            filtered.sort(
                key=lambda x: (x["total_torrents"], x["episodes_count"], x["rating"]),
                reverse=True,
            )
        elif sort_by == "date":
            filtered.sort(
                key=lambda x: (
                    x["first_air_date"] or "",
                    str(x["latest_release_date"] or ""),
                ),
                reverse=True,
            )
        elif sort_by == "name":
            filtered.sort(key=lambda x: (x["title"] or "").lower())
        else:
            filtered.sort(
                key=lambda x: (x["rating"], x["eztv_show_id"]),
                reverse=True,
            )

        offset = (page - 1) * page_size
        return filtered[offset : offset + page_size], total_count

    @staticmethod
    def get_genres_with_counts(eztv_session: Session) -> list[dict[str, Any]]:
        """Aggregate genre counts across all shows in eztv_metadata.db with engine-scoped cache."""
        scope = catalog_cache.session_scope(eztv_session)
        fp = CatalogRepository._fingerprint(eztv_session)

        def _compute() -> list[dict[str, Any]]:
            rows = eztv_session.exec(
                select(EZTVShow.genres).where(col(EZTVShow.genres).is_not(None))
            ).all()
            counts: dict[str, int] = {}
            for g_str in rows:
                if not g_str:
                    continue
                for part in g_str.split(","):
                    clean = part.strip()
                    if clean:
                        counts[clean] = counts.get(clean, 0) + 1
            sorted_genres = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            return [{"genre": k, "count": v} for k, v in sorted_genres]

        return catalog_cache.get_or_set(scope, "genres", fp, _compute)

    @staticmethod
    def get_curated_sections(
        eztv_session: Session, p2p_session: Optional[Session] = None
    ) -> list[dict[str, Any]]:
        """Produce curated sections over eztv_metadata.db in a single pass with cache (DEC-004)."""
        scope = catalog_cache.session_scope(eztv_session, p2p_session)
        fp = CatalogRepository._fingerprint(eztv_session, p2p_session)

        def _compute() -> list[dict[str, Any]]:
            all_serialized = CatalogRepository._get_all_serialized_shows(
                eztv_session, p2p_session
            )
            if not all_serialized:
                return []
            has_p2p = any(item["max_seeds"] > 0 for item in all_serialized)

            section_specs = [
                ("top_p2p", "Em Alta no Catálogo EZTV", "Flame", None, "seeds"),
                ("recent_releases", "Estreias & Recentes", "Clock", None, "date"),
                (
                    "scifi_fantasy",
                    "Ficção Científica & Fantasia",
                    "Zap",
                    "sci-fi,fantasy",
                    "rating",
                ),
                ("action_adventure", "Ação & Aventura", "Film", "action,adventure", "rating"),
                (
                    "crime_mystery",
                    "Crime, Investigação & Mistério",
                    "Shield",
                    "crime,mystery",
                    "rating",
                ),
                ("comedy", "Comédias & Sitcoms", "Smile", "comedy", "rating"),
                (
                    "documentaries",
                    "Documentários, História & Natureza",
                    "Compass",
                    "documentary",
                    "rating",
                ),
            ]

            sections: list[dict[str, Any]] = []
            for sec_id, title, icon, genre_filter, sort_by in section_specs:
                matched = [
                    item
                    for item in all_serialized
                    if CatalogRepository._matches_genre_in_memory(item["genres"], genre_filter)
                ]
                if not matched:
                    continue
                if sort_by == "seeds" and has_p2p:
                    matched.sort(
                        key=lambda x: (x["max_seeds"], x["rating"], x["episodes_count"]),
                        reverse=True,
                    )
                elif sort_by == "date":
                    matched.sort(
                        key=lambda x: (
                            x["first_air_date"] or "",
                            str(x["latest_release_date"] or ""),
                        ),
                        reverse=True,
                    )
                else:
                    matched.sort(
                        key=lambda x: (x["rating"], x["eztv_show_id"]),
                        reverse=True,
                    )
                sections.append(
                    {"id": sec_id, "title": title, "icon": icon, "items": matched[:20]}
                )
            return sections

        return catalog_cache.get_or_set(scope, "sections", fp, _compute)

    @staticmethod
    def get_show(eztv_session: Session, identifier: str) -> Optional[EZTVShow]:
        """Resolve an EZTV show by IMDb ID (tt...) or numeric EZTV show ID."""
        raw = identifier.strip()
        if raw.isdigit():
            by_id = eztv_session.get(EZTVShow, int(raw))
            if by_id:
                return by_id
        if raw.lower().startswith("eztv-") and raw[5:].isdigit():
            return eztv_session.get(EZTVShow, int(raw[5:]))

        clean_imdb = CatalogRepository.normalize_imdb_id(raw)
        return eztv_session.exec(
            select(EZTVShow).where(EZTVShow.imdb_id == clean_imdb)
        ).first()

    @staticmethod
    def get_show_detail(
        eztv_session: Session,
        p2p_session: Optional[Session],
        identifier: str,
    ) -> Optional[dict[str, Any]]:
        """Get show metadata, cataloged episodes, and optional P2P releases."""
        show = CatalogRepository.get_show(eztv_session, identifier)
        if not show or show.id is None:
            return None

        episodes = list(
            eztv_session.exec(
                select(EZTVEpisodeCatalog)
                .where(EZTVEpisodeCatalog.show_id == show.id)
                .order_by(
                    col(EZTVEpisodeCatalog.season).desc(),
                    col(EZTVEpisodeCatalog.episode).desc(),
                )
            ).all()
        )
        ep_count = len(episodes)
        max_season = max((e.season for e in episodes), default=0)
        max_episode = max(
            (e.episode for e in episodes if e.season == max_season), default=0
        )

        p2p_info = None
        releases: list[CatalogRelease] = []
        if show.imdb_id:
            norm_imdb = CatalogRepository.normalize_imdb_id(show.imdb_id)
            try:
                p2p_info = eztv_session.get(CatalogShow, norm_imdb)
                releases = CatalogRepository.get_show_releases(eztv_session, norm_imdb)
            except Exception:
                p2p_info = None
                releases = []
            if not p2p_info and p2p_session is not None:
                p2p_info = p2p_session.get(CatalogShow, norm_imdb)
            if not releases and p2p_session is not None:
                releases = CatalogRepository.get_show_releases(p2p_session, norm_imdb)

        return {
            "show": CatalogRepository._serialize_eztv_show(
                show, (ep_count, max_season, max_episode), p2p_info
            ),
            "episodes": episodes,
            "releases": releases,
        }

    @staticmethod
    def get_show_releases(p2p_session: Session, imdb_id: str) -> list[CatalogRelease]:
        """Get all indexed P2P releases for a show ordered by season, episode, and seeds."""
        clean_id = CatalogRepository.normalize_imdb_id(imdb_id)
        query = (
            select(CatalogRelease)
            .where(CatalogRelease.imdb_id == clean_id)
            .order_by(
                col(CatalogRelease.season).desc(),
                col(CatalogRelease.episode).desc(),
                col(CatalogRelease.seeds).desc(),
            )
        )
        return list(p2p_session.exec(query).all())

    @staticmethod
    def get_stats(
        eztv_session: Session, p2p_session: Optional[Session] = None
    ) -> dict[str, Any]:
        """Get aggregate statistics using materialized episode counts and scoped cache."""
        scope = catalog_cache.session_scope(eztv_session, p2p_session)
        fp = CatalogRepository._fingerprint(eztv_session, p2p_session)

        def _compute() -> dict[str, Any]:
            total_shows = int(eztv_session.exec(select(func.count(EZTVShow.id))).one() or 0)
            materialized_eps = int(
                eztv_session.exec(
                    select(func.coalesce(func.sum(EZTVShow.episodes_count), 0))
                ).one()
                or 0
            )
            if materialized_eps > 0:
                total_episodes = materialized_eps
            else:
                total_episodes = int(
                    eztv_session.exec(select(func.count(EZTVEpisodeCatalog.id))).one() or 0
                )
            latest_eztv_date = eztv_session.exec(select(func.max(EZTVShow.updated_at))).one()

            total_releases = 0
            max_seeds = 0
            latest_p2p_date = None
            try:
                total_releases = int(
                    eztv_session.exec(select(func.count(CatalogRelease.id))).one() or 0
                )
                max_seeds = int(
                    eztv_session.exec(select(func.max(CatalogShow.max_seeds))).one() or 0
                )
                latest_p2p_date = eztv_session.exec(
                    select(func.max(CatalogShow.latest_release_date))
                ).one()
            except Exception:
                total_releases = 0
                max_seeds = 0
                latest_p2p_date = None

            if p2p_session is not None and total_releases == 0 and max_seeds == 0:
                total_releases = int(
                    p2p_session.exec(select(func.count(CatalogRelease.id))).one() or 0
                )
                max_seeds = int(
                    p2p_session.exec(select(func.max(CatalogShow.max_seeds))).one() or 0
                )
                latest_p2p_date = latest_p2p_date or p2p_session.exec(
                    select(func.max(CatalogShow.latest_release_date))
                ).one()

            return {
                "total_shows": total_shows,
                "total_episodes": total_episodes,
                "total_releases": total_releases,
                "max_seeds_in_catalog": max_seeds,
                "latest_release_date": latest_p2p_date or latest_eztv_date,
            }

        return catalog_cache.get_or_set(scope, "stats", fp, _compute)
