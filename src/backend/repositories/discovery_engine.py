"""Advanced Discovery Engine repository for filtering, facets, and similarity (ADR-008)."""

from __future__ import annotations

import difflib
import json
import math
import re
import unicodedata
from typing import Any, Optional

from sqlalchemy import literal_column, text
from sqlmodel import Session, col, func, or_, select

from src.backend.core.cache import discovery_cache
from src.backend.core.canonical_taxonomy import (
    ALL_CANONICAL_GENRES,
    ALL_CANONICAL_PROVIDERS,
    DATA_SOURCE_DEFINITIONS,
    WORK_TYPE_KEYS,
    expand_genre_synonyms,
    expand_provider_aliases,
    merge_canonical_genres,
    merge_canonical_providers,
    normalize_status_label,
)
from src.backend.core.content_filters import (
    build_foreign_sql_clause,
    build_mood_sql_clause,
    build_parental_sql_clause,
)
from src.backend.models.catalog_domain import (
    DataProvenance,
    ExternalIdentifier,
    IMDbCatalogShow,
    IMDbEpisodeCatalog,
    MediaWork,
    PersonRecord,
    ReleaseCalendarEvent,
    StreamingAvailability,
    WorkCredit,
    WorkRelation,
)
from src.backend.models.db import CatalogShow, ShowRecord
from src.backend.models.eztv_db import EZTVEpisodeCatalog, EZTVShow
from src.backend.models.sources_db import ExternalRelease
from src.backend.models.unified import UnifiedEpisode, UnifiedSeason, UnifiedShow
from src.backend.services.entity_resolution import EntityResolutionService

_SEARCH_STOPWORDS: set[str] = {
    "de",
    "do",
    "da",
    "dos",
    "das",
    "um",
    "uma",
    "os",
    "as",
    "o",
    "a",
    "e",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "por",
    "com",
    "the",
    "of",
    "in",
    "to",
    "and",
    "an",
    "on",
    "at",
    "by",
    "for",
}

_LEADING_ARTICLES: tuple[str, ...] = (
    "the ",
    "a ",
    "an ",
    "o ",
    "os ",
    "as ",
    "um ",
    "uma ",
)


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

    @staticmethod
    def _normalize_search_text(raw: Optional[str]) -> str:
        """Accent-insensitive, lowercase, alphanumeric normalization for bilingual PT/EN search."""
        if not raw:
            return ""
        folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
        folded = folded.lower().replace("&", " and ")
        folded = re.sub(r"[^a-z0-9\s]", " ", folded)
        return re.sub(r"\s+", " ", folded).strip()

    @classmethod
    def _strip_leading_article(cls, norm_text: str) -> str:
        for art in _LEADING_ARTICLES:
            if norm_text.startswith(art) and len(norm_text) > len(art):
                return norm_text[len(art) :].strip()
        return norm_text

    @classmethod
    def _expand_bilingual_genre_terms(cls, raw_genre: str) -> list[str]:
        return expand_genre_synonyms(raw_genre)

    @staticmethod
    def _csv_token_in(column: Any, token: str) -> Any:
        """Exact CSV token match preventing false substring hits (e.g. Ação vs Animação)."""
        normalized_col = "," + func.replace(func.coalesce(column, ""), ", ", ",") + ","
        return normalized_col.ilike(f"%,{token},%")

    @classmethod
    def score_title_pair_relevance(
        cls,
        q_norm: str,
        q_core: str,
        q_tokens: list[str],
        titles: list[Optional[str]],
        credit_blob: str,
        votes: int,
        rating: float,
    ) -> float:
        """Compute composite bilingual relevance score prioritizing exact and similar matches."""
        if not q_norm:
            return 0.0

        norm_titles = [cls._normalize_search_text(t) for t in titles if t]
        norm_titles = [t for t in norm_titles if t]
        if not norm_titles:
            return 0.0

        core_titles = [cls._strip_leading_article(t) for t in norm_titles]
        combined_title_tokens = set(" ".join(norm_titles).split())

        best_tier = 0.0
        best_sim = 0.0

        for idx, t in enumerate(norm_titles):
            t_core = core_titles[idx]
            # Tier 1: Exact match (with or without leading article in PT-BR or EN-US)
            if t == q_norm or (q_core and t_core == q_core):
                best_tier = max(best_tier, 1000.0)
            # Tier 2: Prefix / franchise root match ("matrix" -> "matrix reloaded")
            elif (
                t.startswith(q_norm + " ")
                or (q_core and t_core.startswith(q_core + " "))
                or t.startswith(q_norm)
            ):
                compactness = 120.0 * (len(q_core or q_norm) / max(len(t_core or t), 1))
                best_tier = max(best_tier, 650.0 + compactness)
            # Tier 3: Contiguous whole-word phrase match inside title
            elif f" {q_norm} " in f" {t} " or (q_core and f" {q_core} " in f" {t_core} "):
                compactness = 80.0 * (len(q_core or q_norm) / max(len(t_core or t), 1))
                best_tier = max(best_tier, 480.0 + compactness)

            sim = difflib.SequenceMatcher(None, q_core or q_norm, t_core or t).ratio()
            if sim > best_sim:
                best_sim = sim

        # Tier 4: All meaningful tokens present across PT-BR / EN-US titles
        if best_tier < 450.0 and q_tokens:
            matched_tokens = sum(
                1
                for tok in q_tokens
                if any(w == tok or w.startswith(tok) for w in combined_title_tokens)
            )
            if matched_tokens == len(q_tokens):
                best_tier = max(best_tier, 360.0)
            elif matched_tokens > 0:
                best_tier = max(best_tier, 180.0 * (matched_tokens / len(q_tokens)))

        # Tier 5: Director / creator / cast match
        if best_tier < 300.0 and credit_blob:
            norm_credits = cls._normalize_search_text(credit_blob)
            if q_norm in norm_credits:
                best_tier = max(best_tier, 240.0)

        similarity_bonus = best_sim * 200.0
        popularity_bonus = math.log10(max(votes, 1) + 1) * 24.0
        rating_bonus = max(rating, 0.0) * 2.5
        return best_tier + similarity_bonus + popularity_bonus + rating_bonus

    @classmethod
    def score_imdb_show_relevance(cls, row: IMDbCatalogShow, raw_query: str) -> float:
        """Score an IMDbCatalogShow against a query across PT-BR, English, and Original titles."""
        q_norm = cls._normalize_search_text(raw_query)
        q_core = cls._strip_leading_article(q_norm)
        raw_tokens = q_norm.split()
        meaningful_tokens = [t for t in raw_tokens if t not in _SEARCH_STOPWORDS and len(t) >= 2]
        q_tokens = meaningful_tokens or raw_tokens
        if row.imdb_id and row.imdb_id.lower() == raw_query.strip().lower():
            return 2500.0
        credit_blob = " ".join(filter(None, [row.directors, row.creators, row.cast_members]))
        return cls.score_title_pair_relevance(
            q_norm=q_norm,
            q_core=q_core,
            q_tokens=q_tokens,
            titles=[row.title_ptbr, row.primary_title, row.original_title],
            credit_blob=credit_blob,
            votes=int(row.rating_votes or 0),
            rating=float(row.rating_score or 0.0),
        )

    @classmethod
    def _fts_search_imdb_ids(
        cls, session: Session, raw_query: str, limit: int = 250
    ) -> Optional[list[str]]:
        """Retrieve candidate imdb_ids via FTS5 (accent-insensitive PT/EN) in <3ms."""
        clean = raw_query.strip()
        if not clean:
            return None
        if re.match(r"^tt\d+$", clean, re.IGNORECASE):
            return [EntityResolutionService.normalize_imdb_id(clean)]

        q_norm = cls._normalize_search_text(clean)
        all_tokens = [t for t in q_norm.split() if t]
        if not all_tokens:
            return None

        meaningful = [t for t in all_tokens if t not in _SEARCH_STOPWORDS and len(t) >= 3]
        active_tokens = meaningful if meaningful else all_tokens

        def _fmt_tok(tok: str) -> str:
            return f'"{tok}"*' if len(tok) >= 3 else f'"{tok}"'

        and_expr = " AND ".join(_fmt_tok(t) for t in active_tokens)
        title_and_expr = f"{{primary_title original_title title_ptbr}} : ({and_expr})"

        seen: dict[str, None] = {}
        try:
            # Stage 1: Title-focused FTS5 match ordered by vote popularity
            rows_s1 = session.exec(
                text(
                    """
                    SELECT s.imdb_id
                    FROM shows_fts f
                    JOIN shows s ON s.rowid = f.rowid
                    WHERE shows_fts MATCH :expr
                    ORDER BY s.rating_votes DESC
                    LIMIT :lim
                    """
                ),
                params={"expr": title_and_expr, "lim": limit},
            ).all()
            for r in rows_s1:
                if r[0]:
                    seen[str(r[0])] = None

            # Stage 2: Full-column FTS5 match (includes directors, creators, cast)
            if len(seen) < 40:
                rows_s2 = session.exec(
                    text(
                        """
                        SELECT s.imdb_id
                        FROM shows_fts f
                        JOIN shows s ON s.rowid = f.rowid
                        WHERE shows_fts MATCH :expr
                        ORDER BY s.rating_votes DESC
                        LIMIT :lim
                        """
                    ),
                    params={"expr": and_expr, "lim": 100},
                ).all()
                for r in rows_s2:
                    if r[0]:
                        seen[str(r[0])] = None

            # Stage 3: Relaxed OR match across meaningful tokens for partial/similarity recall
            if len(seen) < 15 and len(active_tokens) >= 2:
                or_expr = " OR ".join(_fmt_tok(t) for t in active_tokens[:5])
                title_or_expr = f"{{primary_title original_title title_ptbr}} : ({or_expr})"
                rows_s3 = session.exec(
                    text(
                        """
                        SELECT s.imdb_id
                        FROM shows_fts f
                        JOIN shows s ON s.rowid = f.rowid
                        WHERE shows_fts MATCH :expr
                        ORDER BY bm25(shows_fts, 1.0, 10.0, 8.0, 10.0, 1.0, 1.0, 1.0)
                        LIMIT 80
                        """
                    ),
                    params={"expr": title_or_expr},
                ).all()
                for r in rows_s3:
                    if r[0]:
                        seen[str(r[0])] = None
        except Exception:
            return None

        return list(seen.keys()) if seen else None

    @classmethod
    def _fts_person_imdb_ids(
        cls, session: Session, person_query: str, limit: int = 500
    ) -> Optional[list[str]]:
        """Retrieve imdb_ids of works matching a person in directors/creators/cast via FTS5."""
        q_norm = cls._normalize_search_text(person_query)
        tokens = [t for t in q_norm.split() if len(t) >= 2]
        if not tokens:
            return None
        and_expr = " AND ".join(f'"{t}"*' if len(t) >= 3 else f'"{t}"' for t in tokens)
        person_expr = f"{{directors creators cast_members}} : ({and_expr})"
        try:
            rows = session.exec(
                text(
                    """
                    SELECT s.imdb_id
                    FROM shows_fts f
                    JOIN shows s ON s.rowid = f.rowid
                    WHERE shows_fts MATCH :expr
                    ORDER BY s.rating_votes DESC
                    LIMIT :lim
                    """
                ),
                params={"expr": person_expr, "lim": limit},
            ).all()
            ids = [str(r[0]) for r in rows if r[0]]
            return ids if ids else None
        except Exception:
            return None

    @classmethod
    def _has_imdb_catalog(cls, session: Session) -> bool:
        """Check in O(1) (via cached probe) whether IMDb universal catalog is populated."""
        scope = discovery_cache.session_scope(session)

        def _probe() -> bool:
            try:
                return session.exec(select(IMDbCatalogShow.imdb_id).limit(1)).first() is not None
            except Exception:
                return False

        return discovery_cache.get_or_set(scope, "has_imdb_catalog", "flag", _probe, ttl=15.0)

    @staticmethod
    def _map_imdb_work_type(title_type: Optional[str]) -> str:
        mapping = {
            "movie": "movie",
            "tvMovie": "movie",
            "tvSeries": "tv_show",
            "tvMiniSeries": "mini_series",
        }
        return mapping.get(title_type or "", "tv_show")

    @staticmethod
    def _expand_work_type_filter(type_tokens: list[str]) -> list[str]:
        mapped: list[str] = []
        canonical = {
            "tvmovie": "tvMovie",
            "tvseries": "tvSeries",
            "tvminiseries": "tvMiniSeries",
        }
        for t in type_tokens:
            if t == "movie":
                mapped.extend(["movie", "tvMovie"])
            elif t == "tv_show":
                mapped.append("tvSeries")
            elif t == "mini_series":
                mapped.append("tvMiniSeries")
            elif t in canonical:
                mapped.append(canonical[t])
            else:
                mapped.append(t)
        return mapped

    @staticmethod
    def _derive_imdb_num(row: IMDbCatalogShow) -> int:
        if row.imdb_num is not None:
            return int(row.imdb_num)
        digits = (row.imdb_id or "").lower().lstrip("t")
        return int(digits) if digits.isdigit() else 0

    @staticmethod
    def _build_sources_media_index(
        eztv_session: Optional[Session],
    ) -> dict[str, list[str]]:
        """Lazy import wrapper returning normalized_imdb_id -> source_keys from sources.db."""
        from src.backend.services.sources_registry import SourcesRegistryService

        return SourcesRegistryService.get_media_index_by_imdb(eztv_session)

    @classmethod
    def _serialize_imdb_summary(
        cls,
        row: IMDbCatalogShow,
        saved_library_map: dict[str, str],
        eztv_by_imdb: dict[str, int],
        p2p_seeds_by_imdb: dict[str, int],
        media_sources_by_imdb: Optional[dict[str, list[str]]] = None,
    ) -> dict[str, Any]:
        norm_imdb = EntityResolutionService.normalize_imdb_id(row.imdb_id)
        genres = merge_canonical_genres(row.genres_ptbr, row.genres)
        providers = merge_canonical_providers(
            row.streaming_providers, row.network, keep_unknown=True
        )
        directors = cls._parse_csv(row.directors)[:4]
        top_cast = cls._parse_csv(row.cast_members)[:4]
        eztv_show_id = (
            row.eztv_id
            if row.has_eztv and row.eztv_id
            else (eztv_by_imdb.get(norm_imdb) if norm_imdb else None)
        )
        eztv_available = bool(row.has_eztv or eztv_show_id)
        sources_set: set[str] = (
            set(media_sources_by_imdb.get(norm_imdb, []))
            if (media_sources_by_imdb and norm_imdb)
            else set()
        )
        if eztv_available:
            sources_set.add("eztv")
        media_sources = sorted(sources_set)
        has_media = bool(media_sources)
        rating = float(row.rating_score or 0.0)
        votes = int(row.rating_votes or 0)
        default_status = (
            "Returning Series" if row.title_type == "tvSeries" and not row.end_year else "Released"
        )
        display_title = row.title_ptbr or row.primary_title
        orig_title = (
            row.primary_title
            if row.title_ptbr and row.title_ptbr.lower() != row.primary_title.lower()
            else (row.original_title or row.primary_title)
        )
        return {
            "id": cls._derive_imdb_num(row),
            "work_type": cls._map_imdb_work_type(row.title_type),
            "title": display_title,
            "original_title": orig_title,
            "overview": row.synopsis_ptbr or row.synopsis or "",
            "tagline": row.tagline,
            "release_date": row.release_date or (str(row.start_year) if row.start_year else None),
            "release_year": row.start_year,
            "runtime_minutes": row.runtime_minutes,
            "status": row.status or default_status,
            "origin_country": (cls._parse_csv(row.countries) or ["US"])[0],
            "original_language": (cls._parse_csv(row.languages) or ["en"])[0],
            "poster_url": row.poster_url,
            "backdrop_url": row.backdrop_url,
            "canonical_rating": rating,
            "rating_source": "imdb",
            "ratings_breakdown": {"imdb": {"rating": rating, "votes": votes}} if rating > 0 else {},
            "popularity_score": float(votes),
            "vote_count": votes,
            "seasons_count": int(row.total_seasons or 0),
            "episodes_count": 0,
            "network_or_studio": row.network,
            "collection_name": None,
            "genres": genres,
            "directors": directors,
            "top_cast": top_cast,
            "streaming_providers": providers,
            "imdb_id": norm_imdb or row.imdb_id,
            "tmdb_id": row.tmdb_id,
            "tvmaze_id": row.tvmaze_id,
            "wikidata_id": None,
            "user_library_status": saved_library_map.get(norm_imdb) if norm_imdb else None,
            "p2p_max_seeds": p2p_seeds_by_imdb.get(norm_imdb, 0) if norm_imdb else 0,
            "eztv_available": eztv_available,
            "eztv_show_id": eztv_show_id,
            "has_media": has_media,
            "media_sources": media_sources,
            "sources_count": len(media_sources),
        }

    @classmethod
    def _active_p2p_imdb_set(cls, eztv_session: Optional[Session]) -> set[str]:
        """Return normalized IMDb IDs from sources.db with active P2P seeds (max_seeds > 0)."""
        if eztv_session is None:
            return set()
        scope = discovery_cache.session_scope(eztv_session)

        def _fetch() -> set[str]:
            result: set[str] = set()
            try:
                rows = eztv_session.exec(
                    select(CatalogShow.imdb_id).where(CatalogShow.max_seeds > 0)
                ).all()
                for raw_id in rows:
                    if raw_id:
                        norm = EntityResolutionService.normalize_imdb_id(raw_id)
                        if norm:
                            result.add(norm)
                ext_rows = eztv_session.exec(
                    select(ExternalRelease.imdb_id).where(
                        col(ExternalRelease.imdb_id).is_not(None),
                        ExternalRelease.seeds > 0,
                    )
                ).all()
                for raw_id in ext_rows:
                    if raw_id:
                        norm = EntityResolutionService.normalize_imdb_id(raw_id)
                        if norm:
                            result.add(norm)
            except Exception:
                pass
            return result

        return discovery_cache.get_or_set(scope, "active_p2p_imdbs", "all", _fetch, ttl=60.0)

    @classmethod
    def _aggregate_imdb_facet_rows(
        cls,
        rows: list[Any],
        active_p2p_imdbs: Optional[set[str]] = None,
        saved_imdbs: Optional[set[str]] = None,
        scale: float = 1.0,
    ) -> dict[str, list[dict[str, Any]]]:
        """Aggregate exact or scaled multi-dimensional facets over IMDbCatalogShow rows."""
        wt: dict[str, int] = {k: 0 for k in WORK_TYPE_KEYS}
        ds: dict[str, int] = {k: 0 for k, _ in DATA_SOURCE_DEFINITIONS}
        fg: dict[str, int] = {k: 0 for k in ALL_CANONICAL_GENRES}
        fp: dict[str, int] = {k: 0 for k in ALL_CANONICAL_PROVIDERS}
        fd: dict[str, int] = {}
        fs: dict[str, int] = {}
        fc: dict[str, int] = {}

        p2p_set = active_p2p_imdbs or set()
        saved_set = saved_imdbs or set()

        for (
            tt,
            has_ez,
            tmdb_id,
            tvmaze_id,
            has_ptbr,
            has_yt,
            g_pt,
            g_en,
            sp,
            net,
            yr,
            st,
            ctry,
            imdb_id,
        ) in rows:
            # 1. Title-type & genre-backed Work Types
            if tt in ("movie", "tvMovie"):
                wt["movie"] += 1
            if tt == "tvMovie":
                wt["tv_movie"] += 1
            elif tt == "tvSeries":
                wt["tv_show"] += 1
            elif tt == "tvMiniSeries":
                wt["mini_series"] += 1

            canon_genres = merge_canonical_genres(g_pt, g_en)
            for g in canon_genres:
                fg[g] = fg.get(g, 0) + 1

            g_set = set(canon_genres)
            if "Documentário" in g_set:
                wt["documentary"] += 1
            if "Animação" in g_set:
                wt["animation"] += 1
            if g_set & {"Reality-TV", "Talk-Show", "Game-Show"}:
                wt["special"] += 1
            if "Curta-Metragem" in g_set:
                wt["short"] += 1

            # 2. Data Sources & Catalog Provenance
            norm_imdb = EntityResolutionService.normalize_imdb_id(imdb_id) if imdb_id else ""
            is_real_imdb = bool(
                norm_imdb and not (norm_imdb.startswith("tt99") and len(norm_imdb) >= 12)
            )
            if is_real_imdb:
                ds["imdb"] += 1
            if has_ez:
                ds["eztv"] += 1
            if has_ez or (norm_imdb and norm_imdb in p2p_set):
                ds["p2p_active"] += 1
            if tmdb_id is not None:
                ds["tmdb"] += 1
            if has_ptbr:
                ds["ptbr"] += 1
            if has_yt:
                ds["youtube_trailer"] += 1
            if tvmaze_id is not None:
                ds["tvmaze"] += 1
            if norm_imdb and norm_imdb in saved_set:
                ds["personal_library"] += 1

            # 3. Canonical Streaming Providers & Networks
            for p in merge_canonical_providers(sp, net, keep_unknown=False):
                fp[p] = fp.get(p, 0) + 1

            # 4. Decades, Normalized Status, Countries
            if yr:
                dec = f"{(int(yr) // 10) * 10}s"
                fd[dec] = fd.get(dec, 0) + 1
            norm_st = normalize_status_label(st)
            if norm_st:
                fs[norm_st] = fs.get(norm_st, 0) + 1
            for c in cls._parse_csv(ctry)[:1]:
                fc[c] = fc.get(c, 0) + 1

        def _scale_buckets(
            counts: dict[str, int],
            fixed_order: Optional[tuple[str, ...]] = None,
            sort_desc: bool = True,
        ) -> list[dict[str, Any]]:
            if scale != 1.0:
                scaled = {
                    k: (max(1, int(round(v * scale))) if v > 0 else 0) for k, v in counts.items()
                }
            else:
                scaled = counts
            items = [{"key": k, "count": v} for k, v in scaled.items()]
            if sort_desc:
                order_idx = {k: i for i, k in enumerate(fixed_order)} if fixed_order else {}
                items.sort(key=lambda x: (-x["count"], order_idx.get(x["key"], 999), x["key"]))
            return items

        return {
            "work_types": _scale_buckets(wt, fixed_order=WORK_TYPE_KEYS),
            "data_sources": _scale_buckets(
                ds, fixed_order=tuple(k for k, _ in DATA_SOURCE_DEFINITIONS)
            ),
            "genres": _scale_buckets(fg, fixed_order=ALL_CANONICAL_GENRES),
            "streaming_providers": _scale_buckets(fp, fixed_order=ALL_CANONICAL_PROVIDERS),
            "decades": [
                {"key": k, "count": (max(1, int(round(v * scale))) if scale != 1.0 else v)}
                for k, v in sorted(fd.items(), key=lambda x: x[0], reverse=True)[:14]
            ],
            "statuses": _scale_buckets(fs),
            "countries": _scale_buckets(fc)[:15],
        }

    @classmethod
    def refresh_global_facets_cache(
        cls,
        session: Session,
        eztv_session: Optional[Session] = None,
        persist_to_sync_state: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        """Compute exact global facets over all rows in shows and store in sync_state."""
        rows = list(
            session.exec(
                text(
                    """
                    SELECT
                        title_type,
                        has_eztv,
                        tmdb_id,
                        tvmaze_id,
                        (synopsis_ptbr IS NOT NULL AND synopsis_ptbr != ''),
                        (trailer_url IS NOT NULL AND trailer_url != ''),
                        genres_ptbr,
                        genres,
                        streaming_providers,
                        network,
                        start_year,
                        status,
                        countries,
                        imdb_id
                    FROM shows
                    """
                )
            ).all()
        )
        p2p_set = cls._active_p2p_imdb_set(eztv_session)
        facets = cls._aggregate_imdb_facet_rows(rows, active_p2p_imdbs=p2p_set)

        if persist_to_sync_state and len(rows) > 0:
            try:
                payload = json.dumps(
                    {"total_rows": len(rows), "facets": facets}, ensure_ascii=False
                )
                session.exec(
                    text(
                        """
                        INSERT INTO sync_state (key, value, updated_at)
                        VALUES ('global_facets_v2', :val, CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = CURRENT_TIMESTAMP
                        """
                    ),
                    params={"val": payload},
                )
                session.commit()
            except Exception:
                pass

        discovery_cache.invalidate()
        return facets

    @classmethod
    def _build_imdb_facets(
        cls,
        session: Session,
        base_filters: list[Any],
        filter_sig: Any = None,
        total_matches: int = 0,
        eztv_session: Optional[Session] = None,
        saved_imdbs: Optional[set[str]] = None,
        active_p2p_imdbs: Optional[set[str]] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Compute exact or scaled SQL-backed facets across formats, sources, genres & providers."""
        scope = discovery_cache.session_scope(session)
        saved_set = saved_imdbs or set()

        def _inject_dynamic_counts(
            facets_obj: dict[str, list[dict[str, Any]]], lib_count: int
        ) -> dict[str, list[dict[str, Any]]]:
            media_idx = cls._build_sources_media_index(eztv_session)
            src_counts: dict[str, int] = {}
            for src_list in media_idx.values():
                for sk in src_list:
                    src_counts[sk] = src_counts.get(sk, 0) + 1

            out = {k: list(v) for k, v in facets_obj.items()}
            ds_list = []
            seen_keys: set[str] = set()
            static_core_keys = {
                "imdb",
                "tmdb",
                "tvmaze",
                "ptbr",
                "youtube_trailer",
                "personal_library",
                "p2p_active",
                "eztv",
            }
            for item in out.get("data_sources", []):
                key = item["key"]
                seen_keys.add(key)
                if key == "personal_library":
                    ds_list.append({"key": "personal_library", "count": lib_count})
                elif key not in static_core_keys and not base_filters:
                    ds_list.append(
                        {"key": key, "count": max(item["count"], src_counts.get(key, 0))}
                    )
                else:
                    ds_list.append(item)
            for dyn_key, dyn_cnt in sorted(src_counts.items()):
                if dyn_key not in seen_keys:
                    ds_list.append({"key": dyn_key, "count": dyn_cnt})
                    seen_keys.add(dyn_key)
            if "personal_library" not in seen_keys:
                ds_list.append({"key": "personal_library", "count": lib_count})
            out["data_sources"] = ds_list
            return out

        if not base_filters:

            def _compute_global() -> dict[str, list[dict[str, Any]]]:
                current_total = int(
                    session.exec(select(func.count(IMDbCatalogShow.imdb_id))).one() or 0
                )
                try:
                    cached_row = session.exec(
                        text("SELECT value FROM sync_state WHERE key = 'global_facets_v2'")
                    ).first()
                    if cached_row and cached_row[0]:
                        parsed = json.loads(cached_row[0])
                        if int(parsed.get("total_rows", -1)) == current_total:
                            return parsed["facets"]
                except Exception:
                    pass
                return cls.refresh_global_facets_cache(
                    session,
                    eztv_session=eztv_session,
                    persist_to_sync_state=(current_total >= 100),
                )

            base_global = discovery_cache.get_or_set(
                scope, "imdb_facets_global", "default", _compute_global, ttl=120.0
            )
            return _inject_dynamic_counts(base_global, len(saved_set))

        def _compute_filtered() -> dict[str, list[dict[str, Any]]]:
            if total_matches == 0:
                return cls._aggregate_imdb_facet_rows([], active_p2p_imdbs, saved_set)

            stmt = select(
                IMDbCatalogShow.title_type,
                IMDbCatalogShow.has_eztv,
                IMDbCatalogShow.tmdb_id,
                IMDbCatalogShow.tvmaze_id,
                (
                    col(IMDbCatalogShow.synopsis_ptbr).is_not(None)
                    & (col(IMDbCatalogShow.synopsis_ptbr) != "")
                ),
                (
                    col(IMDbCatalogShow.trailer_url).is_not(None)
                    & (col(IMDbCatalogShow.trailer_url) != "")
                ),
                IMDbCatalogShow.genres_ptbr,
                IMDbCatalogShow.genres,
                IMDbCatalogShow.streaming_providers,
                IMDbCatalogShow.network,
                IMDbCatalogShow.start_year,
                IMDbCatalogShow.status,
                IMDbCatalogShow.countries,
                IMDbCatalogShow.imdb_id,
            )
            for cond in base_filters:
                stmt = stmt.where(cond)

            max_exact = 60000
            if total_matches > max_exact:
                sample = list(session.exec(stmt.limit(45000)).all())
                scale = total_matches / max(len(sample), 1)
            else:
                sample = list(session.exec(stmt).all())
                scale = 1.0

            return cls._aggregate_imdb_facet_rows(
                sample,
                active_p2p_imdbs=active_p2p_imdbs,
                saved_imdbs=saved_set,
                scale=scale,
            )

        if filter_sig is not None:
            return discovery_cache.get_or_set(
                scope, "imdb_facets_filtered", filter_sig, _compute_filtered, ttl=60.0
            )
        return _compute_filtered()

    @classmethod
    def _query_imdb_catalog_sql(
        cls,
        session: Session,
        eztv_session: Optional[Session],
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
        country: Optional[str] = None,
        language: Optional[str] = None,
        person_query: Optional[str] = None,
        role_type: Optional[str] = None,
        min_seasons: Optional[int] = None,
        exclude_watched: bool = False,
        only_with_p2p: bool = False,
        data_sources: Optional[str] = None,
        sort_by: str = "rating",
        page: int = 1,
        page_size: int = 24,
    ) -> dict[str, Any]:
        """Execute 100% SQL Pushdown filtering, ordering, and pagination over 279k+ IMDb titles."""
        from src.backend.repositories.preferences import ExplorePreferencesRepository

        filters: list[Any] = []
        prefs = ExplorePreferencesRepository.get_preferences(session)
        if not language:
            f_clause = build_foreign_sql_clause(prefs.foreign_titles_mode)
            if f_clause is not None:
                filters.append(f_clause)
        p_clause = build_parental_sql_clause(prefs.parental_control_enabled)
        if p_clause is not None:
            filters.append(p_clause)
        m_clause = build_mood_sql_clause(prefs.mood_mode)
        if m_clause is not None:
            filters.append(m_clause)

        active_p2p_imdbs = cls._active_p2p_imdb_set(eztv_session)
        media_sources_by_imdb = cls._build_sources_media_index(eztv_session)

        saved_library_map: dict[str, str] = {}
        watched_imdbs: list[str] = []
        for sr in session.exec(select(ShowRecord)).all():
            if sr.imdb_id:
                norm = EntityResolutionService.normalize_imdb_id(sr.imdb_id)
                if norm:
                    saved_library_map[norm] = sr.user_status
                    if sr.user_status in ("completed", "watching"):
                        watched_imdbs.append(norm)

        if work_types:
            wt_clauses: list[Any] = []
            direct_types: list[str] = []
            for raw_t in [t.lower() for t in cls._parse_csv(work_types)]:
                if raw_t == "movie":
                    direct_types.extend(["movie", "tvMovie"])
                elif raw_t == "tv_show":
                    direct_types.append("tvSeries")
                elif raw_t == "mini_series":
                    direct_types.append("tvMiniSeries")
                elif raw_t in ("tv_movie", "tvmovie"):
                    direct_types.append("tvMovie")
                elif raw_t == "documentary":
                    wt_clauses.append(
                        cls._csv_token_in(IMDbCatalogShow.genres_ptbr, "Documentário")
                        | cls._csv_token_in(IMDbCatalogShow.genres, "Documentary")
                    )
                elif raw_t == "animation":
                    wt_clauses.append(
                        cls._csv_token_in(IMDbCatalogShow.genres_ptbr, "Animação")
                        | cls._csv_token_in(IMDbCatalogShow.genres, "Animation")
                    )
                elif raw_t == "special":
                    wt_clauses.append(
                        or_(
                            *(
                                cls._csv_token_in(IMDbCatalogShow.genres_ptbr, tok)
                                | cls._csv_token_in(IMDbCatalogShow.genres, tok)
                                for tok in ("Reality-TV", "Talk-Show", "Game-Show", "Talk")
                            )
                        )
                    )
                elif raw_t == "short":
                    wt_clauses.append(
                        cls._csv_token_in(IMDbCatalogShow.genres_ptbr, "Curta-Metragem")
                        | cls._csv_token_in(IMDbCatalogShow.genres, "Short")
                    )
                else:
                    direct_types.extend(cls._expand_work_type_filter([raw_t]))
            if direct_types:
                wt_clauses.append(
                    col(IMDbCatalogShow.title_type).in_(list(dict.fromkeys(direct_types)))
                )
            if wt_clauses:
                filters.append(or_(*wt_clauses))

        if year_from is not None:
            filters.append(col(IMDbCatalogShow.start_year) >= year_from)
        if year_to is not None:
            filters.append(col(IMDbCatalogShow.start_year) <= year_to)
        if min_rating is not None:
            filters.append(col(IMDbCatalogShow.rating_score) >= min_rating)
        if max_rating is not None:
            filters.append(col(IMDbCatalogShow.rating_score) <= max_rating)
        if min_runtime is not None:
            filters.append(col(IMDbCatalogShow.runtime_minutes) >= min_runtime)
        if max_runtime is not None:
            filters.append(col(IMDbCatalogShow.runtime_minutes) <= max_runtime)
        if min_seasons is not None:
            filters.append(col(IMDbCatalogShow.total_seasons) >= min_seasons)

        if status:
            st_clauses: list[Any] = []
            for raw_st in cls._parse_csv(status):
                canon_st = normalize_status_label(raw_st) or raw_st
                if canon_st == "Running":
                    st_clauses.extend(
                        [
                            col(IMDbCatalogShow.status).ilike(pat)
                            for pat in (
                                "%Running%",
                                "%Returning Series%",
                                "%Airing%",
                                "%In Production%",
                            )
                        ]
                    )
                elif canon_st == "Ended":
                    st_clauses.extend(
                        [
                            col(IMDbCatalogShow.status).ilike(pat)
                            for pat in ("%Ended%", "%Completed%")
                        ]
                    )
                elif canon_st == "To Be Determined":
                    st_clauses.extend(
                        [
                            col(IMDbCatalogShow.status).ilike(pat)
                            for pat in ("%To Be Determined%", "%TBD%")
                        ]
                    )
                elif canon_st == "Canceled":
                    st_clauses.extend(
                        [
                            col(IMDbCatalogShow.status).ilike(pat)
                            for pat in ("%Canceled%", "%Cancelled%")
                        ]
                    )
                else:
                    st_clauses.append(col(IMDbCatalogShow.status).ilike(f"%{raw_st}%"))
            if st_clauses:
                filters.append(or_(*st_clauses))

        if country:
            c_clauses = [
                col(IMDbCatalogShow.countries).ilike(f"%{c}%") for c in cls._parse_csv(country)
            ]
            if c_clauses:
                filters.append(or_(*c_clauses))

        if language:
            l_clauses = [
                col(IMDbCatalogShow.languages).ilike(f"%{lg}%") for lg in cls._parse_csv(language)
            ]
            if l_clauses:
                filters.append(or_(*l_clauses))

        if streaming_providers:
            sp_clauses: list[Any] = []
            seen_sp_tokens: set[str] = set()
            for p in cls._parse_csv(streaming_providers):
                for al in expand_provider_aliases(p):
                    low = al.lower()
                    if low in seen_sp_tokens:
                        continue
                    seen_sp_tokens.add(low)
                    sp_clauses.append(
                        cls._csv_token_in(IMDbCatalogShow.streaming_providers, al)
                        | cls._csv_token_in(IMDbCatalogShow.network, al)
                    )
            if sp_clauses:
                filters.append(or_(*sp_clauses))

        def _genre_syn_clauses(raw_g: str) -> list[Any]:
            clauses: list[Any] = []
            seen_syn: set[str] = set()
            for syn in expand_genre_synonyms(raw_g):
                low = syn.lower()
                if low in seen_syn:
                    continue
                seen_syn.add(low)
                clauses.append(cls._csv_token_in(IMDbCatalogShow.genres_ptbr, syn))
                clauses.append(cls._csv_token_in(IMDbCatalogShow.genres, syn))
            return clauses

        if genres_any:
            g_any_clauses: list[Any] = []
            for g in cls._parse_csv(genres_any):
                g_any_clauses.extend(_genre_syn_clauses(g))
            if g_any_clauses:
                filters.append(or_(*g_any_clauses))

        if genres_all:
            for g in cls._parse_csv(genres_all):
                syn_clauses = _genre_syn_clauses(g)
                if syn_clauses:
                    filters.append(or_(*syn_clauses))

        if genres_not:
            for g in cls._parse_csv(genres_not):
                syn_clauses = _genre_syn_clauses(g)
                if syn_clauses:
                    filters.append(~or_(*syn_clauses))

        role_clean = (role_type or "").strip().lower()
        if person_query:
            pq_clean = person_query.strip()
            pq = f"%{pq_clean}%"
            if role_clean == "director":
                filters.append(col(IMDbCatalogShow.directors).ilike(pq))
            elif role_clean in ("creator", "writer"):
                filters.append(col(IMDbCatalogShow.creators).ilike(pq))
            elif role_clean == "actor":
                filters.append(col(IMDbCatalogShow.cast_members).ilike(pq))
            else:
                person_fts_ids = cls._fts_person_imdb_ids(session, pq_clean, limit=500)
                if person_fts_ids is not None:
                    filters.append(col(IMDbCatalogShow.imdb_id).in_(person_fts_ids))
                else:
                    filters.append(
                        col(IMDbCatalogShow.directors).ilike(pq)
                        | col(IMDbCatalogShow.creators).ilike(pq)
                        | col(IMDbCatalogShow.cast_members).ilike(pq)
                    )
        elif role_clean:
            if role_clean == "director":
                filters.append(
                    col(IMDbCatalogShow.directors).is_not(None)
                    & (col(IMDbCatalogShow.directors) != "")
                )
            elif role_clean in ("creator", "writer"):
                filters.append(
                    col(IMDbCatalogShow.creators).is_not(None)
                    & (col(IMDbCatalogShow.creators) != "")
                )
            elif role_clean == "actor":
                filters.append(
                    col(IMDbCatalogShow.cast_members).is_not(None)
                    & (col(IMDbCatalogShow.cast_members) != "")
                )

        def _imdb_in(ids: list[str] | set[str]) -> Any:
            id_list = list(ids)
            if len(id_list) <= 900:
                return col(IMDbCatalogShow.imdb_id).in_(id_list)
            subq = select(literal_column("value")).select_from(func.json_each(json.dumps(id_list)))
            return col(IMDbCatalogShow.imdb_id).in_(subq)

        if data_sources:
            for src_key in [s.lower() for s in cls._parse_csv(data_sources)]:
                if src_key == "eztv":
                    eztv_imdbs = [k for k, srcs in media_sources_by_imdb.items() if "eztv" in srcs]
                    if eztv_imdbs:
                        filters.append((col(IMDbCatalogShow.has_eztv) == 1) | _imdb_in(eztv_imdbs))
                    else:
                        filters.append(col(IMDbCatalogShow.has_eztv) == 1)
                elif src_key in ("media", "has_media"):
                    all_media_imdbs = list(media_sources_by_imdb.keys())
                    if all_media_imdbs:
                        filters.append(
                            (col(IMDbCatalogShow.has_eztv) == 1) | _imdb_in(all_media_imdbs)
                        )
                    else:
                        filters.append(col(IMDbCatalogShow.has_eztv) == 1)
                elif src_key not in (
                    "p2p_active",
                    "imdb",
                    "tmdb",
                    "tvmaze",
                    "ptbr",
                    "youtube_trailer",
                    "personal_library",
                ):
                    matched_imdbs = [
                        k for k, srcs in media_sources_by_imdb.items() if src_key in srcs
                    ]
                    if matched_imdbs:
                        filters.append(_imdb_in(matched_imdbs))
                    else:
                        filters.append(col(IMDbCatalogShow.imdb_id) == f"__empty_{src_key}__")
                elif src_key == "p2p_active":
                    if active_p2p_imdbs:
                        filters.append(
                            (col(IMDbCatalogShow.has_eztv) == 1) | _imdb_in(active_p2p_imdbs)
                        )
                    else:
                        filters.append(col(IMDbCatalogShow.has_eztv) == 1)
                elif src_key == "imdb":
                    synthetic_mask = col(IMDbCatalogShow.imdb_id).like("tt99%") & (
                        func.length(IMDbCatalogShow.imdb_id) >= 12
                    )
                    filters.append(col(IMDbCatalogShow.imdb_id).is_not(None) & (~synthetic_mask))
                elif src_key == "tmdb":
                    filters.append(col(IMDbCatalogShow.tmdb_id).is_not(None))
                elif src_key == "tvmaze":
                    filters.append(col(IMDbCatalogShow.tvmaze_id).is_not(None))
                elif src_key == "ptbr":
                    filters.append(
                        col(IMDbCatalogShow.synopsis_ptbr).is_not(None)
                        & (col(IMDbCatalogShow.synopsis_ptbr) != "")
                    )
                elif src_key == "youtube_trailer":
                    filters.append(
                        col(IMDbCatalogShow.trailer_url).is_not(None)
                        & (col(IMDbCatalogShow.trailer_url) != "")
                    )
                elif src_key == "personal_library":
                    if saved_library_map:
                        filters.append(_imdb_in(list(saved_library_map.keys())))
                    else:
                        filters.append(col(IMDbCatalogShow.imdb_id) == "__empty_library__")

        if only_with_p2p:
            if active_p2p_imdbs:
                filters.append((col(IMDbCatalogShow.has_eztv) == 1) | _imdb_in(active_p2p_imdbs))
            else:
                filters.append(col(IMDbCatalogShow.has_eztv) == 1)

        has_query = bool(q and q.strip())
        if has_query and q:
            qt = q.strip()
            fts_ids = cls._fts_search_imdb_ids(session, qt, limit=250)
            if fts_ids is not None:
                filters.append(col(IMDbCatalogShow.imdb_id).in_(fts_ids))
            else:
                filters.append(
                    col(IMDbCatalogShow.primary_title).ilike(f"%{qt}%")
                    | col(IMDbCatalogShow.original_title).ilike(f"%{qt}%")
                    | col(IMDbCatalogShow.title_ptbr).ilike(f"%{qt}%")
                    | col(IMDbCatalogShow.imdb_id).ilike(f"%{qt}%")
                )

        if exclude_watched and watched_imdbs:
            filters.append(~_imdb_in(watched_imdbs))

        scope = discovery_cache.session_scope(session)
        filter_sig = (
            q,
            work_types,
            genres_any,
            genres_all,
            genres_not,
            year_from,
            year_to,
            min_rating,
            max_rating,
            min_runtime,
            max_runtime,
            status,
            streaming_providers,
            country,
            language,
            person_query,
            role_type,
            min_seasons,
            exclude_watched,
            only_with_p2p,
            data_sources,
            len(watched_imdbs) if exclude_watched else 0,
            len(saved_library_map),
        )

        offset = (page - 1) * page_size

        # When a search query `q` is active and sort_by is relevance/rating (default),
        # score all candidate rows by bilingual PT/EN exact & similarity relevance!
        if has_query and q and sort_by in ("rating", "relevance", ""):
            cand_stmt = select(IMDbCatalogShow)
            for cond in filters:
                cand_stmt = cand_stmt.where(cond)
            candidates = list(session.exec(cand_stmt.limit(250)).all())
            candidates.sort(
                key=lambda row: cls.score_imdb_show_relevance(row, q),
                reverse=True,
            )
            total = len(candidates)
            page_rows = candidates[offset : offset + page_size]
        else:
            if not filters:
                total = discovery_cache.get_or_set(
                    scope,
                    "imdb_total_count",
                    "all",
                    lambda: int(
                        session.exec(select(func.count(IMDbCatalogShow.imdb_id))).one() or 0
                    ),
                    ttl=60.0,
                )
                data_stmt = select(IMDbCatalogShow)
            else:
                count_stmt = select(func.count(IMDbCatalogShow.imdb_id))
                data_stmt = select(IMDbCatalogShow)
                for cond in filters:
                    count_stmt = count_stmt.where(cond)
                    data_stmt = data_stmt.where(cond)
                total = discovery_cache.get_or_set(
                    scope,
                    "imdb_total_count",
                    filter_sig,
                    lambda: int(session.exec(count_stmt).one() or 0),
                    ttl=60.0,
                )

            if sort_by == "popularity":
                data_stmt = data_stmt.order_by(
                    col(IMDbCatalogShow.rating_votes).desc(),
                    col(IMDbCatalogShow.rating_score).desc(),
                )
            elif sort_by == "year_desc":
                data_stmt = data_stmt.order_by(
                    col(IMDbCatalogShow.start_year).desc(),
                    col(IMDbCatalogShow.rating_votes).desc(),
                )
            elif sort_by == "year_asc":
                data_stmt = data_stmt.order_by(
                    col(IMDbCatalogShow.start_year).asc(),
                    col(IMDbCatalogShow.rating_votes).desc(),
                )
            elif sort_by == "runtime":
                data_stmt = data_stmt.order_by(
                    col(IMDbCatalogShow.runtime_minutes).desc(),
                    col(IMDbCatalogShow.rating_votes).desc(),
                )
            elif sort_by == "title":
                data_stmt = data_stmt.order_by(col(IMDbCatalogShow.primary_title).asc())
            elif min_rating is None:
                data_stmt = data_stmt.order_by(
                    col(IMDbCatalogShow.rating_votes).desc(),
                    col(IMDbCatalogShow.rating_score).desc(),
                )
            else:
                data_stmt = data_stmt.order_by(
                    col(IMDbCatalogShow.rating_score).desc(),
                    col(IMDbCatalogShow.rating_votes).desc(),
                )

            page_rows = list(session.exec(data_stmt.offset(offset).limit(page_size)).all())

        eztv_by_imdb, _ = cls.build_eztv_lookup_index(eztv_session)
        media_sources_by_imdb_page = media_sources_by_imdb
        page_imdbs = [r.imdb_id for r in page_rows]
        p2p_seeds_by_imdb: dict[str, int] = {}
        if eztv_session is not None and page_imdbs:
            try:
                for cs in eztv_session.exec(
                    select(CatalogShow).where(col(CatalogShow.imdb_id).in_(page_imdbs))
                ).all():
                    norm = EntityResolutionService.normalize_imdb_id(cs.imdb_id)
                    if norm and cs.max_seeds > 0:
                        p2p_seeds_by_imdb[norm] = cs.max_seeds
            except Exception:
                pass

        items = [
            cls._serialize_imdb_summary(
                r,
                saved_library_map,
                eztv_by_imdb,
                p2p_seeds_by_imdb,
                media_sources_by_imdb=media_sources_by_imdb_page,
            )
            for r in page_rows
        ]
        facets = cls._build_imdb_facets(
            session,
            filters,
            filter_sig,
            total_matches=total,
            eztv_session=eztv_session,
            saved_imdbs=set(saved_library_map.keys()),
            active_p2p_imdbs=active_p2p_imdbs,
        )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "facets": facets,
        }

    @classmethod
    def _imdb_row_to_unified(
        cls,
        row: IMDbCatalogShow,
        eztv_by_imdb: dict[str, int],
        seasons: Optional[list[UnifiedSeason]] = None,
        media_sources_by_imdb: Optional[dict[str, list[str]]] = None,
    ) -> UnifiedShow:
        """Convert an IMDbCatalogShow row into a UnifiedShow contract for Descobrir."""
        norm_imdb = EntityResolutionService.normalize_imdb_id(row.imdb_id)
        eztv_show_id = (
            row.eztv_id
            if row.has_eztv and row.eztv_id
            else (eztv_by_imdb.get(norm_imdb) if norm_imdb else None)
        )
        eztv_available = bool(row.has_eztv or eztv_show_id)
        sources_set: set[str] = (
            set(media_sources_by_imdb.get(norm_imdb, []))
            if (media_sources_by_imdb and norm_imdb)
            else set()
        )
        if eztv_available:
            sources_set.add("eztv")
        media_sources = sorted(sources_set)
        has_media = bool(media_sources)
        genres = merge_canonical_genres(row.genres_ptbr, row.genres)
        providers = merge_canonical_providers(
            row.streaming_providers, row.network, keep_unknown=True
        )
        display_title = row.title_ptbr or row.primary_title
        orig_title = (
            row.primary_title
            if row.title_ptbr and row.title_ptbr.lower() != row.primary_title.lower()
            else (row.original_title or row.primary_title)
        )
        default_status = (
            "Returning Series" if row.title_type == "tvSeries" and not row.end_year else "Released"
        )
        return UnifiedShow(
            id=cls._derive_imdb_num(row),
            tmdb_id=row.tmdb_id,
            tvmaze_id=row.tvmaze_id,
            imdb_id=norm_imdb or row.imdb_id,
            title=display_title,
            original_title=orig_title,
            overview=row.synopsis_ptbr or row.synopsis or "",
            poster_url=row.poster_url,
            backdrop_url=row.backdrop_url,
            rating=float(row.rating_score or 0.0),
            genres=genres,
            first_air_date=row.release_date or (str(row.start_year) if row.start_year else None),
            status=row.status or default_status,
            network=row.network,
            streaming_providers=providers,
            eztv_available=eztv_available,
            has_media=has_media,
            media_sources=media_sources,
            sources_count=len(media_sources),
            source_provider="imdb",
            seasons=seasons or [],
        )

    @classmethod
    def search_unified_shows(
        cls,
        session: Session,
        eztv_session: Optional[Session],
        q: str,
        limit: int = 40,
    ) -> list[UnifiedShow]:
        """Search 279k+ titles in mainstream.db (PT-BR & EN-US) ranked by exact/similarity match."""
        if not cls._has_imdb_catalog(session) or not q.strip():
            return []
        qt = q.strip()
        fts_ids = cls._fts_search_imdb_ids(session, qt, limit=200)
        stmt = select(IMDbCatalogShow)
        if fts_ids is not None:
            stmt = stmt.where(col(IMDbCatalogShow.imdb_id).in_(fts_ids))
        else:
            stmt = stmt.where(
                col(IMDbCatalogShow.primary_title).ilike(f"%{qt}%")
                | col(IMDbCatalogShow.original_title).ilike(f"%{qt}%")
                | col(IMDbCatalogShow.title_ptbr).ilike(f"%{qt}%")
                | col(IMDbCatalogShow.imdb_id).ilike(f"%{qt}%")
            )
        candidates = list(session.exec(stmt.limit(200)).all())
        if not candidates:
            return []
        candidates.sort(
            key=lambda row: cls.score_imdb_show_relevance(row, qt),
            reverse=True,
        )
        eztv_by_imdb, _ = cls.build_eztv_lookup_index(eztv_session)
        media_sources_by_imdb = cls._build_sources_media_index(eztv_session)
        return [
            cls._imdb_row_to_unified(r, eztv_by_imdb, media_sources_by_imdb=media_sources_by_imdb)
            for r in candidates[:limit]
        ]

    @classmethod
    def get_trending_unified_shows(
        cls,
        session: Session,
        eztv_session: Optional[Session],
        limit: int = 20,
    ) -> list[UnifiedShow]:
        """Return top popular recent titles from mainstream.db with backdrops & EZTV badges."""
        if not cls._has_imdb_catalog(session):
            return []
        stmt = (
            select(IMDbCatalogShow)
            .where(
                col(IMDbCatalogShow.start_year) >= 2022,
                col(IMDbCatalogShow.backdrop_url).is_not(None),
                col(IMDbCatalogShow.rating_score) >= 7.0,
            )
            .order_by(
                col(IMDbCatalogShow.has_eztv).desc(),
                col(IMDbCatalogShow.rating_votes).desc(),
            )
            .limit(limit)
        )
        rows = list(session.exec(stmt).all())
        eztv_by_imdb, _ = cls.build_eztv_lookup_index(eztv_session)
        media_sources_by_imdb = cls._build_sources_media_index(eztv_session)
        return [
            cls._imdb_row_to_unified(r, eztv_by_imdb, media_sources_by_imdb=media_sources_by_imdb)
            for r in rows
        ]

    @classmethod
    def get_unified_show_from_mainstream(
        cls,
        session: Session,
        eztv_session: Optional[Session],
        show_id: int,
        imdb_id: Optional[str] = None,
    ) -> Optional[UnifiedShow]:
        """Resolve complete UnifiedShow (with seasons/episodes) from mainstream.db + sources.db."""
        if not cls._has_imdb_catalog(session):
            return None
        row: Optional[IMDbCatalogShow] = None
        if imdb_id:
            norm = EntityResolutionService.normalize_imdb_id(imdb_id)
            row = session.get(IMDbCatalogShow, norm)
        if row is None and show_id > 0:
            row = session.exec(
                select(IMDbCatalogShow).where(IMDbCatalogShow.imdb_num == show_id)
            ).first()
            if row is None:
                row = session.exec(
                    select(IMDbCatalogShow).where(IMDbCatalogShow.tmdb_id == show_id)
                ).first()
            if row is None:
                row = session.get(IMDbCatalogShow, f"tt{str(show_id).zfill(7)}")
        if row is None:
            return None

        # Reconstruct seasons and episodes from IMDbEpisodeCatalog + EZTVEpisodeCatalog
        imdb_eps = list(
            session.exec(
                select(IMDbEpisodeCatalog)
                .where(IMDbEpisodeCatalog.show_imdb_id == row.imdb_id)
                .order_by(
                    col(IMDbEpisodeCatalog.season).asc(),
                    col(IMDbEpisodeCatalog.episode).asc(),
                )
            ).all()
        )
        eztv_ep_map: dict[tuple[int, int], EZTVEpisodeCatalog] = {}
        eztv_by_imdb, _ = cls.build_eztv_lookup_index(eztv_session)
        norm_imdb = EntityResolutionService.normalize_imdb_id(row.imdb_id)
        ez_show_id = (
            row.eztv_id
            if row.has_eztv and row.eztv_id
            else (eztv_by_imdb.get(norm_imdb) if norm_imdb else None)
        )
        if eztv_session is not None and ez_show_id:
            try:
                ez_eps = eztv_session.exec(
                    select(EZTVEpisodeCatalog).where(EZTVEpisodeCatalog.show_id == ez_show_id)
                ).all()
                for ee in ez_eps:
                    eztv_ep_map[(int(ee.season or 0), int(ee.episode or 0))] = ee
            except Exception:
                pass

        seasons_dict: dict[int, list[UnifiedEpisode]] = {}
        for ie in imdb_eps:
            s_num = int(ie.season or 0)
            e_num = int(ie.episode or 0)
            if s_num <= 0 or e_num <= 0:
                continue
            ez_match = eztv_ep_map.get((s_num, e_num))
            ep_digits = (ie.episode_imdb_id or "").lower().lstrip("t")
            ep_id = int(ep_digits) if ep_digits.isdigit() else None
            seasons_dict.setdefault(s_num, []).append(
                UnifiedEpisode(
                    id=ep_id,
                    season_number=s_num,
                    episode_number=e_num,
                    title=(ez_match.title if ez_match and ez_match.title else ie.title)
                    or f"Episódio {e_num}",
                    overview=(ez_match.summary if ez_match and ez_match.summary else "") or "",
                    air_date=(ez_match.airdate if ez_match and ez_match.airdate else None)
                    or (str(ie.start_year) if ie.start_year else None),
                    rating=float(ie.rating_score or (ez_match.rating if ez_match else 0.0) or 0.0),
                )
            )

        # If IMDbEpisodeCatalog had no rows for this show, fall back to EZTVEpisodeCatalog
        if not seasons_dict and eztv_ep_map:
            for (s_num, e_num), ee in sorted(eztv_ep_map.items()):
                if s_num <= 0 or e_num <= 0:
                    continue
                seasons_dict.setdefault(s_num, []).append(
                    UnifiedEpisode(
                        id=ee.id,
                        season_number=s_num,
                        episode_number=e_num,
                        title=ee.title or f"Episódio {e_num}",
                        overview=ee.summary or "",
                        air_date=ee.airdate,
                        rating=float(ee.rating or 0.0),
                    )
                )

        seasons_list = [
            UnifiedSeason(
                season_number=s_num,
                name=f"Temporada {s_num}",
                episode_count=len(eps),
                episodes=eps,
            )
            for s_num, eps in sorted(seasons_dict.items())
        ]
        media_sources_by_imdb = cls._build_sources_media_index(eztv_session)
        return cls._imdb_row_to_unified(
            row,
            eztv_by_imdb,
            seasons=seasons_list,
            media_sources_by_imdb=media_sources_by_imdb,
        )

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
                p.id: p for p in session.exec(select(PersonRecord)).all() if p.id is not None
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
        data_sources: Optional[str] = None,
        sort_by: str = "rating",
        page: int = 1,
        page_size: int = 24,
    ) -> dict[str, Any]:
        """Execute composite boolean/relational filtering and compute dynamic facets."""
        if cls._has_imdb_catalog(session):
            return cls._query_imdb_catalog_sql(
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

        facet_sources: dict[str, int] = {k: 0 for k, _ in DATA_SOURCE_DEFINITIONS}
        for w in filtered:
            norm_w = EntityResolutionService.normalize_imdb_id(w.imdb_id)
            if norm_w:
                facet_sources["imdb"] += 1
                if p2p_seeds_by_imdb.get(norm_w, 0) > 0:
                    facet_sources["p2p_active"] += 1
                if norm_w in saved_library_map:
                    facet_sources["personal_library"] += 1
            if w.tmdb_id:
                facet_sources["tmdb"] += 1
            if w.tvmaze_id:
                facet_sources["tvmaze"] += 1
            if w.overview:
                facet_sources["ptbr"] += 1
            has_ez, _ = cls._resolve_eztv_match(w, eztv_by_imdb, eztv_by_slug)
            if has_ez:
                facet_sources["eztv"] += 1

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
                "data_sources": [
                    {"key": k, "count": v}
                    for k, v in sorted(facet_sources.items(), key=lambda i: i[1], reverse=True)
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
            "has_media": eztv_available,
            "media_sources": ["eztv"] if eztv_available else [],
            "sources_count": 1 if eztv_available else 0,
        }

    @classmethod
    def _get_imdb_work_dossier(
        cls,
        session: Session,
        work_identifier: int | str,
        eztv_session: Optional[Session] = None,
    ) -> Optional[dict[str, Any]]:
        """Build complete dossier from IMDbCatalogShow + IMDbEpisodeCatalog in mainstream.db."""
        row: Optional[IMDbCatalogShow] = None
        ident_str = str(work_identifier).strip()
        if ident_str.lower().startswith("tt"):
            norm_id = EntityResolutionService.normalize_imdb_id(ident_str)
            row = session.get(IMDbCatalogShow, norm_id)
        elif ident_str.isdigit():
            num = int(ident_str)
            row = session.exec(
                select(IMDbCatalogShow).where(IMDbCatalogShow.imdb_num == num)
            ).first()
            if row is None:
                row = session.get(IMDbCatalogShow, f"tt{ident_str.zfill(7)}")
        if row is None:
            return None

        saved_library_map: dict[str, str] = {}
        for sr in session.exec(select(ShowRecord)).all():
            if sr.imdb_id:
                n = EntityResolutionService.normalize_imdb_id(sr.imdb_id)
                if n:
                    saved_library_map[n] = sr.user_status

        eztv_by_imdb, _ = cls.build_eztv_lookup_index(eztv_session)
        norm_imdb = EntityResolutionService.normalize_imdb_id(row.imdb_id)
        p2p_seeds_by_imdb: dict[str, int] = {}
        if eztv_session is not None and norm_imdb:
            try:
                cs = eztv_session.get(CatalogShow, norm_imdb)
                if cs and cs.max_seeds > 0:
                    p2p_seeds_by_imdb[norm_imdb] = cs.max_seeds
            except Exception:
                pass

        summary = cls._serialize_imdb_summary(
            row,
            saved_library_map,
            eztv_by_imdb,
            p2p_seeds_by_imdb,
            media_sources_by_imdb=cls._build_sources_media_index(eztv_session),
        )

        # Fetch episode count and sample seasons from IMDbEpisodeCatalog
        ep_count = int(
            session.exec(
                select(func.count(IMDbEpisodeCatalog.episode_imdb_id)).where(
                    IMDbEpisodeCatalog.show_imdb_id == row.imdb_id
                )
            ).one()
            or 0
        )
        summary["episodes_count"] = ep_count

        credits_list: list[dict[str, Any]] = []
        idx = 1
        for d in cls._parse_csv(row.directors)[:6]:
            credits_list.append(
                {
                    "person_id": idx,
                    "name": d,
                    "role_type": "director",
                    "character_name": None,
                    "department": "Directing",
                    "country": summary["origin_country"],
                }
            )
            idx += 1
        for c in cls._parse_csv(row.creators)[:6]:
            credits_list.append(
                {
                    "person_id": idx,
                    "name": c,
                    "role_type": "creator",
                    "character_name": None,
                    "department": "Writing",
                    "country": summary["origin_country"],
                }
            )
            idx += 1
        for a in cls._parse_csv(row.cast_members)[:12]:
            credits_list.append(
                {
                    "person_id": idx,
                    "name": a,
                    "role_type": "actor",
                    "character_name": None,
                    "department": "Acting",
                    "country": summary["origin_country"],
                }
            )
            idx += 1

        avail_list = [
            {
                "provider_name": p,
                "territory": "BR",
                "monetization_type": "flatrate",
                "source_provider": "tmdb",
            }
            for p in summary["streaming_providers"]
        ]

        # SQL-backed similar works using primary genre & format (sub-15ms on 279k rows)
        similar: list[dict[str, Any]] = []
        primary_genres = cls._parse_csv(row.genres or row.genres_ptbr)[:2]
        sim_stmt = select(IMDbCatalogShow).where(
            IMDbCatalogShow.imdb_id != row.imdb_id,
            IMDbCatalogShow.title_type == row.title_type,
        )
        if primary_genres:
            sim_stmt = sim_stmt.where(col(IMDbCatalogShow.genres).ilike(f"%{primary_genres[0]}%"))
        sim_rows = session.exec(
            sim_stmt.order_by(col(IMDbCatalogShow.rating_votes).desc()).limit(6)
        ).all()
        for sr_row in sim_rows:
            s_genres = cls._parse_csv(sr_row.genres_ptbr or sr_row.genres)
            similar.append(
                {
                    "id": cls._derive_imdb_num(sr_row),
                    "title": sr_row.title_ptbr or sr_row.primary_title,
                    "original_title": sr_row.original_title,
                    "work_type": cls._map_imdb_work_type(sr_row.title_type),
                    "release_year": sr_row.start_year,
                    "poster_url": sr_row.poster_url,
                    "canonical_rating": float(sr_row.rating_score or 0.0),
                    "genres": s_genres,
                    "similarity_score": 82.0,
                    "similarity_reasons": [f"Gênero e formato afins ({', '.join(primary_genres)})"],
                }
            )

        ext_ids = [{"provider": "imdb", "external_id": row.imdb_id, "confidence": "deterministic"}]
        if row.tmdb_id:
            ext_ids.append(
                {"provider": "tmdb", "external_id": str(row.tmdb_id), "confidence": "deterministic"}
            )
        if row.tvmaze_id:
            ext_ids.append(
                {
                    "provider": "tvmaze",
                    "external_id": str(row.tvmaze_id),
                    "confidence": "deterministic",
                }
            )

        provenance = [
            {
                "source_provider": "imdb",
                "external_id": row.imdb_id,
                "field_name": "title,rating,episodes",
                "field_value": row.primary_title,
                "selection_reason": "canonical_imdb_backbone",
                "fetched_at": row.updated_at or "",
            }
        ]
        if row.tmdb_id:
            provenance.append(
                {
                    "source_provider": "tmdb",
                    "external_id": str(row.tmdb_id),
                    "field_name": "title_ptbr,synopsis_ptbr,poster_url,providers",
                    "field_value": row.title_ptbr or row.primary_title,
                    "selection_reason": "ptbr_tmdb_hydration",
                    "fetched_at": row.updated_at or "",
                }
            )
        if row.has_eztv and row.eztv_id:
            provenance.append(
                {
                    "source_provider": "eztv",
                    "external_id": str(row.eztv_id),
                    "field_name": "has_eztv,status,streaming_providers",
                    "field_value": row.eztv_match_type or "exact_imdb",
                    "selection_reason": "sources_cross_reference",
                    "fetched_at": row.updated_at or "",
                }
            )

        summary.update(
            {
                "trailer_url": row.trailer_url,
                "content_rating": row.content_rating,
                "external_identifiers": ext_ids,
                "provenance": provenance,
                "credits": credits_list,
                "availabilities": avail_list,
                "explicit_relations": [],
                "similar_works": similar,
                "calendar_events": [],
            }
        )
        return summary

    @classmethod
    def get_work_dossier(
        cls,
        session: Session,
        work_id: int | str,
        eztv_session: Optional[Session] = None,
    ) -> Optional[dict[str, Any]]:
        """Build comprehensive canonical dossier for a MediaWork or IMDbCatalogShow."""
        if cls._has_imdb_catalog(session):
            imdb_dossier = cls._get_imdb_work_dossier(session, work_id, eztv_session=eztv_session)
            if imdb_dossier is not None:
                return imdb_dossier

        numeric_id = int(work_id) if str(work_id).isdigit() else None
        work = session.get(MediaWork, numeric_id) if numeric_id is not None else None
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
        """Find all audiovisual works where two people collaborated (supports 279k IMDb catalog)."""
        if cls._has_imdb_catalog(session):
            ids_a = cls._fts_person_imdb_ids(session, person_a_query, limit=600)
            ids_b = cls._fts_person_imdb_ids(session, person_b_query, limit=600)
            if ids_a and ids_b:
                common_imdbs = list(set(ids_a).intersection(set(ids_b)))
                if common_imdbs:
                    rows = list(
                        session.exec(
                            select(IMDbCatalogShow).where(
                                col(IMDbCatalogShow.imdb_id).in_(common_imdbs)
                            )
                        ).all()
                    )
                    norm_a = cls._normalize_search_text(person_a_query)
                    norm_b = cls._normalize_search_text(person_b_query)

                    def _infer_role(row: IMDbCatalogShow, norm_p: str) -> str:
                        if norm_p in cls._normalize_search_text(row.directors):
                            return "director"
                        if norm_p in cls._normalize_search_text(row.creators):
                            return "creator"
                        return "actor"

                    shared = [
                        {
                            "id": cls._derive_imdb_num(r),
                            "title": r.title_ptbr or r.primary_title,
                            "work_type": cls._map_imdb_work_type(r.title_type),
                            "release_year": r.start_year,
                            "canonical_rating": float(r.rating_score or 0.0),
                            "poster_url": r.poster_url,
                            "person_a_role": _infer_role(r, norm_a),
                            "person_b_role": _infer_role(r, norm_b),
                        }
                        for r in rows
                    ]
                    shared.sort(
                        key=lambda x: (x["release_year"] or 0, x["canonical_rating"]),
                        reverse=True,
                    )
                    return {
                        "person_a": person_a_query.strip(),
                        "person_b": person_b_query.strip(),
                        "shared_works": shared,
                    }

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
