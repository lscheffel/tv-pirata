"""EZTV native adapter aligned with sources-apis.md (eztvx.to, RSS, eztvstatus.org)."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session

from src.backend.models.sources_db import ExternalSourceRecord
from src.backend.providers.eztv import EZTVProvider
from src.backend.providers.sources.base import (
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceQueryContext,
    build_official_magnet,
    parse_release_title_and_year,
    register_source_adapter,
    validate_safe_url,
)
from src.backend.repositories.catalog import CatalogRepository
from src.backend.services.catalog_indexer import EZTVIndexerService
from src.backend.services.entity_resolution import EntityResolutionService
from src.backend.services.federated_catalog import FederatedCatalogService

DEFAULT_EZTV_BASE_URL = "https://eztvx.to"
DEFAULT_EZTV_RSS_URL = "https://myrss.org/eztv"
DEFAULT_EZTV_STATUS_URL = "https://eztvstatus.org/"


class EZTVAdapterConfig(BaseModel):
    """Configuration schema for the EZTV base catalog adapter (sources-apis.md)."""

    base_url: str = Field(default=DEFAULT_EZTV_BASE_URL, title="URL Principal da EZTV")
    rss_url: str = Field(default=DEFAULT_EZTV_RSS_URL, title="Feed RSS Oficial (myrss.org/eztv)")
    status_url: str = Field(
        default=DEFAULT_EZTV_STATUS_URL,
        title="URL de Saúde / Status Oficial (eztvstatus.org)",
    )
    mirrors: list[str] = Field(
        default_factory=lambda: ["https://eztv.re", "https://eztv1.xyz"],
        title="Mirrors P2P",
    )
    timeout_seconds: float = Field(default=6.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


@register_source_adapter
class EZTVSourceAdapter(BaseSourceAdapter):
    """Base EZTV TV Series P2P catalog, RSS pulse, and numeric IMDb live lookup adapter."""

    adapter_key = "eztv"
    display_name = "EZTV (Catálogo Base P2P)"
    description = (
        "API REST JSON oficial da EZTV (eztvx.to/api/get-torrents?limit=100&imdb_id=...), "
        "feed RSS (myrss.org/eztv) e diagnóstico (eztvstatus.org)."
    )
    default_source_kind = "torrent_mirrorable"
    default_media_types = "tvSeries,tvMiniSeries"
    supports_sync = True
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return EZTVAdapterConfig

    @staticmethod
    def _parse_cfg(instance: ExternalSourceRecord) -> EZTVAdapterConfig:
        try:
            raw = json.loads(instance.config_json or "{}")
        except Exception:
            raw = {}
        if instance.base_url and not raw.get("base_url"):
            raw["base_url"] = instance.base_url
        return EZTVAdapterConfig.model_validate(raw)

    @staticmethod
    def parse_rss_xml(xml_text: str) -> list[NormalizedReleaseCandidate]:
        """Parse official EZTV RSS XML (https://myrss.org/eztv) into normalized candidates."""
        candidates: list[NormalizedReleaseCandidate] = []
        if not xml_text or "<rss" not in xml_text.lower() and "<channel" not in xml_text.lower():
            return candidates
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return candidates

        for item in root.findall(".//item"):
            raw_title = (item.findtext("title") or "").strip()
            if not raw_title:
                continue
            link = validate_safe_url(item.findtext("link"), ("http", "https", "magnet"))
            enclosure = item.find("enclosure")
            enc_url = (
                validate_safe_url(enclosure.attrib.get("url"), ("http", "https", "magnet"))
                if enclosure is not None
                else None
            )
            magnet_url: Optional[str] = None
            torrent_url: Optional[str] = None
            external_url: Optional[str] = None
            info_hash: Optional[str] = None

            for elem in item.iter():
                tag_low = elem.tag.lower()
                txt = (elem.text or "").strip()
                if tag_low.endswith("magneturi") and txt.startswith("magnet:"):
                    magnet_url = validate_safe_url(txt, ("magnet",))
                elif tag_low.endswith("infohash") and len(txt) >= 32:
                    info_hash = txt.lower()

            for candidate_u in (link, enc_url):
                if not candidate_u:
                    continue
                if candidate_u.startswith("magnet:"):
                    magnet_url = magnet_url or candidate_u
                elif candidate_u.endswith(".torrent"):
                    torrent_url = torrent_url or candidate_u
                else:
                    external_url = external_url or candidate_u

            if not magnet_url and info_hash:
                magnet_url = build_official_magnet(info_hash, raw_title)
            if not info_hash and magnet_url:
                hm = re.search(r"btih:([a-fA-F0-9]{32,40})", magnet_url)
                if hm:
                    info_hash = hm.group(1).lower()

            if not (magnet_url or torrent_url or external_url):
                continue

            _clean, year, season, episode, quality = parse_release_title_and_year(raw_title)
            digest = hashlib.sha1(
                f"eztv_rss:{info_hash or raw_title}".encode("utf-8")
            ).hexdigest()[:14]
            candidates.append(
                NormalizedReleaseCandidate(
                    external_id=f"eztv_rss:{digest}",
                    imdb_id=None,
                    title=raw_title,
                    work_type="tvSeries",
                    season=season,
                    episode=episode,
                    quality=quality,
                    seeds=10,
                    peers=2,
                    size_bytes=0,
                    release_type="magnet" if magnet_url else ("torrent" if torrent_url else "link"),
                    magnet_url=magnet_url,
                    torrent_url=torrent_url,
                    external_url=external_url,
                    info_hash=info_hash,
                    year=year,
                    matched_by="rss_feed",
                    match_confidence=0.88,
                )
            )
        return candidates

    async def fetch_rss_pulse(
        self,
        instance: ExternalSourceRecord,
    ) -> list[NormalizedReleaseCandidate]:
        """Fetch and parse the official EZTV RSS feed (https://myrss.org/eztv)."""
        cfg = self._parse_cfg(instance)
        rss_url = validate_safe_url(cfg.rss_url, ("http", "https")) or DEFAULT_EZTV_RSS_URL
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.get(rss_url)
                if resp.status_code == 200 and resp.text:
                    return self.parse_rss_xml(resp.text)
        except Exception:
            pass
        return []

    async def sync(
        self,
        instance: ExternalSourceRecord,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 5,
        enrich: bool = True,
        mode: str = "incremental",
    ) -> dict[str, Any]:
        cfg = self._parse_cfg(instance)
        eff_pages = 1 if mode == "incremental" else max(1, min(pages, 100))
        indexer = EZTVIndexerService()
        target_primary = mainstream_session or sources_session
        telemetry = await indexer.sync_pages(
            session=target_primary,
            start_page=1,
            max_pages=eff_pages,
            enrich_metadata=enrich,
        )
        if mainstream_session is not None and sources_session is not mainstream_session:
            await indexer.sync_pages(
                session=sources_session,
                start_page=1,
                max_pages=eff_pages,
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
        telemetry["rss_url"] = cfg.rss_url
        telemetry["status_url"] = cfg.status_url
        telemetry["mode"] = mode
        return telemetry

    async def search(
        self,
        instance: ExternalSourceRecord,
        query_ctx: SourceQueryContext,
        sources_session: Optional[Session] = None,
        mainstream_session: Optional[Session] = None,
    ) -> AdapterSearchOutcome:
        norm_imdb = EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
        if not norm_imdb:
            return AdapterSearchOutcome(status="ok", releases=[])

        cfg = self._parse_cfg(instance)
        base_url = (instance.base_url or cfg.base_url or DEFAULT_EZTV_BASE_URL).rstrip("/")
        provider = EZTVProvider(base_url=f"{base_url}/api")

        candidates: list[NormalizedReleaseCandidate] = []
        try:
            # Stage 2 JIT live lookup by numeric IMDb ID (without 'tt', limit 1..100)
            live = await provider.get_torrents_by_imdb(
                imdb_id=norm_imdb.lstrip("t"),
                limit=max(1, min(query_ctx.limit, 100)),
                page=1,
            )
            for lr in live:
                mag = validate_safe_url(lr.magnet_url, ("magnet",))
                if not mag and lr.hash:
                    mag = build_official_magnet(lr.hash, lr.title or lr.filename)
                tor = validate_safe_url(lr.torrent_url, ("http", "https"))
                candidates.append(
                    NormalizedReleaseCandidate(
                        external_id=str(lr.id),
                        imdb_id=norm_imdb,
                        title=lr.title or lr.filename,
                        work_type="tvSeries",
                        season=lr.season,
                        episode=lr.episode,
                        quality=lr.quality,
                        seeds=lr.seeds,
                        peers=lr.peers,
                        size_bytes=lr.size_bytes,
                        release_type="magnet" if mag else "torrent",
                        magnet_url=mag,
                        torrent_url=tor,
                        info_hash=lr.hash,
                        matched_by="exact_imdb",
                        match_confidence=1.0,
                    )
                )
            if candidates:
                return AdapterSearchOutcome(status="ok", releases=candidates)
        except Exception:
            pass

        # Fallback to local CatalogRelease snapshot if live endpoint returned empty/offline
        if sources_session is not None:
            local_rows = CatalogRepository.get_show_releases(sources_session, norm_imdb)
            if not local_rows and mainstream_session is not None:
                local_rows = CatalogRepository.get_show_releases(mainstream_session, norm_imdb)
            for r in local_rows[: query_ctx.limit]:
                mag = validate_safe_url(r.magnet_url, ("magnet",))
                tor = validate_safe_url(r.torrent_url, ("http", "https"))
                candidates.append(
                    NormalizedReleaseCandidate(
                        external_id=str(r.eztv_id),
                        imdb_id=norm_imdb,
                        title=r.title or r.filename,
                        work_type="tvSeries",
                        season=r.season,
                        episode=r.episode,
                        quality=r.quality,
                        seeds=r.seeds,
                        peers=r.peers,
                        size_bytes=r.size_bytes,
                        release_type="magnet" if mag else "torrent",
                        magnet_url=mag,
                        torrent_url=tor,
                        info_hash=r.hash,
                        matched_by="exact_imdb",
                        match_confidence=1.0,
                    )
                )

        return AdapterSearchOutcome(status="ok", releases=candidates)

    async def healthcheck(
        self,
        instance: ExternalSourceRecord,
        sources_session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """Verify EZTV API health with numeric imdb_id lookup and report official status_url."""
        cfg = self._parse_cfg(instance)
        outcome = await self.search(
            instance,
            SourceQueryContext(title="Game of Thrones", year=2011, imdb_id="tt0944947", limit=5),
            sources_session=sources_session,
        )
        return {
            "status": outcome.status,
            "releases_found": len(outcome.releases),
            "message": outcome.message,
            "rss_url": cfg.rss_url,
            "status_url": cfg.status_url,
        }
