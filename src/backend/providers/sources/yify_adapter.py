"""YIFY / YTS v2 official movie torrent adapter (movies-api.accel.li/api/v2/) (ADR-014)."""

from __future__ import annotations

import asyncio
import json
import math
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.backend.core.domain_concurrency import create_shared_http_client, domain_semaphores
from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord
from src.backend.providers.sources.base import (
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceQueryContext,
    build_official_magnet,
    compute_title_match_confidence,
    is_antibot_challenge,
    register_source_adapter,
    utc_now,
    validate_safe_url,
)
from src.backend.services.entity_resolution import EntityResolutionService

DEFAULT_YTS_BASE_URL = "https://movies-api.accel.li/api/v2/list_movies.json"
DEFAULT_YTS_API_ROOT = "https://movies-api.accel.li/api/v2"
DEFAULT_YTS_MIRRORS: list[str] = [
    "https://yts.gg/api/v2/list_movies.json",
    "https://yts.mx/api/v2/list_movies.json",
    "https://yts.lt/api/v2/list_movies.json",
]


class YIFYAdapterConfig(BaseModel):
    """Configuration schema for YIFY / YTS JSON API v2 (movies-api.accel.li)."""

    base_url: str = Field(
        default=DEFAULT_YTS_BASE_URL,
        title="Endpoint YTS API v2 (movies-api.accel.li)",
    )
    mirrors: list[str] = Field(
        default_factory=lambda: list(DEFAULT_YTS_MIRRORS),
        title="Mirrors YTS Alternativos",
    )
    default_quality: str = Field(
        default="All",
        title="Filtro de Qualidade Padrão (All, 2160p, 1080p, 1080p.x265, 720p, 480p, 3D)",
    )
    minimum_rating: int = Field(
        default=0,
        ge=0,
        le=9,
        title="Nota Mínima IMDb (0-9)",
    )
    sort_by: str = Field(
        default="date_added",
        title="Ordenação Padrão (date_added, seeds, download_count, rating, year, title)",
    )
    with_rt_ratings: bool = Field(
        default=True,
        title="Incluir Notas Rotten Tomatoes (with_rt_ratings)",
    )
    timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


@register_source_adapter
class YIFYSourceAdapter(BaseSourceAdapter):
    """YIFY / YTS movie indexer supporting 4 official v2 endpoints & 10-tracker magnet builder."""

    adapter_key = "yify"
    display_name = "YIFY / YTS (movies-api.accel.li v2)"
    description = (
        "API JSON v2 oficial do YTS (movies-api.accel.li/api/v2/) com list_movies, "
        "movie_details, movie_suggestions, movie_parental_guides e 10 trackers oficiais."
    )
    default_source_kind = "torrent_mirrorable"
    default_media_types = "movie"
    supports_sync = True
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return YIFYAdapterConfig

    @staticmethod
    def _parse_cfg(instance: ExternalSourceRecord) -> YIFYAdapterConfig:
        try:
            raw = json.loads(instance.config_json or "{}")
        except Exception:
            raw = {}
        if instance.base_url and not raw.get("base_url"):
            raw["base_url"] = instance.base_url
        return YIFYAdapterConfig.model_validate(raw)

    @staticmethod
    def _candidate_endpoints(cfg: YIFYAdapterConfig) -> list[str]:
        urls = [cfg.base_url, *cfg.mirrors, DEFAULT_YTS_BASE_URL]
        out: list[str] = []
        for u in urls:
            safe = validate_safe_url(u, ("http", "https"))
            if safe and safe not in out:
                out.append(safe)
        return out or [DEFAULT_YTS_BASE_URL]

    @staticmethod
    def _api_root_from_endpoint(endpoint: str) -> str:
        if "/api/v2" in endpoint:
            return endpoint.split("/api/v2")[0] + "/api/v2"
        return DEFAULT_YTS_API_ROOT

    @staticmethod
    def _movies_to_candidates(
        movies: list[dict[str, Any]],
        query_ctx: Optional[SourceQueryContext] = None,
    ) -> list[NormalizedReleaseCandidate]:
        out: list[NormalizedReleaseCandidate] = []
        target_imdb = (
            EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
            if query_ctx and query_ctx.imdb_id
            else None
        )
        for movie in movies:
            imdb_id = EntityResolutionService.normalize_imdb_id(movie.get("imdb_code"))
            title = str(movie.get("title") or "").strip()
            year_raw = movie.get("year")
            year = int(year_raw) if year_raw else None
            rating = float(movie.get("rating") or 0.0)
            genres = ", ".join(movie.get("genres") or []) or None
            poster = validate_safe_url(
                movie.get("medium_cover_image") or movie.get("large_cover_image"),
                ("http", "https"),
            )
            page_url = validate_safe_url(movie.get("url"), ("http", "https"))

            matched_by = "exact_imdb"
            confidence = 1.0
            if query_ctx:
                if target_imdb and imdb_id == target_imdb:
                    matched_by = "exact_imdb"
                    confidence = 1.0
                elif target_imdb and imdb_id and imdb_id != target_imdb:
                    continue
                else:
                    matched_by = "title_year_match"
                    confidence = compute_title_match_confidence(
                        query_title=query_ctx.title,
                        query_original_title=query_ctx.original_title,
                        query_year=query_ctx.year,
                        query_work_type=query_ctx.work_type,
                        candidate_title=title,
                        candidate_year=year,
                    )
                    if not imdb_id and confidence >= 0.85 and target_imdb:
                        imdb_id = target_imdb

            for tor in movie.get("torrents") or []:
                info_hash = str(tor.get("hash") or "").strip()
                raw_quality = str(tor.get("quality") or "Unknown")
                codec = str(tor.get("video_codec") or "").lower()
                quality = (
                    "1080p.x265"
                    if raw_quality == "1080p" and ("x265" in codec or "hevc" in codec)
                    else raw_quality
                )
                ext_id = f"yts:{movie.get('id')}:{quality}:{info_hash[:12]}"
                magnet = build_official_magnet(info_hash, title) if info_hash else None
                tor_url = validate_safe_url(tor.get("url"), ("http", "https"))
                out.append(
                    NormalizedReleaseCandidate(
                        external_id=ext_id,
                        imdb_id=imdb_id,
                        title=f"{title} ({year}) {quality}" if year else f"{title} {quality}",
                        work_type="movie",
                        quality=quality,
                        seeds=int(tor.get("seeds") or 0),
                        peers=int(tor.get("peers") or 0),
                        size_bytes=int(tor.get("size_bytes") or 0),
                        release_type="magnet" if magnet else "torrent",
                        magnet_url=magnet,
                        torrent_url=tor_url,
                        external_url=page_url,
                        info_hash=info_hash or None,
                        poster_url=poster,
                        genres=genres,
                        year=year,
                        rating=rating,
                        matched_by=matched_by,
                        match_confidence=confidence,
                    )
                )
        return out

    @classmethod
    def _movies_to_presence_candidates(
        cls,
        movies: list[dict[str, Any]],
    ) -> list[NormalizedReleaseCandidate]:
        """Convert YTS movie entries into compact 1-row-per-movie Stage 1B presence records."""
        out: list[NormalizedReleaseCandidate] = []
        seen_ext: set[str] = set()
        for movie in movies:
            imdb_id = EntityResolutionService.normalize_imdb_id(movie.get("imdb_code"))
            movie_id = movie.get("id")
            if not imdb_id and not movie_id:
                continue
            ext_id = f"yts:presence:{imdb_id or movie_id}"
            if ext_id in seen_ext:
                continue
            seen_ext.add(ext_id)

            title = str(movie.get("title") or "").strip()
            if not title:
                continue
            year_raw = movie.get("year")
            year = int(year_raw) if year_raw else None
            rating = float(movie.get("rating") or 0.0)
            genres = ", ".join(movie.get("genres") or []) or None
            poster = validate_safe_url(
                movie.get("large_cover_image") or movie.get("medium_cover_image"),
                ("http", "https"),
            )
            page_url = validate_safe_url(movie.get("url"), ("http", "https"))

            torrents = movie.get("torrents") or []
            qualities: list[str] = []
            max_seeds = 0
            max_peers = 0
            best_size = 0
            best_hash: Optional[str] = None
            for tor in torrents:
                raw_q = str(tor.get("quality") or "").strip()
                codec = str(tor.get("video_codec") or "").lower()
                q_label = (
                    "1080p.x265"
                    if raw_q == "1080p" and ("x265" in codec or "hevc" in codec)
                    else raw_q
                )
                if q_label and q_label not in qualities:
                    qualities.append(q_label)
                s_val = int(tor.get("seeds") or 0)
                p_val = int(tor.get("peers") or 0)
                if s_val >= max_seeds:
                    max_seeds = s_val
                    max_peers = p_val
                    best_size = int(tor.get("size_bytes") or 0)
                    best_hash = str(tor.get("hash") or "").strip() or best_hash

            if max_seeds < 1:
                continue

            best_magnet = build_official_magnet(best_hash, title) if best_hash else None
            out.append(
                NormalizedReleaseCandidate(
                    external_id=ext_id,
                    imdb_id=imdb_id,
                    title=f"{title} ({year})" if year else title,
                    work_type="movie",
                    quality=",".join(qualities) if qualities else "1080p",
                    seeds=max_seeds,
                    peers=max_peers,
                    size_bytes=best_size,
                    release_type="magnet" if best_magnet else "link",
                    magnet_url=best_magnet,
                    torrent_url=None,
                    external_url=page_url,
                    info_hash=best_hash,
                    poster_url=poster,
                    genres=genres,
                    year=year,
                    rating=rating,
                    matched_by="exact_imdb" if imdb_id else "title_year_match",
                    match_confidence=1.0 if imdb_id else 0.75,
                )
            )
        return out

    async def fetch_sync_candidates(
        self,
        instance: ExternalSourceRecord,
        *,
        pages: int = 2,
        start_page: int = 1,
        compact_presence: bool = False,
        mode: str = "incremental",
        quality: Optional[str] = None,
        minimum_rating: Optional[int] = None,
        sort_by: Optional[str] = None,
        order_by: str = "desc",
        genre: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> dict[str, Any]:
        """Pure HTTP Fan-out: fetch start_page then remaining pages concurrently via semaphore."""
        cfg = self._parse_cfg(instance)
        endpoints = self._candidate_endpoints(cfg)
        cur_start = max(1, int(start_page))
        page_budget = max(1, min(int(pages), 100))

        eff_quality = (quality or cfg.default_quality or "All").strip()
        eff_min_rating = (
            minimum_rating if minimum_rating is not None else int(cfg.minimum_rating or 0)
        )
        if sort_by:
            eff_sort = sort_by
        elif mode == "baseline":
            eff_sort = "seeds"
        else:
            eff_sort = cfg.sort_by or "date_added"

        base_params: dict[str, Any] = {
            "limit": 50,
            "sort_by": eff_sort,
            "order_by": order_by if order_by in ("desc", "asc") else "desc",
            "with_rt_ratings": "true" if cfg.with_rt_ratings else "false",
        }
        if eff_quality and eff_quality.lower() != "all":
            base_params["quality"] = eff_quality
        if eff_min_rating > 0:
            base_params["minimum_rating"] = min(9, max(0, eff_min_rating))
        if genre and genre.strip().lower() != "all":
            base_params["genre"] = genre.strip()

        last_err: Optional[Exception] = None
        own_client = client is None
        http_client = client or create_shared_http_client(timeout=cfg.timeout_seconds)

        async def _fetch_page(ep: str, pg: int) -> dict[str, Any]:
            async with domain_semaphores.get("yify"):
                r = await http_client.get(ep, params={**base_params, "page": pg})
                r.raise_for_status()
                return r.json()

        try:
            for endpoint in endpoints:
                try:
                    first_payload = await _fetch_page(endpoint, cur_start)
                    first_data = first_payload.get("data") or {}
                    movie_count = int(first_data.get("movie_count") or 0)
                    limit_val = max(1, int(first_data.get("limit") or 50))
                    total_pages = (
                        max(1, math.ceil(movie_count / limit_val))
                        if movie_count > 0
                        else cur_start + page_budget - 1
                    )
                    first_movies = first_data.get("movies") or []
                    if not first_movies:
                        return {
                            "candidates": [],
                            "meta": {
                                "source": instance.source_key,
                                "endpoint": endpoint,
                                "mode": mode,
                                "sort_by": eff_sort,
                                "quality": eff_quality,
                                "minimum_rating": eff_min_rating,
                                "compact_presence": compact_presence,
                                "start_page": cur_start,
                                "last_page": cur_start - 1,
                                "next_page": 1,
                                "total_pages": max(1, total_pages),
                                "movie_count": movie_count,
                                "bootstrap_completed": True,
                                "movies_seen": 0,
                            },
                        }

                    max_end_page = min(cur_start + page_budget - 1, total_pages)
                    remaining_pages = list(range(cur_start + 1, max_end_page + 1))
                    page_results: list[tuple[int, list[dict[str, Any]]]] = [
                        (cur_start, first_movies)
                    ]

                    if remaining_pages:
                        raw_responses = await asyncio.gather(
                            *(_fetch_page(endpoint, pg) for pg in remaining_pages),
                            return_exceptions=True,
                        )
                        for pg, res_item in zip(remaining_pages, raw_responses):
                            if isinstance(res_item, Exception):
                                continue
                            d_blk = res_item.get("data") or {}
                            if d_blk.get("movie_count"):
                                movie_count = int(d_blk.get("movie_count") or movie_count)
                                total_pages = max(1, math.ceil(movie_count / limit_val))
                            pg_movies = d_blk.get("movies") or []
                            if pg_movies:
                                page_results.append((pg, pg_movies))

                    all_movies: list[dict[str, Any]] = []
                    last_page = cur_start
                    exhausted = False
                    for pg, m_list in sorted(page_results, key=lambda x: x[0]):
                        all_movies.extend(m_list)
                        last_page = max(last_page, pg)
                    if remaining_pages and len(page_results) < len(remaining_pages) + 1:
                        exhausted = True

                    cands = (
                        self._movies_to_presence_candidates(all_movies)
                        if compact_presence
                        else self._movies_to_candidates(all_movies)
                    )
                    bootstrap_done = exhausted or (movie_count > 0 and last_page >= total_pages)
                    next_page = 1 if bootstrap_done else (last_page + 1)
                    return {
                        "candidates": cands,
                        "meta": {
                            "source": instance.source_key,
                            "endpoint": endpoint,
                            "mode": mode,
                            "sort_by": eff_sort,
                            "quality": eff_quality,
                            "minimum_rating": eff_min_rating,
                            "compact_presence": compact_presence,
                            "start_page": cur_start,
                            "last_page": last_page,
                            "next_page": next_page,
                            "total_pages": total_pages,
                            "movie_count": movie_count,
                            "bootstrap_completed": bootstrap_done,
                            "movies_seen": len(all_movies),
                        },
                    }
                except Exception as exc:
                    last_err = exc
                    continue
        finally:
            if own_client:
                await http_client.aclose()

        if last_err:
            raise last_err
        return {
            "candidates": [],
            "meta": {
                "source": instance.source_key,
                "mode": mode,
                "start_page": cur_start,
                "next_page": cur_start,
                "total_pages": cur_start,
                "bootstrap_completed": False,
                "movies_seen": 0,
            },
        }

    @staticmethod
    def persist_sync_candidates(
        sources_session: Session,
        source_key: str,
        candidates: list[NormalizedReleaseCandidate],
    ) -> tuple[int, int]:
        """Fan-in SQLite batch SELECT/UPSERT for YTS candidates."""
        indexed = 0
        updated = 0
        if not candidates:
            return indexed, updated

        deduped: list[NormalizedReleaseCandidate] = []
        seen_ext: set[str] = set()
        for c in candidates:
            if c.external_id not in seen_ext:
                seen_ext.add(c.external_id)
                deduped.append(c)

        ext_ids = [c.external_id for c in deduped]
        with sources_session.no_autoflush:
            existing_map = {
                row.external_id: row
                for row in sources_session.exec(
                    select(ExternalRelease).where(
                        ExternalRelease.source_key == source_key,
                        ExternalRelease.external_id.in_(ext_ids),
                    )
                ).all()
            }
            now_ts = utc_now()
            for cand in deduped:
                existing = existing_map.get(cand.external_id)
                if existing:
                    existing.seeds = cand.seeds
                    existing.peers = cand.peers
                    existing.quality = cand.quality
                    existing.poster_url = cand.poster_url or existing.poster_url
                    existing.magnet_url = cand.magnet_url or existing.magnet_url
                    existing.last_checked_at = now_ts
                    sources_session.add(existing)
                    updated += 1
                else:
                    if cand.seeds < 1:
                        continue
                    rel_row = ExternalRelease(
                        source_key=source_key,
                        external_id=cand.external_id,
                        imdb_id=cand.imdb_id,
                        title=cand.title,
                        work_type=cand.work_type,
                        quality=cand.quality,
                        seeds=cand.seeds,
                        peers=cand.peers,
                        size_bytes=cand.size_bytes,
                        release_type=cand.release_type,
                        magnet_url=cand.magnet_url,
                        torrent_url=cand.torrent_url,
                        external_url=cand.external_url,
                        info_hash=cand.info_hash,
                        poster_url=cand.poster_url,
                        genres=cand.genres,
                        year=cand.year,
                        rating=cand.rating,
                        matched_by=cand.matched_by,
                        match_confidence=cand.match_confidence,
                        last_checked_at=now_ts,
                    )
                    sources_session.add(rel_row)
                    existing_map[cand.external_id] = rel_row
                    indexed += 1
        sources_session.commit()
        return indexed, updated

    async def sync(
        self,
        instance: ExternalSourceRecord,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 2,
        start_page: int = 1,
        compact_presence: bool = False,
        enrich: bool = False,
        mode: str = "incremental",
        quality: Optional[str] = None,
        minimum_rating: Optional[int] = None,
        sort_by: Optional[str] = None,
        order_by: str = "desc",
        genre: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> dict[str, Any]:
        fetched = await self.fetch_sync_candidates(
            instance,
            pages=pages,
            start_page=start_page,
            compact_presence=compact_presence,
            mode=mode,
            quality=quality,
            minimum_rating=minimum_rating,
            sort_by=sort_by,
            order_by=order_by,
            genre=genre,
            client=client,
        )
        cands = fetched["candidates"]
        meta = dict(fetched["meta"])
        indexed, updated = self.persist_sync_candidates(
            sources_session, instance.source_key, cands
        )
        meta["releases_indexed"] = indexed
        meta["releases_updated"] = updated
        return meta

    async def search(
        self,
        instance: ExternalSourceRecord,
        query_ctx: SourceQueryContext,
        sources_session: Optional[Session] = None,
        mainstream_session: Optional[Session] = None,
    ) -> AdapterSearchOutcome:
        cfg = self._parse_cfg(instance)
        endpoints = self._candidate_endpoints(cfg)
        norm_imdb = EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
        q_term = (
            query_ctx.custom_query
            or norm_imdb
            or query_ctx.original_title
            or query_ctx.title
        )
        last_error_msg: Optional[str] = None

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            for endpoint in endpoints:
                try:
                    resp = await client.get(
                        endpoint,
                        params={
                            "query_term": q_term,
                            "limit": min(query_ctx.limit, 50),
                            "with_rt_ratings": "true" if cfg.with_rt_ratings else "false",
                        },
                    )
                    if is_antibot_challenge(resp.status_code, resp.text, dict(resp.headers)):
                        last_error_msg = f"Anti-bot Challenge em {endpoint}"
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    movies = payload.get("data", {}).get("movies") or []

                    # Fallback to movie_details.json?imdb_id=... when list_movies returns empty
                    if not movies and norm_imdb and not query_ctx.custom_query:
                        api_root = self._api_root_from_endpoint(endpoint)
                        det_resp = await client.get(
                            f"{api_root}/movie_details.json",
                            params={
                                "imdb_id": norm_imdb,
                                "with_images": "true",
                                "with_cast": "true",
                            },
                        )
                        if det_resp.status_code == 200:
                            det_movie = det_resp.json().get("data", {}).get("movie") or {}
                            if det_movie and det_movie.get("torrents"):
                                movies = [det_movie]

                    candidates = self._movies_to_candidates(movies, query_ctx=query_ctx)
                    return AdapterSearchOutcome(status="ok", releases=candidates)
                except httpx.TimeoutException:
                    last_error_msg = f"Timeout ao consultar {endpoint}"
                except Exception as exc:
                    last_error_msg = str(exc)

        return AdapterSearchOutcome(
            status="error",
            message=last_error_msg or "Todos os mirrors YTS falharam.",
            releases=[],
        )

    async def fetch_movie_enrichment(
        self,
        instance: ExternalSourceRecord,
        imdb_id: str,
        movie_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Fetch official YTS v2 movie_details, movie_suggestions, and movie_parental_guides."""
        cfg = self._parse_cfg(instance)
        endpoints = self._candidate_endpoints(cfg)
        norm_imdb = EntityResolutionService.normalize_imdb_id(imdb_id) or imdb_id.strip()

        async with httpx.AsyncClient(timeout=min(cfg.timeout_seconds, 5.0)) as client:
            for endpoint in endpoints:
                api_root = self._api_root_from_endpoint(endpoint)
                try:
                    yts_id = movie_id
                    seed_movie: dict[str, Any] = {}
                    if not yts_id:
                        list_resp = await client.get(
                            endpoint,
                            params={
                                "query_term": norm_imdb,
                                "limit": 1,
                                "with_rt_ratings": "true",
                            },
                        )
                        list_resp.raise_for_status()
                        movies = list_resp.json().get("data", {}).get("movies") or []
                        if movies:
                            seed_movie = movies[0]
                            yts_id = int(seed_movie.get("id") or 0) or None

                    if not yts_id:
                        return {
                            "status": "not_found",
                            "imdb_id": norm_imdb,
                            "movie_id": None,
                            "details": None,
                            "suggestions": [],
                            "parental_guides": [],
                        }

                    async def _get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
                        try:
                            r = await client.get(f"{api_root}/{path}", params=params)
                            r.raise_for_status()
                            return r.json().get("data") or {}
                        except Exception:
                            return {}

                    details_data, suggestions_data, guides_data = await asyncio.gather(
                        _get_json(
                            "movie_details.json",
                            {
                                "movie_id": yts_id,
                                "with_images": "true",
                                "with_cast": "true",
                            },
                        ),
                        _get_json("movie_suggestions.json", {"movie_id": yts_id}),
                        _get_json("movie_parental_guides.json", {"movie_id": yts_id}),
                    )

                    det_movie = details_data.get("movie") or seed_movie or {}
                    raw_suggestions = suggestions_data.get("movies") or []
                    raw_guides = guides_data.get("parental_guides") or []

                    suggestions = [
                        {
                            "movie_id": s.get("id"),
                            "imdb_id": EntityResolutionService.normalize_imdb_id(
                                s.get("imdb_code")
                            ),
                            "title": s.get("title"),
                            "year": s.get("year"),
                            "rating": float(s.get("rating") or 0.0),
                            "poster_url": validate_safe_url(
                                s.get("medium_cover_image"), ("http", "https")
                            ),
                            "qualities": sorted(
                                {
                                    str(t.get("quality"))
                                    for t in (s.get("torrents") or [])
                                    if t.get("quality")
                                }
                            ),
                        }
                        for s in raw_suggestions
                        if isinstance(s, dict) and s.get("title")
                    ]

                    parental_guides = [
                        {
                            "type": str(g.get("type") or "Info").strip(),
                            "parental_guide_text": str(g.get("parental_guide_text") or "").strip(),
                        }
                        for g in raw_guides
                        if isinstance(g, dict) and g.get("parental_guide_text")
                    ]

                    return {
                        "status": "ok",
                        "endpoint": api_root,
                        "imdb_id": norm_imdb,
                        "movie_id": yts_id,
                        "details": {
                            "title": det_movie.get("title") or seed_movie.get("title"),
                            "year": det_movie.get("year") or seed_movie.get("year"),
                            "rating": float(
                                det_movie.get("rating") or seed_movie.get("rating") or 0.0
                            ),
                            "runtime": int(
                                det_movie.get("runtime") or seed_movie.get("runtime") or 0
                            ),
                            "download_count": int(det_movie.get("download_count") or 0),
                            "like_count": int(det_movie.get("like_count") or 0),
                            "mpa_rating": det_movie.get("mpa_rating") or "",
                            "yt_trailer_code": det_movie.get("yt_trailer_code") or "",
                            "rt_critics_score": seed_movie.get("rt_critics_score")
                            or det_movie.get("rt_critics_score"),
                            "rt_audience_score": seed_movie.get("rt_audience_score")
                            or det_movie.get("rt_audience_score"),
                            "cast": [
                                {
                                    "name": c.get("name"),
                                    "character_name": c.get("character_name"),
                                }
                                for c in (det_movie.get("cast") or [])[:6]
                                if isinstance(c, dict) and c.get("name")
                            ],
                        },
                        "suggestions": suggestions[:4],
                        "parental_guides": parental_guides,
                    }
                except Exception:
                    continue

        return {
            "status": "error",
            "imdb_id": norm_imdb,
            "movie_id": movie_id,
            "details": None,
            "suggestions": [],
            "parental_guides": [],
        }
