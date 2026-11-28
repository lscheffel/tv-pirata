"""Organic Discovery Feed Engine (Hero Pool, Contrastive Roulette & 10x100 Unique Smart Lists)."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from sqlalchemy import or_, text
from sqlmodel import Session, col, select

from src.backend.core.cache import discovery_cache
from src.backend.core.canonical_taxonomy import expand_genre_synonyms, normalize_genre_tokens
from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.db import ShowRecord
from src.backend.repositories.discovery_engine import DiscoveryEngineRepository
from src.backend.repositories.preferences import (
    ExplorePreferencesRepository,
    SmartListConfig,
    UserExplorePreferences,
)

IMPRESSIONS_SYNC_KEY = "discovery_impressions_v1"
MAX_IMPRESSIONS = 200

STATUS_WEIGHTS: dict[str, float] = {
    "watching": 3.0,
    "completed": 2.0,
    "plan_to_watch": 1.0,
    "paused": 0.5,
    "on_hold": 0.5,
    "abandoned": -1.0,
    "dropped": -1.0,
}

RouletteScope = Literal["all", "movie", "tv_show", "with_media"]


def _det_noise(seed: str, list_id: str, imdb_id: str) -> float:
    """Deterministic uniform pseudo-random float in [0.0, 1.0] via SHA-256."""
    digest = hashlib.sha256(f"{seed}|{list_id}|{imdb_id}".encode("utf-8")).digest()
    val = int.from_bytes(digest[:4], "big")
    return val / 4294967295.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiscoveryFeedService:
    """Read-only organic feed generator + decoupled impression tracker (ADR-021)."""

    @staticmethod
    def _load_impressions(session: Session, ttl_hours: int) -> dict[str, datetime]:
        """Load active impression timestamps from sync_state within TTL."""
        ExplorePreferencesRepository._ensure_sync_state_table(session)
        cutoff = _utcnow() - timedelta(hours=max(1, ttl_hours))
        try:
            row = session.exec(
                text("SELECT value FROM sync_state WHERE key = :key"),
                params={"key": IMPRESSIONS_SYNC_KEY},
            ).first()
            if not row or not row[0]:
                return {}
            raw = json.loads(row[0])
            out: dict[str, datetime] = {}
            for entry in raw if isinstance(raw, list) else []:
                if not isinstance(entry, dict):
                    continue
                imdb_id = str(entry.get("imdb_id") or "").strip()
                ts_raw = entry.get("ts")
                if not imdb_id or not ts_raw:
                    continue
                try:
                    dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= cutoff:
                        prev = out.get(imdb_id)
                        if prev is None or dt > prev:
                            out[imdb_id] = dt
                except ValueError:
                    continue
            return out
        except Exception:
            return {}

    @staticmethod
    def record_impressions(
        session: Session,
        imdb_ids: list[str],
        *,
        surface: str = "hero",
        ttl_hours: int = 48,
    ) -> dict[str, Any]:
        """Persist exposed imdb_ids in discovery_impressions_v1 ring-buffer (max 200)."""
        ExplorePreferencesRepository._ensure_sync_state_table(session)
        now = _utcnow()
        cutoff = now - timedelta(hours=max(1, ttl_hours))
        existing_map: dict[str, dict[str, str]] = {}
        try:
            row = session.exec(
                text("SELECT value FROM sync_state WHERE key = :key"),
                params={"key": IMPRESSIONS_SYNC_KEY},
            ).first()
            if row and row[0]:
                for item in json.loads(row[0]):
                    if not isinstance(item, dict):
                        continue
                    iid = str(item.get("imdb_id") or "").strip()
                    ts_raw = str(item.get("ts") or "")
                    if not iid or not ts_raw:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt >= cutoff:
                            existing_map[iid] = {
                                "imdb_id": iid,
                                "ts": dt.isoformat(),
                                "surface": str(item.get("surface") or "hero"),
                            }
                    except ValueError:
                        continue
        except Exception:
            existing_map = {}

        now_iso = now.isoformat()
        for raw_id in imdb_ids:
            iid = str(raw_id or "").strip()
            if iid:
                existing_map[iid] = {"imdb_id": iid, "ts": now_iso, "surface": surface}

        ordered = sorted(existing_map.values(), key=lambda x: x["ts"], reverse=True)[
            :MAX_IMPRESSIONS
        ]
        session.exec(
            text(
                """
                INSERT INTO sync_state (key, value, updated_at)
                VALUES (:key, :val, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            params={"key": IMPRESSIONS_SYNC_KEY, "val": json.dumps(ordered)},
        )
        session.commit()
        return {"recorded": len(imdb_ids), "active_buffer": len(ordered)}

    @staticmethod
    def _build_library_profile(session: Session) -> dict[str, Any]:
        """Build bilingual normalized genre affinity profile and anchor titles from ShowRecord."""
        shows = list(session.exec(select(ShowRecord)).all())
        genre_scores: dict[str, float] = {}
        library_imdb_ids: set[str] = set()
        completed_imdb_ids: set[str] = set()
        anchors: list[tuple[float, ShowRecord]] = []

        for s in shows:
            if s.imdb_id:
                library_imdb_ids.add(s.imdb_id)
                if s.user_status == "completed":
                    completed_imdb_ids.add(s.imdb_id)
            weight = STATUS_WEIGHTS.get(s.user_status, 1.0)
            if weight > 0:
                anchors.append((weight + float(s.rating or 0.0) * 0.1, s))
            for cg in normalize_genre_tokens(s.genres):
                genre_scores[cg] = genre_scores.get(cg, 0.0) + weight

        positive_genres = sorted(
            ((g, sc) for g, sc in genre_scores.items() if sc > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        max_sc = positive_genres[0][1] if positive_genres else 1.0
        normalized_affinity = {g: round(sc / max_sc, 4) for g, sc in positive_genres}
        anchors.sort(key=lambda x: x[0], reverse=True)
        anchor_show = anchors[0][1] if anchors else None
        anchor_genres = normalize_genre_tokens(anchor_show.genres) if anchor_show else []
        return {
            "genre_affinity": normalized_affinity,
            "top_genres": [g for g, _ in positive_genres[:5]],
            "library_imdb_ids": library_imdb_ids,
            "completed_imdb_ids": completed_imdb_ids,
            "anchor_title": anchor_show.title if anchor_show else None,
            "anchor_imdb_id": anchor_show.imdb_id if anchor_show else None,
            "anchor_genres": anchor_genres,
        }

    @staticmethod
    def _score_row(
        row: IMDbCatalogShow,
        *,
        media_sources_by_imdb: dict[str, list[str]],
        eztv_by_imdb: dict[str, int],
        profile: dict[str, Any],
        impressions: dict[str, datetime],
        variance_pct: int,
        session_seed: str,
        list_id: str,
        sort_by: str = "balanced",
    ) -> float:
        year = int(row.start_year or 2000)
        recency = max(0.0, min(1.0, (year - 2010) / 16.0))
        rating_norm = max(0.0, min(1.0, float(row.rating_score or 0.0) / 10.0))
        votes_norm = max(0.0, min(1.0, math.log10(max(1, int(row.rating_votes or 1))) / 6.0))
        quality = 0.65 * rating_norm + 0.35 * votes_norm

        row_genres = normalize_genre_tokens(row.genres)
        aff_map: dict[str, float] = profile["genre_affinity"]
        affinity = max((aff_map.get(g, 0.0) for g in row_genres), default=0.0) if aff_map else 0.0

        has_media = bool(
            row.has_eztv or row.imdb_id in media_sources_by_imdb or row.imdb_id in eztv_by_imdb
        )
        media_score = 1.0 if has_media else 0.0

        if sort_by == "rating":
            base = 0.65 * rating_norm + 0.20 * votes_norm + 0.15 * recency
        elif sort_by == "popularity":
            base = 0.70 * votes_norm + 0.20 * rating_norm + 0.10 * recency
        elif sort_by == "newest":
            base = 0.70 * recency + 0.20 * rating_norm + 0.10 * media_score
        elif sort_by == "p2p_recent":
            base = 0.45 * media_score + 0.35 * recency + 0.20 * rating_norm
        else:
            base = 0.35 * recency + 0.30 * quality + 0.20 * affinity + 0.15 * media_score

        if row.imdb_id in impressions:
            base -= 0.35

        v = max(0.0, min(1.0, variance_pct / 100.0))
        if v <= 0.0:
            return base
        noise = _det_noise(session_seed, list_id, row.imdb_id)
        return (1.0 - 0.65 * v) * base + (0.65 * v) * noise

    @staticmethod
    def _genre_or_clause(genres: list[str]) -> Any:
        """Expand canonical PT-BR genres to bilingual synonyms for SQLite LIKE matching."""
        tokens: list[str] = []
        for g in genres:
            for syn in expand_genre_synonyms(g):
                if syn not in tokens:
                    tokens.append(syn)
        if not tokens:
            return None
        return or_(*(col(IMDbCatalogShow.genres).contains(tok) for tok in tokens))

    @classmethod
    def _query_bucket_candidates(
        cls,
        session: Session,
        category: str,
        *,
        profile: dict[str, Any],
        media_imdb_set: set[str],
        only_with_media: bool = False,
        pool_limit: int = 260,
    ) -> tuple[list[IMDbCatalogShow], dict[str, Any], str]:
        """Fetch pre-filtered quality pool + CatalogView FilterSnapshot for a category."""
        stmt = select(IMDbCatalogShow).where(col(IMDbCatalogShow.poster_url).is_not(None))
        catalog_filter: dict[str, Any] = {}
        display_title_override = ""

        if category == "trending_now":
            stmt = stmt.where(
                col(IMDbCatalogShow.start_year) >= 2024,
                col(IMDbCatalogShow.rating_score) >= 6.8,
                col(IMDbCatalogShow.rating_votes) >= 500,
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"yearFrom": "2024", "minRating": 6.8, "sortBy": "popularity"}
        elif category == "p2p_fresh":
            stmt = stmt.where(
                col(IMDbCatalogShow.start_year) >= 2020,
                col(IMDbCatalogShow.rating_score) >= 6.0,
            )
            if media_imdb_set:
                sample_ids = list(media_imdb_set)[:900]
                stmt = stmt.where(col(IMDbCatalogShow.imdb_id).in_(sample_ids))
            stmt = stmt.order_by(
                col(IMDbCatalogShow.start_year).desc(),
                col(IMDbCatalogShow.rating_votes).desc(),
            )
            catalog_filter = {
                "selectedSources": ["media"],
                "yearFrom": "2020",
                "sortBy": "year_desc",
            }
        elif category == "acclaimed_movies":
            stmt = stmt.where(
                col(IMDbCatalogShow.title_type) == "movie",
                col(IMDbCatalogShow.rating_score) >= 7.8,
                col(IMDbCatalogShow.rating_votes) >= 5000,
            ).order_by(col(IMDbCatalogShow.rating_score).desc())
            catalog_filter = {"selectedTypes": ["movie"], "minRating": 7.8, "sortBy": "rating"}
        elif category == "running_series":
            stmt = stmt.where(
                col(IMDbCatalogShow.title_type).in_(["tvSeries", "tvMiniSeries"]),
                col(IMDbCatalogShow.status) == "Running",
                col(IMDbCatalogShow.rating_score) >= 6.8,
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {
                "selectedTypes": ["tv_show", "mini_series"],
                "selectedStatus": "Running",
                "minRating": 6.8,
                "sortBy": "popularity",
            }
        elif category == "scifi_fantasy_thriller":
            g_clause = cls._genre_or_clause(["Ficção Científica", "Fantasia", "Suspense"])
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.0,
                col(IMDbCatalogShow.rating_votes) >= 2000,
                g_clause,
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {
                "genresAny": ["Ficção Científica", "Fantasia", "Suspense"],
                "minRating": 7.0,
            }
        elif category == "crime_mystery":
            g_clause = cls._genre_or_clause(["Crime & Investigação", "Mistério"])
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.2,
                col(IMDbCatalogShow.rating_votes) >= 2000,
                g_clause,
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {
                "genresAny": ["Crime & Investigação", "Mistério"],
                "minRating": 7.2,
            }
        elif category == "anime_animation_docs":
            g_clause = cls._genre_or_clause(["Animação", "Documentário"])
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.3,
                col(IMDbCatalogShow.rating_votes) >= 1500,
                ((col(IMDbCatalogShow.title_type) == "animation") | g_clause),
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {
                "genresAny": ["Animação", "Documentário"],
                "minRating": 7.3,
            }
        elif category == "because_you_watched":
            anchor_genres: list[str] = profile.get("anchor_genres") or []
            anchor_title = profile.get("anchor_title")
            if anchor_title:
                display_title_override = f"Porque você assiste/curtiu {anchor_title}"
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.0,
                col(IMDbCatalogShow.rating_votes) >= 1500,
            )
            if anchor_genres:
                g_clause = cls._genre_or_clause(anchor_genres[:2])
                if g_clause is not None:
                    stmt = stmt.where(g_clause)
                catalog_filter = {"genresAny": anchor_genres[:2], "minRating": 7.0}
            stmt = stmt.order_by(col(IMDbCatalogShow.rating_votes).desc())
        elif category == "on_your_radar":
            top_g: list[str] = profile.get("top_genres") or ["Drama", "Suspense"]
            g_clause = cls._genre_or_clause(top_g[:2])
            stmt = stmt.where(
                col(IMDbCatalogShow.start_year) >= 2020,
                col(IMDbCatalogShow.rating_score) >= 7.0,
                col(IMDbCatalogShow.rating_votes) >= 1000,
            )
            if g_clause is not None:
                stmt = stmt.where(g_clause)
            stmt = stmt.order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"genresAny": top_g[:3], "yearFrom": "2020", "minRating": 7.0}
        elif category == "hidden_gems_for_you":
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.9,
                col(IMDbCatalogShow.rating_votes) >= 500,
                col(IMDbCatalogShow.rating_votes) <= 45000,
            ).order_by(col(IMDbCatalogShow.rating_score).desc())
            catalog_filter = {"minRating": 7.9, "sortBy": "rating"}
        elif category == "horror_supernatural":
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 6.8,
                cls._genre_or_clause(["Terror"]),
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"genresAny": ["Terror"], "minRating": 6.8}
        elif category == "action_adventure":
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.0,
                cls._genre_or_clause(["Ação", "Aventura"]),
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"genresAny": ["Ação", "Aventura"], "minRating": 7.0}
        elif category == "miniseries_fast":
            stmt = stmt.where(
                col(IMDbCatalogShow.title_type) == "tvMiniSeries",
                col(IMDbCatalogShow.rating_score) >= 7.5,
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"selectedTypes": ["mini_series"], "minRating": 7.5}
        elif category == "classics_masterpieces":
            stmt = stmt.where(
                col(IMDbCatalogShow.start_year) <= 2010,
                col(IMDbCatalogShow.rating_score) >= 8.4,
                col(IMDbCatalogShow.rating_votes) >= 10000,
            ).order_by(col(IMDbCatalogShow.rating_score).desc())
            catalog_filter = {"yearTo": "2010", "minRating": 8.4, "sortBy": "rating"}
        elif category == "releases_2026":
            stmt = stmt.where(
                col(IMDbCatalogShow.start_year) >= 2026,
                col(IMDbCatalogShow.rating_score) >= 6.0,
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"yearFrom": "2026", "sortBy": "popularity"}
        else:
            stmt = stmt.where(
                col(IMDbCatalogShow.rating_score) >= 7.0,
                cls._genre_or_clause(["Comédia"]),
            ).order_by(col(IMDbCatalogShow.rating_votes).desc())
            catalog_filter = {"genresAny": ["Comédia"], "minRating": 7.0}

        scope = discovery_cache.session_scope(session)
        top_key = ":".join(profile.get("top_genres", [])[:2])
        anchor_key = profile.get("anchor_imdb_id") or ""
        cache_key = f"feed_bucket:{category}:{pool_limit}:{top_key}:{anchor_key}"
        rows = discovery_cache.get_or_set(
            scope,
            cache_key,
            (len(media_imdb_set) if category == "p2p_fresh" else 0),
            lambda: list(session.exec(stmt.limit(pool_limit)).all()),
        )
        if only_with_media:
            rows = [r for r in rows if r.has_eztv or r.imdb_id in media_imdb_set]
        return rows, catalog_filter, display_title_override

    @classmethod
    def get_feed(
        cls,
        session: Session,
        eztv_session: Optional[Session],
        *,
        session_seed: str = "default",
        roulette_scope: RouletteScope = "all",
        roulette_spin: int = 0,
    ) -> dict[str, Any]:
        """Build complete read-only Discover Feed (Hero Pool, Roulette, 10x100 Unique Lists)."""
        if not DiscoveryEngineRepository._has_imdb_catalog(session):
            return {
                "hero_pool": [],
                "roulette": [],
                "smart_lists": [],
                "dynamic_shortcuts": [],
                "stats": {"unique_titles": 0},
            }

        prefs: UserExplorePreferences = ExplorePreferencesRepository.get_preferences(session)
        impressions = cls._load_impressions(session, prefs.impression_ttl_hours)
        profile = cls._build_library_profile(session)
        eztv_by_imdb, _ = DiscoveryEngineRepository.build_eztv_lookup_index(eztv_session)
        media_sources_by_imdb = DiscoveryEngineRepository._build_sources_media_index(eztv_session)
        media_imdb_set = set(media_sources_by_imdb.keys()) | set(eztv_by_imdb.keys())

        seen_global: set[str] = set()
        completed_ids: set[str] = profile["completed_imdb_ids"]

        # 1. Hero Pool (12–15 rotated candidates with backdrop + rating >= 7.0 + recency)
        hero_candidates = list(
            session.exec(
                select(IMDbCatalogShow)
                .where(
                    col(IMDbCatalogShow.start_year) >= 2022,
                    col(IMDbCatalogShow.backdrop_url).is_not(None),
                    col(IMDbCatalogShow.poster_url).is_not(None),
                    col(IMDbCatalogShow.rating_score) >= 7.0,
                )
                .order_by(col(IMDbCatalogShow.rating_votes).desc())
                .limit(120)
            ).all()
        )
        hero_candidates = [r for r in hero_candidates if r.imdb_id not in completed_ids]
        hero_candidates.sort(
            key=lambda r: cls._score_row(
                r,
                media_sources_by_imdb=media_sources_by_imdb,
                eztv_by_imdb=eztv_by_imdb,
                profile=profile,
                impressions=impressions,
                variance_pct=max(prefs.discovery_variance_pct, 35),
                session_seed=session_seed,
                list_id="hero_pool",
            ),
            reverse=True,
        )
        hero_pool: list[dict[str, Any]] = []
        for r in hero_candidates[:12]:
            seen_global.add(r.imdb_id)
            u = DiscoveryEngineRepository._imdb_row_to_unified(
                r, eztv_by_imdb, media_sources_by_imdb=media_sources_by_imdb
            ).model_dump()
            r_genres = normalize_genre_tokens(r.genres)
            matched_aff = [g for g in r_genres if g in profile["genre_affinity"]]
            if matched_aff and profile.get("anchor_title"):
                u["highlight_reason"] = (
                    f"Afinidade com {profile['anchor_title']} · {matched_aff[0]}"
                )
            elif r.start_year and r.start_year >= 2025:
                u["highlight_reason"] = f"Destaque {r.start_year} · Nota {r.rating_score or 0:.1f}"
            else:
                u["highlight_reason"] = f"Em alta · {r.rating_votes or 0:,} votos".replace(",", ".")
            hero_pool.append(u)

        # 2. Contextual Stratified Roulette (3 contrasting archetypes)
        r_stmt = select(IMDbCatalogShow).where(
            col(IMDbCatalogShow.poster_url).is_not(None),
            col(IMDbCatalogShow.rating_score) >= 6.8,
        )
        if roulette_scope == "movie":
            r_stmt = r_stmt.where(col(IMDbCatalogShow.title_type) == "movie")
        elif roulette_scope == "tv_show":
            r_stmt = r_stmt.where(col(IMDbCatalogShow.title_type).in_(["tvSeries", "tvMiniSeries"]))
        r_pool = list(
            session.exec(r_stmt.order_by(col(IMDbCatalogShow.rating_votes).desc()).limit(260)).all()
        )
        if roulette_scope == "with_media":
            r_pool = [r for r in r_pool if r.has_eztv or r.imdb_id in media_imdb_set]
        r_pool = [
            r for r in r_pool if r.imdb_id not in seen_global and r.imdb_id not in completed_ids
        ]

        roulette_seed = f"{session_seed}:spin:{roulette_spin}:{roulette_scope}"
        roulette_items: list[dict[str, Any]] = []

        def _pick_roulette(sub_pool: list[IMDbCatalogShow], tag: str, slot_key: str) -> None:
            avail = [x for x in sub_pool if x.imdb_id not in seen_global]
            if not avail:
                avail = [x for x in r_pool if x.imdb_id not in seen_global]
            if not avail:
                return
            avail.sort(
                key=lambda x: _det_noise(roulette_seed, slot_key, x.imdb_id),
                reverse=True,
            )
            chosen = avail[0]
            seen_global.add(chosen.imdb_id)
            u = DiscoveryEngineRepository._imdb_row_to_unified(
                chosen, eztv_by_imdb, media_sources_by_imdb=media_sources_by_imdb
            ).model_dump()
            u["roulette_tag"] = tag
            roulette_items.append(u)

        recent_media_pool = [
            x
            for x in r_pool
            if (x.start_year or 0) >= 2023 and (x.has_eztv or x.imdb_id in media_imdb_set)
        ]
        affinity_pool = [
            x
            for x in r_pool
            if any(g in profile["genre_affinity"] for g in normalize_genre_tokens(x.genres))
        ]
        hidden_gem_pool = [
            x
            for x in r_pool
            if float(x.rating_score or 0.0) >= 7.8 and int(x.rating_votes or 0) <= 50000
        ]
        _pick_roulette(recent_media_pool, "Novidade c/ Mídia", "r1")
        _pick_roulette(affinity_pool, "Sua Afinidade", "r2")
        _pick_roulette(hidden_gem_pool, "Joia Oculta", "r3")

        # 3. 10 Smart Lists (allocated in ascending scarcity order -> 100% unique titles)
        enabled_lists: list[SmartListConfig] = sorted(
            [sl for sl in prefs.smart_lists if sl.enabled],
            key=lambda s: s.order,
        )
        list_pools: list[tuple[SmartListConfig, list[IMDbCatalogShow], dict[str, Any], str]] = []
        for sl in enabled_lists:
            pool_rows, cat_filter, title_ovr = cls._query_bucket_candidates(
                session,
                sl.category,
                profile=profile,
                media_imdb_set=media_imdb_set,
                only_with_media=sl.only_with_media,
                pool_limit=380,
            )
            list_pools.append((sl, pool_rows, cat_filter, title_ovr))

        # Sort by scarcity (smallest candidate pool reserves unique IDs first)
        scarcity_sorted = sorted(list_pools, key=lambda tup: len(tup[1]))
        built_by_id: dict[str, dict[str, Any]] = {}

        for sl, pool_rows, cat_filter, title_ovr in scarcity_sorted:
            eff_var = (
                sl.variance_override
                if sl.variance_override is not None
                else prefs.discovery_variance_pct
            )
            ranked = sorted(
                pool_rows,
                key=lambda r: cls._score_row(
                    r,
                    media_sources_by_imdb=media_sources_by_imdb,
                    eztv_by_imdb=eztv_by_imdb,
                    profile=profile,
                    impressions=impressions,
                    variance_pct=eff_var,
                    session_seed=session_seed,
                    list_id=sl.id,
                    sort_by=sl.sort_by,
                ),
                reverse=True,
            )
            chosen_rows: list[IMDbCatalogShow] = []
            for r in ranked:
                if r.imdb_id in seen_global:
                    continue
                seen_global.add(r.imdb_id)
                chosen_rows.append(r)
                if len(chosen_rows) >= sl.limit:
                    break

            built_by_id[sl.id] = {
                "id": sl.id,
                "title": title_ovr or sl.title,
                "category": sl.category,
                "limit": sl.limit,
                "sort_by": sl.sort_by,
                "only_with_media": sl.only_with_media,
                "catalog_filter": cat_filter,
                "items": [
                    DiscoveryEngineRepository._imdb_row_to_unified(
                        r, eztv_by_imdb, media_sources_by_imdb=media_sources_by_imdb
                    ).model_dump()
                    for r in chosen_rows
                ],
            }

        ordered_lists = [built_by_id[sl.id] for sl in enabled_lists if sl.id in built_by_id]
        dynamic_shortcuts = [
            {
                "id": f"dyn_genre_{idx}",
                "label": f"Para Você: {g}",
                "filters": {"genresAny": [g], "minRating": 7.0},
            }
            for idx, g in enumerate(profile.get("top_genres", [])[:3])
        ]

        return {
            "hero_pool": hero_pool,
            "roulette": roulette_items,
            "smart_lists": ordered_lists,
            "dynamic_shortcuts": dynamic_shortcuts,
            "stats": {
                "unique_titles": len(seen_global),
                "lists_count": len(ordered_lists),
                "variance_pct": prefs.discovery_variance_pct,
                "active_impressions": len(impressions),
            },
        }
