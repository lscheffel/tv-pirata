"""EZTV native adapter bridging legacy EZTV tables and live API into the plugin registry."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlmodel import Session

from src.backend.models.sources_db import ExternalSourceRecord
from src.backend.providers.eztv import EZTVProvider
from src.backend.providers.sources.base import (
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceQueryContext,
    register_source_adapter,
    validate_safe_url,
)
from src.backend.repositories.catalog import CatalogRepository
from src.backend.services.catalog_indexer import EZTVIndexerService
from src.backend.services.entity_resolution import EntityResolutionService
from src.backend.services.federated_catalog import FederatedCatalogService


class EZTVAdapterConfig(BaseModel):
    """Configuration schema for the EZTV base catalog adapter."""

    base_url: str = Field(default="https://eztvx.to", title="URL Principal da EZTV")
    mirrors: list[str] = Field(
        default_factory=lambda: ["https://eztv.re", "https://eztv1.xyz"],
        title="Mirrors P2P",
    )
    timeout_seconds: float = Field(default=6.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


@register_source_adapter
class EZTVSourceAdapter(BaseSourceAdapter):
    """Base EZTV TV Series P2P catalog & live search adapter."""

    adapter_key = "eztv"
    display_name = "EZTV (Catálogo Base P2P)"
    description = "Catálogo persistente de séries de TV e releases P2P via API oficial da EZTV."
    default_source_kind = "torrent_mirrorable"
    default_media_types = "tvSeries,tvMiniSeries"
    supports_sync = True
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return EZTVAdapterConfig

    async def sync(
        self,
        instance: ExternalSourceRecord,
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

        candidates: list[NormalizedReleaseCandidate] = []
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

        if candidates:
            return AdapterSearchOutcome(status="ok", releases=candidates)

        try:
            raw_cfg = json.loads(instance.config_json or "{}")
        except Exception:
            raw_cfg = {}
        base_url = instance.base_url or raw_cfg.get("base_url") or "https://eztvx.to"
        provider = EZTVProvider(base_url=f"{base_url.rstrip('/')}/api/get-torrents")
        try:
            live = await provider.get_torrents_by_imdb(
                imdb_id=norm_imdb, limit=min(query_ctx.limit, 50)
            )
            for lr in live:
                mag = validate_safe_url(lr.magnet_url, ("magnet",))
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
            return AdapterSearchOutcome(status="ok", releases=candidates)
        except Exception as exc:
            return AdapterSearchOutcome(status="error", message=str(exc), releases=[])
