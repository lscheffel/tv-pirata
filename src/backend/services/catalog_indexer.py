"""EZTV catalog ingestion and indexing service."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, select

from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.db import CatalogRelease, CatalogShow, ShowRecord
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease
from src.backend.models.unified import TorrentRelease
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider
from src.backend.repositories.catalog import CatalogRepository
from src.backend.repositories.notification import NotificationRepository

logger = logging.getLogger(__name__)


class EZTVIndexerService:
    """Service to ingest and index EZTV torrent distributions into the local catalog."""

    def __init__(
        self,
        base_url: str = "https://eztvx.to/api",
        client: Optional[httpx.AsyncClient] = None,
        tvmaze_provider: Optional[TVMazeProvider] = None,
        tmdb_provider: Optional[TMDBProvider] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client
        self.tvmaze = tvmaze_provider or TVMazeProvider()
        self.tmdb = tmdb_provider or TMDBProvider()

    @staticmethod
    def normalize_imdb_id(raw_id: str | int | None) -> Optional[str]:
        """Normalize numeric or prefixed IMDB ID to canonical 'tt' format."""
        if not raw_id:
            return None
        cleaned = str(raw_id).strip().lower()
        if not cleaned or cleaned == "0":
            return None
        if cleaned.startswith("tt"):
            return cleaned
        # Format numeric string with minimum 7 digits
        digits = cleaned.lstrip("tt")
        if not digits.isdigit():
            return None
        return f"tt{digits.zfill(7)}"

    @staticmethod
    def extract_clean_show_title(raw_title: str, raw_filename: str = "") -> str:
        """Extract sanitized show name from release title or filename."""
        source = raw_title or raw_filename or "Show Desconhecido"
        # Replace dots and underscores with spaces
        clean = re.sub(r"[._]", " ", source).strip()

        # Regex targeting standard scene naming delimiters (S01E02, 1x02, Resolution, Sources)
        pattern = re.compile(
            r"^(.*?)(?:\s+(?:s\d{1,2}|season|\d{1,2}x\d{1,2}|1080p|720p|480p|2160p|4k|hdtv|web-dl|webrip|web|x264|x265|hevc|amzn))",
            re.IGNORECASE,
        )
        match = pattern.search(clean)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate

        # Fallback: strip standard trailing release group tags like [EZTV] or [EZTVx.to]
        clean = re.sub(r"\[.*?\]", "", clean)
        clean = re.sub(r"\b(?:EZTV|mSD|AFG|MeGusta|SYNCOPY)\b", "", clean, flags=re.IGNORECASE)
        return clean.strip() or source

    async def fetch_page(self, page: int = 1, limit: int = 100) -> list[dict]:
        """Fetch a single page of releases from EZTV API with 429/5xx backoff."""
        url = f"{self.base_url}/get-torrents"
        params = {"page": page, "limit": limit}
        client = self._client or httpx.AsyncClient(timeout=15.0)
        should_close = self._client is None

        try:
            for attempt in range(3):
                response = await client.get(url, params=params)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(0.6 * (2**attempt))
                    continue
                response.raise_for_status()
                data = response.json()
                return data.get("torrents", [])
            return []
        except Exception as exc:
            logger.warning("Error fetching EZTV page %s: %s", page, exc)
            return []
        finally:
            if should_close:
                await client.aclose()

    async def enrich_show_metadata(self, imdb_id: str) -> Optional[dict]:
        """Fetch poster, backdrop, overview, genres and rating via TVMaze / TMDB."""
        # 1. Primary: TVMaze (Token-free, fast lookup)
        try:
            tvmaze_show = await self.tvmaze.lookup_by_imdb(imdb_id)
            if tvmaze_show and tvmaze_show.poster_url:
                return {
                    "title": tvmaze_show.title,
                    "overview": tvmaze_show.overview,
                    "poster_url": tvmaze_show.poster_url,
                    "backdrop_url": tvmaze_show.backdrop_url,
                    "rating": tvmaze_show.rating,
                    "genres": ", ".join(tvmaze_show.genres),
                    "first_air_date": tvmaze_show.first_air_date,
                    "status": tvmaze_show.status,
                }
        except Exception as exc:
            logger.debug("TVMaze lookup failed for %s: %s", imdb_id, exc)

        # 2. Secondary: TMDB
        try:
            tmdb_show = await self.tmdb.lookup_by_imdb(imdb_id)
            if tmdb_show:
                return {
                    "title": tmdb_show.title,
                    "overview": tmdb_show.overview,
                    "poster_url": tmdb_show.poster_url,
                    "backdrop_url": tmdb_show.backdrop_url,
                    "rating": tmdb_show.rating,
                    "genres": ", ".join(tmdb_show.genres),
                    "first_air_date": tmdb_show.first_air_date,
                    "status": tmdb_show.status,
                }
        except Exception as exc:
            logger.debug("TMDB lookup failed for %s: %s", imdb_id, exc)

        return None

    async def sync_pages(
        self,
        session: Session,
        start_page: int = 1,
        max_pages: int = 5,
        enrich_metadata: bool = True,
        *,
        stop_on_known_pages: int = 0,
        request_delay: float = 0.0,
        mainstream_session: Optional[Session] = None,
    ) -> dict:
        """Synchronize a range of pages from EZTV with dual-write and optional watermark stop."""
        torrents_indexed = 0
        shows_created = 0
        shows_updated = 0
        shows_enriched = 0
        pages_processed = 0
        consecutive_known_pages = 0

        affected_imdb_ids: set[str] = set()
        now_utc = datetime.now(timezone.utc)
        bind = session.get_bind()
        has_ext_table = bool(bind is not None and sa_inspect(bind).has_table("external_releases"))
        has_eztv_show_table = False
        if bind is not None and sa_inspect(bind).has_table("shows"):
            show_cols = {c["name"] for c in sa_inspect(bind).get_columns("shows")}
            has_eztv_show_table = "slug" in show_cols and "id" in show_cols

        for idx, page in enumerate(range(start_page, start_page + max_pages)):
            if idx > 0 and request_delay > 0:
                await asyncio.sleep(request_delay)
            raw_torrents = await self.fetch_page(page=page, limit=100)
            if not raw_torrents:
                break
            pages_processed += 1
            page_new_torrents = 0

            # Preload existing ExternalRelease keys for this page
            page_ext_ids = [
                str(int(it.get("id", 0))) for it in raw_torrents if int(it.get("id", 0)) > 0
            ]
            existing_ext_map: dict[str, ExternalRelease] = {}
            if has_ext_table and page_ext_ids:
                try:
                    ext_rows = session.exec(
                        select(ExternalRelease).where(
                            ExternalRelease.source_key == "eztv",
                            ExternalRelease.external_id.in_(page_ext_ids),
                        )
                    ).all()
                    existing_ext_map = {r.external_id: r for r in ext_rows}
                except Exception:
                    existing_ext_map = {}

            for item in raw_torrents:
                norm_imdb = self.normalize_imdb_id(item.get("imdb_id"))
                if not norm_imdb:
                    continue

                affected_imdb_ids.add(norm_imdb)
                eztv_id = int(item.get("id", 0))
                if eztv_id == 0:
                    continue

                parsed = TorrentRelease.from_eztv(item)
                existing_rel = session.exec(
                    select(CatalogRelease).where(CatalogRelease.eztv_id == eztv_id)
                ).first()
                rel_timestamp = item.get("date_released_unix", 0)

                if existing_rel:
                    existing_rel.seeds = parsed.seeds
                    existing_rel.peers = parsed.peers
                    existing_rel.magnet_url = parsed.magnet_url
                else:
                    new_rel = CatalogRelease(
                        eztv_id=eztv_id,
                        hash=parsed.hash,
                        imdb_id=norm_imdb,
                        title=parsed.title,
                        filename=parsed.filename,
                        season=parsed.season,
                        episode=parsed.episode,
                        quality=parsed.quality,
                        seeds=parsed.seeds,
                        peers=parsed.peers,
                        size_bytes=parsed.size_bytes,
                        magnet_url=parsed.magnet_url,
                        torrent_url=parsed.torrent_url,
                        date_released_unix=int(rel_timestamp or 0),
                    )
                    session.add(new_rel)
                    torrents_indexed += 1
                    page_new_torrents += 1

                # Dual-write idempotente para ExternalRelease (source_key="eztv")
                if has_ext_table:
                    ext_key = str(eztv_id)
                    ext_rec = existing_ext_map.get(ext_key)
                    if ext_rec is not None:
                        ext_rec.seeds = parsed.seeds
                        ext_rec.peers = parsed.peers
                        ext_rec.magnet_url = parsed.magnet_url
                        ext_rec.last_checked_at = now_utc
                        session.add(ext_rec)
                    else:
                        new_ext = ExternalRelease(
                            source_key="eztv",
                            external_id=ext_key,
                            imdb_id=norm_imdb,
                            title=parsed.title or parsed.filename,
                            work_type="tvSeries",
                            season=parsed.season,
                            episode=parsed.episode,
                            quality=parsed.quality,
                            seeds=parsed.seeds,
                            peers=parsed.peers,
                            size_bytes=parsed.size_bytes,
                            release_type="magnet" if parsed.magnet_url else "torrent",
                            magnet_url=parsed.magnet_url,
                            torrent_url=parsed.torrent_url,
                            info_hash=parsed.hash,
                            matched_by="eztv_api",
                            match_confidence=1.0,
                            created_at=now_utc,
                            last_checked_at=now_utc,
                        )
                        session.add(new_ext)
                        existing_ext_map[ext_key] = new_ext

                # Check/Create CatalogShow
                clean_name = self.extract_clean_show_title(parsed.title, parsed.filename)
                catalog_show = session.get(CatalogShow, norm_imdb)
                if not catalog_show:
                    catalog_show = CatalogShow(
                        imdb_id=norm_imdb,
                        title=clean_name,
                        total_torrents=1,
                        max_seeds=parsed.seeds,
                        latest_season=parsed.season,
                        latest_episode=parsed.episode,
                        is_enriched=False,
                    )
                    session.add(catalog_show)
                    shows_created += 1
                else:
                    shows_updated += 1

                # Ensure EZTVShow exists in sources.db shows table
                if has_eztv_show_table:
                    ez_show = session.exec(
                        select(EZTVShow).where(EZTVShow.imdb_id == norm_imdb)
                    ).first()
                    if ez_show is None:
                        imdb_digits = norm_imdb.lstrip("t")
                        ez_id = int(imdb_digits) if imdb_digits.isdigit() else None
                        if ez_id and session.get(EZTVShow, ez_id) is None:
                            session.add(
                                EZTVShow(
                                    id=ez_id,
                                    imdb_id=norm_imdb,
                                    name=clean_name,
                                    updated_at=now_utc.isoformat(),
                                )
                            )

            session.commit()

            if stop_on_known_pages > 0:
                if page_new_torrents == 0:
                    consecutive_known_pages += 1
                    if consecutive_known_pages >= stop_on_known_pages:
                        break
                else:
                    consecutive_known_pages = 0

        # Update aggregated metrics for affected shows
        for imdb_id in affected_imdb_ids:
            show = session.get(CatalogShow, imdb_id)
            if not show:
                continue

            releases = session.exec(
                select(CatalogRelease).where(CatalogRelease.imdb_id == imdb_id)
            ).all()

            if releases:
                show.total_torrents = len(releases)
                show.max_seeds = max(r.seeds for r in releases)
                latest_season = max(r.season for r in releases)
                season_releases = [r for r in releases if r.season == latest_season]
                latest_episode = max((r.episode for r in season_releases), default=0)
                show.latest_season = latest_season
                show.latest_episode = latest_episode

                latest_unix = max((r.date_released_unix for r in releases), default=0)
                if latest_unix > 0:
                    show.latest_release_date = datetime.fromtimestamp(latest_unix, tz=timezone.utc)

            show.last_synced_at = datetime.now(timezone.utc)
            session.add(show)

        session.commit()

        # Propagate has_eztv=True to mainstream.db when mainstream_session is supplied
        if mainstream_session is not None and affected_imdb_ids:
            try:
                aff_list = list(affected_imdb_ids)
                for i in range(0, len(aff_list), 400):
                    chunk = aff_list[i : i + 400]
                    rows = mainstream_session.exec(
                        select(IMDbCatalogShow).where(
                            IMDbCatalogShow.imdb_id.in_(chunk),
                            IMDbCatalogShow.has_eztv.is_(False),
                        )
                    ).all()
                    for ms_row in rows:
                        ms_row.has_eztv = True
                        mainstream_session.add(ms_row)
                mainstream_session.commit()
            except Exception as exc:
                logger.warning("Failed to propagate has_eztv to mainstream.db: %s", exc)

        # High-throughput Concurrent Enrichment for Unenriched Shows
        if enrich_metadata:
            unenriched_ids = [
                imdb_id
                for imdb_id in affected_imdb_ids
                if (s := session.get(CatalogShow, imdb_id)) and not s.is_enriched
            ]

            if unenriched_ids:
                sem = asyncio.Semaphore(6)

                async def fetch_enrichment(target_id: str):
                    async with sem:
                        res = await self.enrich_show_metadata(target_id)
                        return target_id, res

                tasks = [fetch_enrichment(i) for i in unenriched_ids]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for outcome in results:
                    if isinstance(outcome, tuple) and outcome[1]:
                        target_id, meta = outcome
                        target_show = session.get(CatalogShow, target_id)
                        if target_show:
                            target_show.title = meta.get("title") or target_show.title
                            target_show.overview = meta.get("overview") or target_show.overview
                            target_show.poster_url = meta.get("poster_url")
                            target_show.backdrop_url = meta.get("backdrop_url")
                            target_show.rating = meta.get("rating", 0.0)
                            target_show.genres = meta.get("genres", "")
                            target_show.first_air_date = meta.get("first_air_date")
                            target_show.status = meta.get("status")
                            target_show.is_enriched = True
                            shows_enriched += 1
                            session.add(target_show)

                session.commit()

        return {
            "pages_processed": pages_processed,
            "torrents_indexed": torrents_indexed,
            "shows_created": shows_created,
            "shows_updated": shows_updated,
            "shows_enriched": shows_enriched,
            "affected_shows": len(affected_imdb_ids),
            "affected_imdb_ids": sorted(affected_imdb_ids),
        }

    async def sync_pages_until_watermark(
        self,
        session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        max_pages: int = 25,
        stop_on_known_pages: int = 2,
        request_delay: float = 0.35,
    ) -> dict:
        """Scan recent EZTV pages until 2 consecutive known pages or max_pages ceiling."""
        return await self.sync_pages(
            session=session,
            start_page=1,
            max_pages=max_pages,
            enrich_metadata=False,
            stop_on_known_pages=stop_on_known_pages,
            request_delay=request_delay,
            mainstream_session=mainstream_session,
        )

    async def sync_library_shows_via_eztv(
        self,
        sources_session: Session,
        mainstream_session: Session,
        *,
        offset: int = 0,
        limit: int = 12,
    ) -> dict:
        """Sweep personal library ShowRecord rows against EZTV by imdb_id to backfill episodes."""
        all_lib = list(
            mainstream_session.exec(select(ShowRecord).where(ShowRecord.imdb_id.is_not(None))).all()
        )
        total = len(all_lib)
        batch = all_lib[offset : offset + limit]
        torrents_indexed = 0
        now_utc = datetime.now(timezone.utc)
        client = self._client or httpx.AsyncClient(timeout=12.0)
        should_close = self._client is None
        try:
            for show in batch:
                norm_imdb = self.normalize_imdb_id(show.imdb_id)
                if not norm_imdb:
                    continue
                digits = norm_imdb.lstrip("t")
                try:
                    resp = await client.get(
                        f"{self.base_url}/get-torrents",
                        params={"imdb_id": digits, "limit": 100, "page": 1},
                    )
                    if resp.status_code != 200:
                        continue
                    torrents = resp.json().get("torrents") or []
                except Exception:
                    continue
                for item in torrents:
                    eztv_id = int(item.get("id", 0))
                    if eztv_id == 0:
                        continue
                    parsed = TorrentRelease.from_eztv(item)
                    if not sources_session.exec(
                        select(CatalogRelease).where(CatalogRelease.eztv_id == eztv_id)
                    ).first():
                        sources_session.add(
                            CatalogRelease(
                                eztv_id=eztv_id,
                                hash=parsed.hash,
                                imdb_id=norm_imdb,
                                title=parsed.title,
                                filename=parsed.filename,
                                season=parsed.season,
                                episode=parsed.episode,
                                quality=parsed.quality,
                                seeds=parsed.seeds,
                                peers=parsed.peers,
                                size_bytes=parsed.size_bytes,
                                magnet_url=parsed.magnet_url,
                                torrent_url=parsed.torrent_url,
                                date_released_unix=int(item.get("date_released_unix") or 0),
                            )
                        )
                        torrents_indexed += 1
                    ext_key = str(eztv_id)
                    if not sources_session.exec(
                        select(ExternalRelease).where(
                            ExternalRelease.source_key == "eztv",
                            ExternalRelease.external_id == ext_key,
                        )
                    ).first():
                        sources_session.add(
                            ExternalRelease(
                                source_key="eztv",
                                external_id=ext_key,
                                imdb_id=norm_imdb,
                                title=parsed.title or parsed.filename,
                                work_type="tvSeries",
                                season=parsed.season,
                                episode=parsed.episode,
                                quality=parsed.quality,
                                seeds=parsed.seeds,
                                peers=parsed.peers,
                                size_bytes=parsed.size_bytes,
                                release_type="magnet" if parsed.magnet_url else "torrent",
                                magnet_url=parsed.magnet_url,
                                torrent_url=parsed.torrent_url,
                                info_hash=parsed.hash,
                                matched_by="eztv_api",
                                match_confidence=1.0,
                                created_at=now_utc,
                                last_checked_at=now_utc,
                            )
                        )
                sources_session.commit()
        finally:
            if should_close:
                await client.aclose()
        next_offset = offset + len(batch)
        return {
            "titles_scanned": len(batch),
            "releases_indexed": torrents_indexed,
            "next_offset": next_offset,
            "exhausted": next_offset >= total,
            "total": total,
        }

    async def enrich_pending_shows(self, session: Session, limit: int = 100) -> int:
        """Enrich existing catalog shows that have not yet been enriched."""
        query = select(CatalogShow).where(CatalogShow.is_enriched.is_(False)).limit(limit)
        pending = list(session.exec(query).all())
        if not pending:
            return 0

        sem = asyncio.Semaphore(6)

        async def fetch_enrichment(target_id: str):
            async with sem:
                res = await self.enrich_show_metadata(target_id)
                return target_id, res

        tasks = [fetch_enrichment(s.imdb_id) for s in pending]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        enriched_count = 0
        for outcome in results:
            if isinstance(outcome, tuple) and outcome[1]:
                target_id, meta = outcome
                target_show = session.get(CatalogShow, target_id)
                if target_show:
                    target_show.title = meta.get("title") or target_show.title
                    target_show.overview = meta.get("overview") or target_show.overview
                    target_show.poster_url = meta.get("poster_url")
                    target_show.backdrop_url = meta.get("backdrop_url")
                    target_show.rating = meta.get("rating", 0.0)
                    target_show.genres = meta.get("genres", "")
                    target_show.first_air_date = meta.get("first_air_date")
                    target_show.status = meta.get("status")
                    target_show.is_enriched = True
                    enriched_count += 1
                    session.add(target_show)

        session.commit()
        return enriched_count

    async def sync_and_reconcile_recent(
        self,
        session: Session,
        sources_session: Optional[Session] = None,
    ) -> dict:
        """Fetch latest EZTV page and reconcile matching releases with user's library."""
        raw_torrents = await self.fetch_page(page=1, limit=100)
        if not raw_torrents:
            return {
                "releases_inspected": 0,
                "notifications_created": 0,
                "torrents_indexed": 0,
            }

        # Index page 1 into sources.db (when provided) or session fallback
        target_cat_session = sources_session or session
        telemetry = await self.sync_pages(
            session=target_cat_session,
            start_page=1,
            max_pages=1,
            enrich_metadata=True,
            mainstream_session=session if sources_session is not None else None,
        )

        # Build lookup table of user's saved shows
        saved_shows = session.exec(select(ShowRecord)).all()
        saved_map: dict[str, ShowRecord] = {}
        for s in saved_shows:
            if s.imdb_id:
                clean_imdb = CatalogRepository.normalize_imdb_id(s.imdb_id)
                saved_map[clean_imdb] = s

        notifications_created = 0

        for item in raw_torrents:
            norm_imdb = self.normalize_imdb_id(item.get("imdb_id"))
            if not norm_imdb or norm_imdb not in saved_map:
                continue

            target_show = saved_map[norm_imdb]
            parsed = TorrentRelease.from_eztv(item)

            if parsed.season > 0 and parsed.episode > 0:
                notif = NotificationRepository.create_notification(
                    session=session,
                    show_id=target_show.id,
                    imdb_id=norm_imdb,
                    show_title=target_show.title,
                    season=parsed.season,
                    episode=parsed.episode,
                    release_title=parsed.title,
                    quality=parsed.quality,
                    seeds=parsed.seeds,
                    magnet_url=parsed.magnet_url,
                )
                if notif:
                    notifications_created += 1

        return {
            "releases_inspected": len(raw_torrents),
            "notifications_created": notifications_created,
            "torrents_indexed": telemetry.get("torrents_indexed", 0),
        }
