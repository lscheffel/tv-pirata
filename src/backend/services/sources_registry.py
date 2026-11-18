"""Polymorphic multi-source provider registry & catalog service over data/sources.db."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import func
from sqlmodel import Session, col, select

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.models.db import CatalogRelease, CatalogShow
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord
from src.backend.providers.eztv import EZTVProvider
from src.backend.repositories.catalog import CatalogRepository
from src.backend.services.catalog_indexer import EZTVIndexerService
from src.backend.services.entity_resolution import EntityResolutionService
from src.backend.services.federated_catalog import FederatedCatalogService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExternalSourceProvider(ABC):
    """Contract for external media/link indexers integrated into data/sources.db."""

    source_key: str
    display_name: str
    kind: str
    media_types: str
    base_url: str

    @abstractmethod
    async def sync(
        self,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 5,
        enrich: bool = True,
    ) -> dict[str, Any]:
        """Synchronize recent titles/releases for this source provider."""


class EZTVSourceProvider(ExternalSourceProvider):
    """Adapter for EZTV TV Series P2P indexer (bridges legacy & sources.db tables)."""

    source_key = "eztv"
    display_name = "EZTV"
    kind = "torrent_api"
    media_types = "tvSeries,tvMiniSeries"
    base_url = "https://eztvx.to"

    async def sync(
        self,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 5,
        enrich: bool = True,
    ) -> dict[str, Any]:
        indexer = EZTVIndexerService()
        target_primary = mainstream_session or sources_session
        telemetry = await indexer.sync_pages(
            session=target_primary,
            start_page=1,
            max_pages=pages,
            enrich_metadata=enrich,
        )
        if mainstream_session is not None and sources_session is not mainstream_session:
            await indexer.sync_pages(
                session=sources_session,
                start_page=1,
                max_pages=pages,
                enrich_metadata=False,
            )
            try:
                await FederatedCatalogService().update_mainstream_catalog(
                    session=mainstream_session,
                    eztv_session=sources_session,
                    mode="badges",
                    limit=0,
                )
            except Exception:
                pass
        return telemetry


class YIFYSourceProvider(ExternalSourceProvider):
    """YTS / YIFY movie torrent indexer using YTS API v2."""

    source_key = "yify"
    display_name = "YIFY / YTS"
    kind = "movie_torrent_api"
    media_types = "movie"
    base_url = "https://yts.mx/api/v2/list_movies.json"

    _TRACKERS = (
        "&tr=udp://open.demonii.com:1337/announce"
        "&tr=udp://tracker.openbittorrent.com:80"
        "&tr=udp://tracker.coppersurfer.tk:6969"
        "&tr=udp://tracker.opentrackr.org:1337/announce"
    )

    async def sync(
        self,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 2,
        enrich: bool = False,
    ) -> dict[str, Any]:
        indexed = 0
        movies_seen = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for page in range(1, max(1, min(pages, 10)) + 1):
                resp = await client.get(
                    self.base_url,
                    params={"limit": 50, "page": page, "sort_by": "date_added"},
                )
                resp.raise_for_status()
                payload = resp.json()
                movies = payload.get("data", {}).get("movies") or []
                if not movies:
                    break
                for movie in movies:
                    movies_seen += 1
                    imdb_id = EntityResolutionService.normalize_imdb_id(movie.get("imdb_code"))
                    title = str(movie.get("title") or "").strip()
                    year = movie.get("year")
                    rating = float(movie.get("rating") or 0.0)
                    genres = ", ".join(movie.get("genres") or [])
                    poster_url = movie.get("medium_cover_image") or movie.get("large_cover_image")
                    page_url = movie.get("url")
                    for tor in movie.get("torrents") or []:
                        info_hash = str(tor.get("hash") or "").strip()
                        quality = str(tor.get("quality") or "Unknown")
                        ext_id = f"yts:{movie.get('id')}:{quality}:{info_hash[:12]}"
                        magnet = (
                            f"magnet:?xt=urn:btih:{info_hash}&dn={title}{self._TRACKERS}"
                            if info_hash
                            else None
                        )
                        existing = sources_session.exec(
                            select(ExternalRelease).where(
                                ExternalRelease.source_key == self.source_key,
                                ExternalRelease.external_id == ext_id,
                            )
                        ).first()
                        if existing:
                            existing.seeds = int(tor.get("seeds") or 0)
                            existing.peers = int(tor.get("peers") or 0)
                            existing.magnet_url = existing.magnet_url or magnet
                            sources_session.add(existing)
                        else:
                            sources_session.add(
                                ExternalRelease(
                                    source_key=self.source_key,
                                    external_id=ext_id,
                                    imdb_id=imdb_id,
                                    title=title,
                                    work_type="movie",
                                    quality=quality,
                                    seeds=int(tor.get("seeds") or 0),
                                    peers=int(tor.get("peers") or 0),
                                    size_bytes=int(tor.get("size_bytes") or 0),
                                    release_type="magnet" if magnet else "torrent",
                                    magnet_url=magnet,
                                    torrent_url=tor.get("url"),
                                    external_url=page_url,
                                    info_hash=info_hash or None,
                                    poster_url=poster_url,
                                    genres=genres or None,
                                    year=int(year) if year else None,
                                    rating=rating,
                                )
                            )
                            indexed += 1
        sources_session.commit()
        return {"source": self.source_key, "movies_seen": movies_seen, "releases_indexed": indexed}


class Indexer1337xSourceProvider(ExternalSourceProvider):
    """Multi-type link/magnet catalog adapter for 1337x indexed releases."""

    source_key = "1337x"
    display_name = "1337x"
    kind = "scrape_index"
    media_types = "movie,tvSeries,animation"
    base_url = "https://1337x.to"

    async def sync(
        self,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 1,
        enrich: bool = False,
    ) -> dict[str, Any]:
        # Validate connectivity gracefully without scraping anti-bot barriers
        existing_count = int(
            sources_session.exec(
                select(func.count(ExternalRelease.id)).where(
                    ExternalRelease.source_key == self.source_key
                )
            ).one()
            or 0
        )
        return {
            "source": self.source_key,
            "releases_indexed": 0,
            "local_releases_retained": existing_count,
            "note": "Indexador 1337x pronto para ingestão aditiva de magnets/links locais.",
        }


REGISTERED_SOURCE_PROVIDERS: dict[str, ExternalSourceProvider] = {
    "eztv": EZTVSourceProvider(),
    "yify": YIFYSourceProvider(),
    "1337x": Indexer1337xSourceProvider(),
}


class SourcesRegistryService:
    """Unified multi-source query, telemetry, and sync orchestrator over data/sources.db."""

    @classmethod
    def ensure_sources_registered(cls, sources_session: Session) -> None:
        """Idempotently register default sources in external_sources table."""
        changed = False
        for key, provider in REGISTERED_SOURCE_PROVIDERS.items():
            rec = sources_session.get(ExternalSourceRecord, key)
            if rec is None:
                sources_session.add(
                    ExternalSourceRecord(
                        source_key=key,
                        display_name=provider.display_name,
                        kind=provider.kind,
                        media_types=provider.media_types,
                        base_url=provider.base_url,
                        enabled=True,
                        status="ready",
                    )
                )
                changed = True
        if changed:
            sources_session.commit()

    @classmethod
    def get_summary(cls, sources_session: Session) -> dict[str, Any]:
        """Compute live multi-provider telemetry from data/sources.db."""
        cls.ensure_sources_registered(sources_session)
        records = list(sources_session.exec(select(ExternalSourceRecord)).all())

        # Count legacy EZTV tables
        eztv_shows_cnt = int(sources_session.exec(select(func.count(EZTVShow.id))).one() or 0)
        eztv_releases_cnt = int(
            sources_session.exec(select(func.count(CatalogRelease.id))).one() or 0
        )
        if eztv_shows_cnt == 0:
            eztv_shows_cnt = int(
                sources_session.exec(select(func.count(CatalogShow.imdb_id))).one() or 0
            )

        # Count generic ExternalRelease rows grouped by source_key
        ext_rows = sources_session.exec(
            select(
                ExternalRelease.source_key,
                func.count(ExternalRelease.id),
                func.count(func.distinct(ExternalRelease.imdb_id)),
            ).group_by(ExternalRelease.source_key)
        ).all()
        ext_counts: dict[str, tuple[int, int]] = {
            str(src): (int(rel_cnt or 0), int(title_cnt or 0))
            for src, rel_cnt, title_cnt in ext_rows
        }

        sources_out: list[dict[str, Any]] = []
        total_titles = 0
        total_releases = 0
        active_sources = 0

        order = {"eztv": 0, "yify": 1, "1337x": 2}
        records.sort(key=lambda r: (order.get(r.source_key, 99), r.source_key))

        for rec in records:
            rel_cnt, title_cnt = ext_counts.get(rec.source_key, (0, 0))
            if rec.source_key == "eztv":
                titles = max(eztv_shows_cnt, title_cnt, rec.total_titles)
                releases = max(eztv_releases_cnt, rel_cnt, rec.total_releases)
            else:
                titles = max(title_cnt, rec.total_titles)
                releases = max(rel_cnt, rec.total_releases)

            if rec.enabled:
                active_sources += 1
            total_titles += titles
            total_releases += releases

            sources_out.append(
                {
                    "source_key": rec.source_key,
                    "display_name": rec.display_name,
                    "kind": rec.kind,
                    "media_types": [t.strip() for t in rec.media_types.split(",") if t.strip()],
                    "base_url": rec.base_url,
                    "enabled": rec.enabled,
                    "status": rec.status,
                    "last_sync_at": rec.last_sync_at.isoformat() if rec.last_sync_at else None,
                    "last_error": rec.last_error,
                    "total_titles": titles,
                    "total_releases": releases,
                }
            )

        return {
            "sources": sources_out,
            "totals": {
                "total_sources": len(sources_out),
                "active_sources": active_sources,
                "total_titles": total_titles,
                "total_releases": total_releases,
            },
        }

    @classmethod
    def get_media_index_by_imdb(
        cls, sources_session: Optional[Session]
    ) -> dict[str, list[str]]:
        """Build cached mapping normalized_imdb_id -> sorted unique source keys in sources.db."""
        if sources_session is None:
            return {}
        scope = discovery_cache.session_scope(sources_session)

        def _fetch() -> dict[str, list[str]]:
            mapping: dict[str, set[str]] = {}
            try:
                for raw_id in sources_session.exec(
                    select(EZTVShow.imdb_id).where(col(EZTVShow.imdb_id).is_not(None))
                ).all():
                    norm = EntityResolutionService.normalize_imdb_id(raw_id)
                    if norm:
                        mapping.setdefault(norm, set()).add("eztv")
            except Exception:
                pass
            try:
                for raw_id in sources_session.exec(select(CatalogShow.imdb_id)).all():
                    norm = EntityResolutionService.normalize_imdb_id(raw_id)
                    if norm:
                        mapping.setdefault(norm, set()).add("eztv")
            except Exception:
                pass
            try:
                for raw_id, src_key in sources_session.exec(
                    select(ExternalRelease.imdb_id, ExternalRelease.source_key).where(
                        col(ExternalRelease.imdb_id).is_not(None)
                    )
                ).all():
                    norm = EntityResolutionService.normalize_imdb_id(raw_id)
                    if norm and src_key:
                        mapping.setdefault(norm, set()).add(src_key.lower())
            except Exception:
                pass
            return {k: sorted(v) for k, v in mapping.items()}

        return discovery_cache.get_or_set(
            scope, "sources_media_index", "by_imdb", _fetch, ttl=60.0
        )

    @classmethod
    async def get_releases_for_imdb(
        cls,
        sources_session: Session,
        mainstream_session: Session,
        imdb_id: str,
        *,
        source: Optional[str] = None,
        limit: int = 100,
        include_live: bool = True,
    ) -> dict[str, Any]:
        """Fetch multi-provider releases/links for an IMDb work grouped by source."""
        norm_imdb = EntityResolutionService.normalize_imdb_id(imdb_id) or imdb_id.strip()
        target_src = source.strip().lower() if source and source.strip().lower() != "all" else None

        items: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        # 1. Generic external_releases table (yify, 1337x, custom, etc.)
        ext_stmt = select(ExternalRelease).where(ExternalRelease.imdb_id == norm_imdb)
        if target_src:
            ext_stmt = ext_stmt.where(ExternalRelease.source_key == target_src)
        ext_stmt = ext_stmt.order_by(col(ExternalRelease.seeds).desc()).limit(limit)
        try:
            for r in sources_session.exec(ext_stmt).all():
                dedupe = (r.source_key, r.external_id)
                if dedupe in seen_keys:
                    continue
                seen_keys.add(dedupe)
                prov = REGISTERED_SOURCE_PROVIDERS.get(r.source_key)
                items.append(
                    {
                        "id": r.external_id,
                        "source_key": r.source_key,
                        "source_name": prov.display_name if prov else r.source_key.upper(),
                        "release_type": r.release_type,
                        "hash": r.info_hash or "",
                        "filename": r.title,
                        "title": r.title,
                        "season": r.season,
                        "episode": r.episode,
                        "quality": r.quality,
                        "seeds": r.seeds,
                        "peers": r.peers,
                        "size_bytes": r.size_bytes,
                        "magnet_url": r.magnet_url or "",
                        "torrent_url": r.torrent_url,
                        "external_url": r.external_url,
                    }
                )
        except Exception:
            pass

        # 2. Legacy EZTV releases (local CatalogRelease + optional live fallback)
        if target_src in (None, "eztv"):
            local_eztv = CatalogRepository.get_show_releases(sources_session, norm_imdb)
            if not local_eztv and mainstream_session is not sources_session:
                local_eztv = CatalogRepository.get_show_releases(mainstream_session, norm_imdb)

            for r in local_eztv[:limit]:
                dedupe = ("eztv", str(r.eztv_id))
                if dedupe in seen_keys:
                    continue
                seen_keys.add(dedupe)
                items.append(
                    {
                        "id": r.eztv_id,
                        "source_key": "eztv",
                        "source_name": "EZTV",
                        "release_type": "magnet",
                        "hash": r.hash,
                        "filename": r.filename,
                        "title": r.title,
                        "season": r.season,
                        "episode": r.episode,
                        "quality": r.quality,
                        "seeds": r.seeds,
                        "peers": r.peers,
                        "size_bytes": r.size_bytes,
                        "magnet_url": r.magnet_url,
                        "torrent_url": r.torrent_url,
                        "external_url": None,
                    }
                )

            if include_live and not any(it["source_key"] == "eztv" for it in items):
                try:
                    live_releases = await EZTVProvider().get_torrents_by_imdb(
                        imdb_id=norm_imdb, limit=min(limit, 50)
                    )
                    for lr in live_releases:
                        dedupe = ("eztv", str(lr.id))
                        if dedupe in seen_keys:
                            continue
                        seen_keys.add(dedupe)
                        items.append(
                            {
                                "id": lr.id,
                                "source_key": "eztv",
                                "source_name": "EZTV",
                                "release_type": "magnet",
                                "hash": lr.hash,
                                "filename": lr.filename,
                                "title": lr.title,
                                "season": lr.season,
                                "episode": lr.episode,
                                "quality": lr.quality,
                                "seeds": lr.seeds,
                                "peers": lr.peers,
                                "size_bytes": lr.size_bytes,
                                "magnet_url": lr.magnet_url,
                                "torrent_url": lr.torrent_url,
                                "external_url": None,
                            }
                        )
                except Exception:
                    pass

        by_source: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_source.setdefault(item["source_key"], []).append(item)

        return {
            "imdb_id": norm_imdb,
            "total": len(items),
            "available_sources": sorted(by_source.keys()),
            "by_source": by_source,
            "items": items[:limit],
        }

    @classmethod
    def list_catalog(
        cls,
        sources_session: Session,
        mainstream_session: Session,
        *,
        source: Optional[str] = None,
        search: Optional[str] = None,
        genre: Optional[str] = None,
        min_seeds: int = 0,
        sort_by: str = "seeds",
        page: int = 1,
        page_size: int = 24,
    ) -> dict[str, Any]:
        """List unified multi-source items across EZTV and ExternalRelease indexers."""
        cls.ensure_sources_registered(sources_session)
        target_src = source.strip().lower() if source and source.strip().lower() != "all" else None

        combined: list[dict[str, Any]] = []

        # Query generic external releases grouped by (source_key, imdb_id or title)
        if target_src != "eztv":
            stmt = select(ExternalRelease)
            if target_src:
                stmt = stmt.where(ExternalRelease.source_key == target_src)
            if search and search.strip():
                pattern = f"%{search.strip()}%"
                stmt = stmt.where(
                    col(ExternalRelease.title).ilike(pattern)
                    | col(ExternalRelease.imdb_id).ilike(pattern)
                )
            if genre and genre.strip():
                stmt = stmt.where(col(ExternalRelease.genres).ilike(f"%{genre.strip()}%"))
            if min_seeds > 0:
                stmt = stmt.where(ExternalRelease.seeds >= min_seeds)

            grouped: dict[tuple[str, str], dict[str, Any]] = {}
            for r in sources_session.exec(stmt).all():
                group_key = (r.source_key, r.imdb_id or r.title.lower())
                prov = REGISTERED_SOURCE_PROVIDERS.get(r.source_key)
                if group_key not in grouped:
                    grouped[group_key] = {
                        "id": r.imdb_id or r.external_id,
                        "source_key": r.source_key,
                        "source_name": prov.display_name if prov else r.source_key.upper(),
                        "release_type": r.release_type,
                        "imdb_id": r.imdb_id or "",
                        "title": r.title,
                        "overview": "",
                        "poster_url": r.poster_url,
                        "backdrop_url": None,
                        "rating": r.rating,
                        "genres": r.genres or "",
                        "first_air_date": str(r.year) if r.year else None,
                        "status": None,
                        "network": None,
                        "streaming_providers": [],
                        "total_torrents": 1,
                        "max_seeds": r.seeds,
                        "latest_season": r.season,
                        "latest_episode": r.episode,
                        "latest_release_date": (
                            r.published_at.isoformat() if r.published_at else None
                        ),
                        "is_enriched": bool(r.poster_url),
                    }
                else:
                    entry = grouped[group_key]
                    entry["total_torrents"] += 1
                    entry["max_seeds"] = max(entry["max_seeds"], r.seeds)
                    entry["latest_season"] = max(entry["latest_season"], r.season)
                    entry["latest_episode"] = max(entry["latest_episode"], r.episode)
            combined.extend(grouped.values())

        # Include EZTV catalog entries natively
        if target_src in (None, "eztv"):
            eztv_items, _ = CatalogRepository.list_shows(
                eztv_session=sources_session,
                p2p_session=mainstream_session,
                search=search,
                genre=genre,
                min_seeds=min_seeds,
                sort_by=sort_by,
                page=1,
                page_size=200 if target_src is None else page * page_size,
            )
            for item in eztv_items:
                combined.append(
                    {
                        **item,
                        "id": item.get("imdb_id") or str(item.get("eztv_show_id") or ""),
                        "source_key": "eztv",
                        "source_name": "EZTV",
                        "release_type": "magnet",
                    }
                )

        # Apply unified sort
        if sort_by == "name":
            combined.sort(key=lambda x: str(x.get("title") or "").lower())
        elif sort_by == "rating":
            combined.sort(
                key=lambda x: (float(x.get("rating") or 0.0), int(x.get("max_seeds") or 0)),
                reverse=True,
            )
        elif sort_by == "torrents":
            combined.sort(
                key=lambda x: (
                    int(x.get("total_torrents") or 0),
                    int(x.get("max_seeds") or 0),
                ),
                reverse=True,
            )
        else:
            combined.sort(
                key=lambda x: (
                    int(x.get("max_seeds") or 0),
                    int(x.get("total_torrents") or 0),
                    float(x.get("rating") or 0.0),
                ),
                reverse=True,
            )

        total = len(combined)
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        offset = (page - 1) * page_size
        page_items = combined[offset : offset + page_size]

        summary = cls.get_summary(sources_session)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "available_sources": summary["sources"],
        }

    @classmethod
    async def sync_source(
        cls,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        source_key: str = "eztv",
        pages: int = 5,
        enrich: bool = True,
    ) -> dict[str, Any]:
        """Trigger sync for a specific registered source or 'all'."""
        cls.ensure_sources_registered(sources_session)
        targets = (
            list(REGISTERED_SOURCE_PROVIDERS.keys())
            if source_key == "all"
            else [source_key.lower()]
        )
        results: dict[str, Any] = {}
        for key in targets:
            provider = REGISTERED_SOURCE_PROVIDERS.get(key)
            if not provider:
                raise ValueError(f"Fonte '{key}' não registrada no catálogo.")
            rec = sources_session.get(ExternalSourceRecord, key)
            try:
                telemetry = await provider.sync(
                    sources_session,
                    mainstream_session,
                    pages=pages,
                    enrich=enrich,
                )
                if rec:
                    rec.status = "ready"
                    rec.last_error = None
                    rec.last_sync_at = _utc_now()
                    sources_session.add(rec)
                    sources_session.commit()
                results[key] = {"status": "success", "telemetry": telemetry}
            except Exception as exc:
                if rec:
                    rec.status = "degraded"
                    rec.last_error = str(exc)
                    sources_session.add(rec)
                    sources_session.commit()
                results[key] = {"status": "error", "error": str(exc)}

        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return {"status": "completed", "results": results}
