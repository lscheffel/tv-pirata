"""YIFY / YTS v2 movie torrent adapter with mirror rotation and on-demand search."""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord
from src.backend.providers.sources.base import (
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceQueryContext,
    compute_title_match_confidence,
    is_antibot_challenge,
    register_source_adapter,
    utc_now,
    validate_safe_url,
)
from src.backend.services.entity_resolution import EntityResolutionService

_TRACKERS = (
    "&tr=udp://open.demonii.com:1337/announce"
    "&tr=udp://tracker.openbittorrent.com:80"
    "&tr=udp://tracker.coppersurfer.tk:6969"
    "&tr=udp://tracker.opentrackr.org:1337/announce"
)


class YIFYAdapterConfig(BaseModel):
    """Configuration schema for YIFY / YTS JSON API v2."""

    base_url: str = Field(
        default="https://yts.mx/api/v2/list_movies.json",
        title="Endpoint YTS API v2",
    )
    mirrors: list[str] = Field(
        default_factory=lambda: [
            "https://yts.lt/api/v2/list_movies.json",
            "https://yts.am/api/v2/list_movies.json",
        ],
        title="Mirrors YTS Alternativos",
    )
    timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


@register_source_adapter
class YIFYSourceAdapter(BaseSourceAdapter):
    """YIFY / YTS movie indexer supporting both batch sync and on-demand lookup."""

    adapter_key = "yify"
    display_name = "YIFY / YTS (Filmes P2P)"
    description = (
        "API JSON v2 oficial do YTS para filmes em 720p, 1080p e 2160p/4K com rotação de mirrors."
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
        urls = [cfg.base_url, *cfg.mirrors]
        out: list[str] = []
        for u in urls:
            safe = validate_safe_url(u, ("http", "https"))
            if safe and safe not in out:
                out.append(safe)
        return out or ["https://yts.mx/api/v2/list_movies.json"]

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
                quality = str(tor.get("quality") or "Unknown")
                ext_id = f"yts:{movie.get('id')}:{quality}:{info_hash[:12]}"
                magnet = (
                    validate_safe_url(
                        f"magnet:?xt=urn:btih:{info_hash}&dn={title}{_TRACKERS}",
                        ("magnet",),
                    )
                    if info_hash
                    else None
                )
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

    async def sync(
        self,
        instance: ExternalSourceRecord,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 2,
        enrich: bool = False,
    ) -> dict[str, Any]:
        cfg = self._parse_cfg(instance)
        endpoints = self._candidate_endpoints(cfg)
        indexed = 0
        movies_seen = 0
        last_err: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            for endpoint in endpoints:
                try:
                    for page in range(1, max(1, min(pages, 10)) + 1):
                        resp = await client.get(
                            endpoint,
                            params={"limit": 50, "page": page, "sort_by": "date_added"},
                        )
                        resp.raise_for_status()
                        payload = resp.json()
                        movies = payload.get("data", {}).get("movies") or []
                        if not movies:
                            break
                        movies_seen += len(movies)
                        for cand in self._movies_to_candidates(movies):
                            existing = sources_session.exec(
                                select(ExternalRelease).where(
                                    ExternalRelease.source_key == instance.source_key,
                                    ExternalRelease.external_id == cand.external_id,
                                )
                            ).first()
                            if existing:
                                existing.seeds = cand.seeds
                                existing.peers = cand.peers
                                existing.magnet_url = existing.magnet_url or cand.magnet_url
                                existing.last_checked_at = utc_now()
                                sources_session.add(existing)
                            else:
                                sources_session.add(
                                    ExternalRelease(
                                        source_key=instance.source_key,
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
                                        last_checked_at=utc_now(),
                                    )
                                )
                                indexed += 1
                    sources_session.commit()
                    return {
                        "source": instance.source_key,
                        "endpoint": endpoint,
                        "movies_seen": movies_seen,
                        "releases_indexed": indexed,
                    }
                except Exception as exc:
                    last_err = exc
                    continue

        if last_err:
            raise last_err
        return {"source": instance.source_key, "movies_seen": 0, "releases_indexed": 0}

    async def search(
        self,
        instance: ExternalSourceRecord,
        query_ctx: SourceQueryContext,
        sources_session: Optional[Session] = None,
        mainstream_session: Optional[Session] = None,
    ) -> AdapterSearchOutcome:
        cfg = self._parse_cfg(instance)
        endpoints = self._candidate_endpoints(cfg)
        q_term = (
            query_ctx.custom_query
            or EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
            or query_ctx.original_title
            or query_ctx.title
        )
        last_error_msg: Optional[str] = None

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            for endpoint in endpoints:
                try:
                    resp = await client.get(
                        endpoint,
                        params={"query_term": q_term, "limit": min(query_ctx.limit, 50)},
                    )
                    if is_antibot_challenge(resp.status_code, resp.text, dict(resp.headers)):
                        last_error_msg = f"Anti-bot Challenge em {endpoint}"
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    movies = payload.get("data", {}).get("movies") or []
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
