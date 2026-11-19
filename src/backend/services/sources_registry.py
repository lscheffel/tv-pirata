"""Polymorphic 1:N adapter & source instance orchestrator over data/sources.db (ADR-013)."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy import func
from sqlmodel import Session, col, delete, select

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.db import CatalogRelease, CatalogShow
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord
from src.backend.providers.sources import (
    ADAPTER_LOAD_ERRORS,
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceDiagnostic,
    SourceQueryContext,
    discover_source_adapters,
    validate_safe_url,
)
from src.backend.providers.sources.base import (
    mask_secret_config,
    merge_preserving_secrets,
)
from src.backend.repositories.catalog import CatalogRepository
from src.backend.services.entity_resolution import EntityResolutionService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _host_key(raw_url: Optional[str]) -> Optional[str]:
    if not raw_url:
        return None
    parsed = urlparse(raw_url)
    return parsed.netloc.lower() if parsed.netloc else None


# Level-2 shared host circuit breaker (netloc -> cooldown_until UTC)
_HOST_COOLDOWN_UNTIL: dict[str, datetime] = {}

DEFAULT_SOURCE_INSTANCES: tuple[dict[str, Any], ...] = (
    {
        "source_key": "eztv",
        "display_name": "EZTV",
        "adapter_key": "eztv",
        "source_kind": "torrent_mirrorable",
        "kind": "torrent_api",
        "media_types": "tvSeries,tvMiniSeries",
        "base_url": "https://eztvx.to",
        "priority": 10,
        "config": {
            "base_url": "https://eztvx.to",
            "mirrors": ["https://eztv.re", "https://eztv1.xyz"],
            "timeout_seconds": 6.0,
            "ttl_hours": 24,
        },
    },
    {
        "source_key": "yify",
        "display_name": "YIFY / YTS",
        "adapter_key": "yify",
        "source_kind": "torrent_mirrorable",
        "kind": "movie_torrent_api",
        "media_types": "movie",
        "base_url": "https://yts.mx/api/v2/list_movies.json",
        "priority": 20,
        "config": {
            "base_url": "https://yts.mx/api/v2/list_movies.json",
            "mirrors": ["https://yts.lt/api/v2/list_movies.json"],
            "timeout_seconds": 8.0,
            "ttl_hours": 24,
        },
    },
    {
        "source_key": "1337x",
        "display_name": "1337x",
        "adapter_key": "torrent_api_py",
        "source_kind": "torrent_mirrorable",
        "kind": "scrape_index",
        "media_types": "movie,tvSeries,animation",
        "base_url": "http://127.0.0.1:8009",
        "priority": 30,
        "config": {
            "base_url": "http://127.0.0.1:8009",
            "site": "1337x",
            "mirrors": [],
            "public_web_Search_url": "https://1337x.to/search/{query}/1/",
            "timeout_seconds": 5.0,
            "ttl_hours": 24,
        },
    },
)


class SourcesRegistryService:
    """Unified multi-source query, dynamic plugin CRUD, lazy-cache, and 2-level circuit breaker."""

    @classmethod
    def get_adapters_map(cls) -> dict[str, BaseSourceAdapter]:
        """Return autodiscovered BaseSourceAdapter dictionary."""
        return discover_source_adapters()

    @classmethod
    def list_adapters_metadata(cls) -> dict[str, Any]:
        """Return metadata and JSON schemas for all discovered source adapters."""
        adapters = cls.get_adapters_map()
        items = []
        for key, adapter in sorted(adapters.items()):
            items.append(
                {
                    "adapter_key": key,
                    "display_name": adapter.display_name,
                    "description": adapter.description,
                    "default_source_kind": adapter.default_source_kind,
                    "default_media_types": [
                        t.strip() for t in adapter.default_media_types.split(",") if t.strip()
                    ],
                    "supports_sync": adapter.supports_sync,
                    "supports_search": adapter.supports_search,
                    "secret_fields": sorted(adapter.secret_fields()),
                    "config_schema": adapter.config_json_schema(),
                }
            )
        return {"adapters": items, "load_errors": dict(ADAPTER_LOAD_ERRORS)}

    @classmethod
    def ensure_sources_registered(cls, sources_session: Session) -> None:
        """Idempotently seed default source instances into external_sources."""
        cls.get_adapters_map()
        changed = False
        for spec in DEFAULT_SOURCE_INSTANCES:
            rec = sources_session.get(ExternalSourceRecord, spec["source_key"])
            if rec is None:
                sources_session.add(
                    ExternalSourceRecord(
                        source_key=spec["source_key"],
                        display_name=spec["display_name"],
                        adapter_key=spec["adapter_key"],
                        source_kind=spec["source_kind"],
                        kind=spec["kind"],
                        media_types=spec["media_types"],
                        base_url=spec["base_url"],
                        config_json=json.dumps(spec["config"], ensure_ascii=False),
                        priority=spec["priority"],
                        enabled=True,
                        status="ready",
                    )
                )
                changed = True
            else:
                if not getattr(rec, "adapter_key", None):
                    rec.adapter_key = spec["adapter_key"]
                    changed = True
                if not getattr(rec, "config_json", None) or rec.config_json == "{}":
                    rec.config_json = json.dumps(spec["config"], ensure_ascii=False)
                    changed = True
        if changed:
            sources_session.commit()

    @classmethod
    def _parse_instance_config(
        cls, rec: ExternalSourceRecord, adapter: Optional[BaseSourceAdapter]
    ) -> dict[str, Any]:
        try:
            raw = json.loads(rec.config_json or "{}")
            if not isinstance(raw, dict):
                raw = {}
        except Exception:
            raw = {}
        if rec.base_url and not raw.get("base_url"):
            raw["base_url"] = rec.base_url
        if adapter:
            try:
                validated = adapter.config_model().model_validate(raw)
                return validated.model_dump()
            except Exception:
                return raw
        return raw

    @classmethod
    def _serialize_instance(
        cls,
        rec: ExternalSourceRecord,
        titles_count: int,
        releases_count: int,
    ) -> dict[str, Any]:
        adapters = cls.get_adapters_map()
        adapter = adapters.get(rec.adapter_key)
        cfg = cls._parse_instance_config(rec, adapter)
        secrets = adapter.secret_fields() if adapter else {"api_key", "token", "password"}
        masked_cfg = mask_secret_config(cfg, secrets)
        now = _utc_now()
        cd_until = _as_utc(rec.cooldown_until)
        host_cd = _HOST_COOLDOWN_UNTIL.get(_host_key(cfg.get("base_url") or rec.base_url) or "")
        effective_cd = max(
            [d for d in (cd_until, _as_utc(host_cd)) if d and d > now],
            default=None,
        )

        return {
            "source_key": rec.source_key,
            "display_name": rec.display_name,
            "adapter_key": rec.adapter_key,
            "source_kind": rec.source_kind or "torrent_mirrorable",
            "kind": rec.kind,
            "media_types": [t.strip() for t in (rec.media_types or "").split(",") if t.strip()],
            "base_url": rec.base_url or cfg.get("base_url"),
            "config": masked_cfg,
            "priority": rec.priority if rec.priority is not None else 100,
            "enabled": rec.enabled,
            "status": "cooldown" if effective_cd else rec.status,
            "cooldown_until": effective_cd.isoformat() if effective_cd else None,
            "last_sync_at": rec.last_sync_at.isoformat() if rec.last_sync_at else None,
            "last_error": rec.last_error,
            "total_titles": titles_count,
            "total_releases": releases_count,
            "supports_sync": adapter.supports_sync if adapter else False,
            "supports_search": adapter.supports_search if adapter else True,
        }

    @classmethod
    def get_summary(cls, sources_session: Session) -> dict[str, Any]:
        """Compute live multi-provider telemetry and masked configs from data/sources.db."""
        cls.ensure_sources_registered(sources_session)
        records = list(sources_session.exec(select(ExternalSourceRecord)).all())

        eztv_shows_cnt = int(sources_session.exec(select(func.count(EZTVShow.id))).one() or 0)
        eztv_releases_cnt = int(
            sources_session.exec(select(func.count(CatalogRelease.id))).one() or 0
        )
        if eztv_shows_cnt == 0:
            eztv_shows_cnt = int(
                sources_session.exec(select(func.count(CatalogShow.imdb_id))).one() or 0
            )

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

        records.sort(key=lambda r: (r.priority if r.priority is not None else 100, r.source_key))

        sources_out: list[dict[str, Any]] = []
        total_titles = 0
        total_releases = 0
        active_sources = 0

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
            sources_out.append(cls._serialize_instance(rec, titles, releases))

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
    def create_instance(
        cls,
        sources_session: Session,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new configured source instance backed by a registered BaseSourceAdapter."""
        cls.ensure_sources_registered(sources_session)
        adapters = cls.get_adapters_map()
        adapter_key = str(payload.get("adapter_key") or "").strip().lower()
        adapter = adapters.get(adapter_key)
        if not adapter:
            raise ValueError(f"Adapter '{adapter_key}' não encontrado no registro de plugins.")

        raw_key = (
            str(payload.get("source_key") or payload.get("display_name") or "").strip().lower()
        )
        source_key = re.sub(r"[^a-z0-9_-]", "_", raw_key).strip("_")
        if not source_key:
            raise ValueError("Identificador source_key inválido.")
        if sources_session.get(ExternalSourceRecord, source_key) is not None:
            raise ValueError(f"Fonte '{source_key}' já existe em sources.db.")

        incoming_cfg = payload.get("config") or {}
        if not isinstance(incoming_cfg, dict):
            incoming_cfg = {}
        if payload.get("base_url") and not incoming_cfg.get("base_url"):
            incoming_cfg["base_url"] = payload["base_url"]

        if incoming_cfg.get("base_url"):
            safe_base = validate_safe_url(str(incoming_cfg["base_url"]), ("http", "https"))
            if not safe_base:
                raise ValueError("base_url inválida (apenas http:// ou https:// são permitidos).")
            incoming_cfg["base_url"] = safe_base

        if isinstance(incoming_cfg.get("mirrors"), list):
            safe_mirrors = []
            for m in incoming_cfg["mirrors"]:
                sm = validate_safe_url(str(m), ("http", "https"))
                if sm:
                    safe_mirrors.append(sm)
            incoming_cfg["mirrors"] = safe_mirrors

        validated_cfg = adapter.config_model().model_validate(incoming_cfg).model_dump()
        source_kind = str(payload.get("source_kind") or adapter.default_source_kind)
        if source_kind not in ("torrent_mirrorable", "unique_web_source"):
            source_kind = adapter.default_source_kind

        media_types_in = payload.get("media_types")
        if isinstance(media_types_in, list):
            media_types_str = ",".join(str(x).strip() for x in media_types_in if str(x).strip())
        elif isinstance(media_types_in, str) and media_types_in.strip():
            media_types_str = media_types_in.strip()
        else:
            media_types_str = adapter.default_media_types

        rec = ExternalSourceRecord(
            source_key=source_key,
            display_name=str(payload.get("display_name") or source_key.upper()).strip(),
            adapter_key=adapter_key,
            source_kind=source_kind,
            kind=adapter_key,
            media_types=media_types_str,
            base_url=validated_cfg.get("base_url"),
            config_json=json.dumps(validated_cfg, ensure_ascii=False),
            priority=int(payload.get("priority", 100)),
            enabled=bool(payload.get("enabled", True)),
            status="ready",
        )
        sources_session.add(rec)
        sources_session.commit()
        sources_session.refresh(rec)
        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return cls._serialize_instance(rec, 0, 0)

    @classmethod
    def update_instance(
        cls,
        sources_session: Session,
        source_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing source instance while preserving masked secrets (RT13-02)."""
        cls.ensure_sources_registered(sources_session)
        rec = sources_session.get(ExternalSourceRecord, source_key)
        if rec is None:
            raise KeyError(f"Fonte '{source_key}' não encontrada.")

        adapters = cls.get_adapters_map()
        adapter = adapters.get(rec.adapter_key)
        existing_cfg = cls._parse_instance_config(rec, adapter)
        secrets = adapter.secret_fields() if adapter else {"api_key", "token", "password"}

        if "display_name" in payload and payload["display_name"]:
            rec.display_name = str(payload["display_name"]).strip()
        if "enabled" in payload and payload["enabled"] is not None:
            rec.enabled = bool(payload["enabled"])
        if "priority" in payload and payload["priority"] is not None:
            rec.priority = int(payload["priority"])
        if "source_kind" in payload and payload["source_kind"] in (
            "torrent_mirrorable",
            "unique_web_source",
        ):
            rec.source_kind = payload["source_kind"]
        if "media_types" in payload and payload["media_types"]:
            mt = payload["media_types"]
            rec.media_types = ",".join(mt) if isinstance(mt, list) else str(mt)

        incoming_cfg = payload.get("config")
        if isinstance(incoming_cfg, dict):
            merged = merge_preserving_secrets(existing_cfg, incoming_cfg, secrets)
            if merged.get("base_url"):
                safe_b = validate_safe_url(str(merged["base_url"]), ("http", "https"))
                if not safe_b:
                    raise ValueError("base_url inválida (use http:// ou https://).")
                merged["base_url"] = safe_b
                rec.base_url = safe_b
            if isinstance(merged.get("mirrors"), list):
                safe_m = []
                for m in merged["mirrors"]:
                    sm = validate_safe_url(str(m), ("http", "https"))
                    if sm:
                        safe_m.append(sm)
                merged["mirrors"] = safe_m
            if adapter:
                merged = adapter.config_model().model_validate(merged).model_dump()
            rec.config_json = json.dumps(merged, ensure_ascii=False)

        if payload.get("clear_cooldown"):
            rec.cooldown_until = None
            rec.status = "ready"
            rec.last_error = None

        sources_session.add(rec)
        sources_session.commit()
        sources_session.refresh(rec)
        catalog_cache.invalidate()
        discovery_cache.invalidate()
        summary = cls.get_summary(sources_session)
        for item in summary["sources"]:
            if item["source_key"] == source_key:
                return item
        return cls._serialize_instance(rec, rec.total_titles, rec.total_releases)

    @classmethod
    def delete_instance(cls, sources_session: Session, source_key: str) -> dict[str, Any]:
        """Delete a non-base external source instance and its cached releases."""
        if source_key == "eztv":
            raise ValueError("O catálogo base 'eztv' não pode ser removido.")
        rec = sources_session.get(ExternalSourceRecord, source_key)
        if rec is None:
            raise KeyError(f"Fonte '{source_key}' não encontrada.")

        sources_session.exec(
            delete(ExternalRelease).where(ExternalRelease.source_key == source_key)
        )
        sources_session.delete(rec)
        sources_session.commit()
        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return {"status": "deleted", "source_key": source_key}

    @classmethod
    async def test_instance(
        cls,
        sources_session: Session,
        source_key: str,
    ) -> dict[str, Any]:
        """Run on-demand healthcheck for a source instance and update its diagnostic status."""
        cls.ensure_sources_registered(sources_session)
        rec = sources_session.get(ExternalSourceRecord, source_key)
        if rec is None:
            raise KeyError(f"Fonte '{source_key}' não encontrada.")
        adapter = cls.get_adapters_map().get(rec.adapter_key)
        if not adapter:
            raise ValueError(f"Adapter '{rec.adapter_key}' indisponível.")

        t0 = time.perf_counter()
        try:
            result = await adapter.healthcheck(rec, sources_session=sources_session)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            st = result.get("status", "ok")
            rec.status = (
                "ready"
                if st == "ok"
                else ("challenge_required" if st == "challenge_required" else "degraded")
            )
            rec.last_error = None if st == "ok" else result.get("message")
            if st == "ok":
                rec.cooldown_until = None
            sources_session.add(rec)
            sources_session.commit()
            return {
                "source_key": source_key,
                "adapter_key": rec.adapter_key,
                "latency_ms": elapsed_ms,
                **result,
            }
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            rec.status = "degraded"
            rec.last_error = str(exc)
            sources_session.add(rec)
            sources_session.commit()
            return {
                "source_key": source_key,
                "adapter_key": rec.adapter_key,
                "status": "error",
                "message": str(exc),
                "latency_ms": elapsed_ms,
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
    def _resolve_work_context(
        cls,
        mainstream_session: Optional[Session],
        norm_imdb: str,
        title: Optional[str] = None,
        year: Optional[int] = None,
        custom_query: Optional[str] = None,
        limit: int = 100,
    ) -> SourceQueryContext:
        work_title = title or norm_imdb
        orig_title: Optional[str] = None
        work_year = year
        work_type: Optional[str] = None

        if mainstream_session is not None and norm_imdb.startswith("tt"):
            try:
                row = mainstream_session.get(IMDbCatalogShow, norm_imdb)
                if row is not None:
                    work_title = row.title_ptbr or row.primary_title or work_title
                    orig_title = row.original_title or row.primary_title
                    work_year = work_year or row.start_year
                    work_type = row.title_type
            except Exception:
                pass

        return SourceQueryContext(
            imdb_id=norm_imdb,
            title=work_title,
            original_title=orig_title,
            year=work_year,
            work_type=work_type,
            custom_query=custom_query,
            limit=limit,
        )

    @classmethod
    def _persist_verified_candidates(
        cls,
        sources_session: Session,
        source_key: str,
        norm_imdb: str,
        candidates: list[NormalizedReleaseCandidate],
    ) -> tuple[list[ExternalRelease], list[dict[str, Any]]]:
        """Write-through candidates with match_confidence >= 0.85; keep 0.60-0.84 ephemeral."""
        persisted: list[ExternalRelease] = []
        approx_ephemeral: list[dict[str, Any]] = []
        now = _utc_now()
        wrote_any = False

        for cand in candidates:
            mag = validate_safe_url(cand.magnet_url, ("magnet",))
            tor = validate_safe_url(cand.torrent_url, ("http", "https"))
            ext = validate_safe_url(cand.external_url, ("http", "https"))
            if not (mag or tor or ext):
                continue

            if cand.match_confidence >= 0.85:
                existing = sources_session.exec(
                    select(ExternalRelease).where(
                        ExternalRelease.source_key == source_key,
                        ExternalRelease.external_id == cand.external_id,
                    )
                ).first()
                if existing:
                    existing.imdb_id = norm_imdb
                    existing.seeds = cand.seeds
                    existing.peers = cand.peers
                    existing.magnet_url = mag or existing.magnet_url
                    existing.torrent_url = tor or existing.torrent_url
                    existing.external_url = ext or existing.external_url
                    existing.matched_by = cand.matched_by
                    existing.match_confidence = cand.match_confidence
                    existing.last_checked_at = now
                    sources_session.add(existing)
                    persisted.append(existing)
                else:
                    new_rel = ExternalRelease(
                        source_key=source_key,
                        external_id=cand.external_id,
                        imdb_id=norm_imdb,
                        title=cand.title,
                        work_type=cand.work_type,
                        season=cand.season,
                        episode=cand.episode,
                        quality=cand.quality,
                        seeds=cand.seeds,
                        peers=cand.peers,
                        size_bytes=cand.size_bytes,
                        release_type=cand.release_type,
                        magnet_url=mag,
                        torrent_url=tor,
                        external_url=ext,
                        info_hash=cand.info_hash,
                        poster_url=validate_safe_url(cand.poster_url, ("http", "https")),
                        genres=cand.genres,
                        year=cand.year,
                        rating=cand.rating,
                        matched_by=cand.matched_by,
                        match_confidence=cand.match_confidence,
                        last_checked_at=now,
                    )
                    sources_session.add(new_rel)
                    persisted.append(new_rel)
                wrote_any = True
            elif cand.match_confidence >= 0.60:
                approx_ephemeral.append(
                    {
                        "id": cand.external_id,
                        "source_key": source_key,
                        "source_name": source_key.upper(),
                        "release_type": cand.release_type,
                        "hash": cand.info_hash or "",
                        "filename": cand.title,
                        "title": cand.title,
                        "season": cand.season,
                        "episode": cand.episode,
                        "quality": cand.quality,
                        "seeds": cand.seeds,
                        "peers": cand.peers,
                        "size_bytes": cand.size_bytes,
                        "magnet_url": mag or "",
                        "torrent_url": tor,
                        "external_url": ext,
                        "matched_by": cand.matched_by,
                        "match_confidence": cand.match_confidence,
                    }
                )

        if wrote_any:
            sources_session.commit()
            discovery_cache.invalidate()
            catalog_cache.invalidate()

        return persisted, approx_ephemeral

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
        live_mode: Optional[str] = None,
        q_override: Optional[str] = None,
        title: Optional[str] = None,
        year: Optional[int] = None,
    ) -> dict[str, Any]:
        """Fetch multi-provider releases with Lazy-Cache (TTL 24h), 2-level CB, and diagnostics."""
        cls.ensure_sources_registered(sources_session)
        adapters = cls.get_adapters_map()
        norm_imdb = EntityResolutionService.normalize_imdb_id(imdb_id) or imdb_id.strip()
        target_src = source.strip().lower() if source and source.strip().lower() != "all" else None
        mode = (live_mode or ("auto" if include_live else "cache")).lower()

        instances = list(
            sources_session.exec(
                select(ExternalSourceRecord).where(ExternalSourceRecord.enabled == True)  # noqa: E712
            ).all()
        )
        instances.sort(key=lambda r: (r.priority if r.priority is not None else 100, r.source_key))
        inst_map = {r.source_key: r for r in instances}
        if target_src and target_src not in inst_map:
            rec_single = sources_session.get(ExternalSourceRecord, target_src)
            if rec_single:
                inst_map[target_src] = rec_single
                instances = [rec_single]
            else:
                instances = []
        elif target_src:
            instances = [inst_map[target_src]]

        # 1. Load existing cached ExternalRelease rows for norm_imdb
        ext_stmt = select(ExternalRelease).where(ExternalRelease.imdb_id == norm_imdb)
        if target_src:
            ext_stmt = ext_stmt.where(ExternalRelease.source_key == target_src)
        ext_stmt = ext_stmt.order_by(col(ExternalRelease.seeds).desc()).limit(limit * 2)
        cached_ext_rows = list(sources_session.exec(ext_stmt).all())
        cached_by_src: dict[str, list[ExternalRelease]] = {}
        for r in cached_ext_rows:
            cached_by_src.setdefault(r.source_key, []).append(r)

        # Load legacy EZTV CatalogRelease rows
        legacy_eztv_rows = []
        if target_src in (None, "eztv"):
            legacy_eztv_rows = CatalogRepository.get_show_releases(sources_session, norm_imdb)
            if not legacy_eztv_rows and mainstream_session is not sources_session:
                legacy_eztv_rows = CatalogRepository.get_show_releases(
                    mainstream_session, norm_imdb
                )

        diagnostics: dict[str, dict[str, Any]] = {}
        approx_matches: list[dict[str, Any]] = []
        now = _utc_now()
        query_ctx = cls._resolve_work_context(
            mainstream_session,
            norm_imdb,
            title=title,
            year=year,
            custom_query=q_override,
            limit=limit,
        )

        # 2. Determine which instances need live Lazy-Search
        to_query_live: list[tuple[ExternalSourceRecord, BaseSourceAdapter, int]] = []
        for inst in instances:
            adapter = adapters.get(inst.adapter_key)
            if not adapter or not adapter.supports_search:
                continue
            cfg = cls._parse_instance_config(inst, adapter)
            ttl_hours = int(cfg.get("ttl_hours") or 24)
            src_cached = cached_by_src.get(inst.source_key, [])
            if inst.source_key == "eztv" and legacy_eztv_rows:
                diagnostics[inst.source_key] = SourceDiagnostic(
                    source_key=inst.source_key,
                    source_name=inst.display_name,
                    adapter_key=inst.adapter_key,
                    source_kind=inst.source_kind or "torrent_mirrorable",  # type: ignore[arg-type]
                    status="ok",
                    from_cache=True,
                ).model_dump()
                if mode != "force" and not q_override:
                    continue

            latest_check: Optional[datetime] = None
            for cr in src_cached:
                chk = _as_utc(cr.last_checked_at or cr.created_at)
                if chk and (latest_check is None or chk > latest_check):
                    latest_check = chk

            is_fresh = bool(
                latest_check and (now - latest_check) < timedelta(hours=max(1, ttl_hours))
            )

            if mode == "cache" or (mode == "auto" and is_fresh and not q_override):
                diagnostics[inst.source_key] = SourceDiagnostic(
                    source_key=inst.source_key,
                    source_name=inst.display_name,
                    adapter_key=inst.adapter_key,
                    source_kind=inst.source_kind or "torrent_mirrorable",  # type: ignore[arg-type]
                    status="ok",
                    from_cache=True,
                    cached_at=latest_check.isoformat() if latest_check else None,
                ).model_dump()
                continue

            # When mode == "auto" and target_src is None, only auto-query default localhost sidecar
            # if explicitly targeted or if it is a primary cloud provider, unless mode == "force"
            if (
                mode == "auto"
                and target_src is None
                and not q_override
                and inst.adapter_key == "torrent_api_py"
                and "127.0.0.1:8009" in str(cfg.get("base_url") or inst.base_url or "")
                and not src_cached
            ):
                # Avoid default localhost:8009 connection refusals unless forced/targeted
                diagnostics[inst.source_key] = SourceDiagnostic(
                    source_key=inst.source_key,
                    source_name=inst.display_name,
                    adapter_key=inst.adapter_key,
                    source_kind=inst.source_kind or "torrent_mirrorable",  # type: ignore[arg-type]
                    status="ok",
                    message=(
                        "Clique em 'Buscar Ao Vivo' ou na aba da fonte para consultar o sidecar."
                    ),
                    from_cache=True,
                ).model_dump()
                continue

            # Check 2-level circuit breaker
            inst_cd = _as_utc(inst.cooldown_until)
            host_k = _host_key(cfg.get("base_url") or inst.base_url)
            host_cd = _as_utc(_HOST_COOLDOWN_UNTIL.get(host_k or ""))
            active_cd = max([d for d in (inst_cd, host_cd) if d and d > now], default=None)
            if active_cd and mode != "force":
                diagnostics[inst.source_key] = SourceDiagnostic(
                    source_key=inst.source_key,
                    source_name=inst.display_name,
                    adapter_key=inst.adapter_key,
                    source_kind=inst.source_kind or "torrent_mirrorable",  # type: ignore[arg-type]
                    status="cooldown",
                    message=inst.last_error or f"Circuito em cooldown até {active_cd.isoformat()}",
                    from_cache=bool(src_cached),
                    cached_at=latest_check.isoformat() if latest_check else None,
                ).model_dump()
                continue

            to_query_live.append((inst, adapter, ttl_hours))

        async def _run_single(
            inst: ExternalSourceRecord, adapter: BaseSourceAdapter
        ) -> tuple[ExternalSourceRecord, AdapterSearchOutcome, int, Optional[Exception]]:
            t0 = time.perf_counter()
            try:
                outcome = await adapter.search(
                    inst,
                    query_ctx,
                    sources_session=sources_session,
                    mainstream_session=mainstream_session,
                )
                return inst, outcome, int((time.perf_counter() - t0) * 1000), None
            except Exception as exc:
                return (
                    inst,
                    AdapterSearchOutcome(status="error", message=str(exc), releases=[]),
                    int((time.perf_counter() - t0) * 1000),
                    exc,
                )

        if to_query_live:
            live_results = await asyncio.gather(
                *(_run_single(inst, adp) for inst, adp, _ttl in to_query_live)
            )
            for inst, outcome, elapsed_ms, raw_exc in live_results:
                cfg = cls._parse_instance_config(inst, adapters.get(inst.adapter_key))
                host_k = _host_key(cfg.get("base_url") or inst.base_url)
                if isinstance(raw_exc, httpx.ConnectError) and host_k:
                    # Level-2 Host Circuit Breaker (2 min shared cooldown)
                    _HOST_COOLDOWN_UNTIL[host_k] = _utc_now() + timedelta(seconds=120)
                    inst.status = "degraded"
                    inst.last_error = f"Sidecar / Host {host_k} inacessível."
                    sources_session.add(inst)
                    sources_session.commit()
                elif outcome.status in ("challenge_required", "error", "timeout"):
                    # Level-1 Instance Circuit Breaker (60s instance cooldown)
                    inst.status = (
                        "challenge_required"
                        if outcome.status == "challenge_required"
                        else "degraded"
                    )
                    inst.last_error = outcome.message
                    inst.cooldown_until = _utc_now() + timedelta(seconds=60)
                    sources_session.add(inst)
                    sources_session.commit()
                else:
                    if inst.status != "ready" or inst.cooldown_until is not None:
                        inst.status = "ready"
                        inst.last_error = None
                        inst.cooldown_until = None
                        sources_session.add(inst)
                        sources_session.commit()

                if outcome.status == "ok" and outcome.releases and inst.source_key != "eztv":
                    persisted, approx = cls._persist_verified_candidates(
                        sources_session,
                        inst.source_key,
                        norm_imdb,
                        outcome.releases,
                    )
                    if persisted:
                        cached_by_src[inst.source_key] = persisted
                    for ap in approx:
                        ap["source_name"] = inst.display_name
                        approx_matches.append(ap)
                elif outcome.status == "ok" and outcome.releases and inst.source_key == "eztv":
                    cached_by_src["eztv_live"] = [
                        ExternalRelease(
                            source_key="eztv",
                            external_id=c.external_id,
                            imdb_id=norm_imdb,
                            title=c.title,
                            work_type="tvSeries",
                            season=c.season,
                            episode=c.episode,
                            quality=c.quality,
                            seeds=c.seeds,
                            peers=c.peers,
                            size_bytes=c.size_bytes,
                            release_type=c.release_type,
                            magnet_url=c.magnet_url,
                            torrent_url=c.torrent_url,
                            info_hash=c.info_hash,
                        )
                        for c in outcome.releases
                    ]

                safe_challenge = validate_safe_url(outcome.challenge_url, ("http", "https"))
                diagnostics[inst.source_key] = SourceDiagnostic(
                    source_key=inst.source_key,
                    source_name=inst.display_name,
                    adapter_key=inst.adapter_key,
                    source_kind=inst.source_kind or "torrent_mirrorable",  # type: ignore[arg-type]
                    status=outcome.status,
                    message=outcome.message,
                    challenge_url=safe_challenge,
                    from_cache=False,
                    cached_at=_utc_now().isoformat() if outcome.status == "ok" else None,
                    latency_ms=elapsed_ms,
                ).model_dump()

        # 3. Assemble final deduplicated release list (including offline cache fallback)
        items: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        for src_key, rel_list in cached_by_src.items():
            eff_key = "eztv" if src_key == "eztv_live" else src_key
            if target_src and eff_key != target_src:
                continue
            inst_obj = inst_map.get(eff_key)
            disp_name = inst_obj.display_name if inst_obj else eff_key.upper()
            for r in rel_list:
                dedupe = (eff_key, str(r.external_id))
                if dedupe in seen_keys:
                    continue
                seen_keys.add(dedupe)
                items.append(
                    {
                        "id": r.external_id,
                        "source_key": eff_key,
                        "source_name": disp_name,
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
                        "magnet_url": validate_safe_url(r.magnet_url, ("magnet",)) or "",
                        "torrent_url": validate_safe_url(r.torrent_url, ("http", "https")),
                        "external_url": validate_safe_url(r.external_url, ("http", "https")),
                        "matched_by": getattr(r, "matched_by", "exact_imdb"),
                        "match_confidence": getattr(r, "match_confidence", 1.0),
                    }
                )

        if target_src in (None, "eztv"):
            for lr in legacy_eztv_rows[:limit]:
                dedupe = ("eztv", str(lr.eztv_id))
                if dedupe in seen_keys:
                    continue
                seen_keys.add(dedupe)
                items.append(
                    {
                        "id": lr.eztv_id,
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
                        "magnet_url": validate_safe_url(lr.magnet_url, ("magnet",)) or "",
                        "torrent_url": validate_safe_url(lr.torrent_url, ("http", "https")),
                        "external_url": None,
                        "matched_by": "exact_imdb",
                        "match_confidence": 1.0,
                    }
                )

        items.sort(key=lambda x: int(x.get("seeds") or 0), reverse=True)
        by_source: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_source.setdefault(item["source_key"], []).append(item)

        return {
            "imdb_id": norm_imdb,
            "total": len(items),
            "available_sources": sorted(by_source.keys()),
            "by_source": by_source,
            "items": items[:limit],
            "approx_matches": approx_matches[:25],
            "source_diagnostics": diagnostics,
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
        """List unified multi-source items across EZTV and all dynamic ExternalRelease instances."""
        cls.ensure_sources_registered(sources_session)
        target_src = source.strip().lower() if source and source.strip().lower() != "all" else None
        inst_map = {
            r.source_key: r
            for r in sources_session.exec(select(ExternalSourceRecord)).all()
        }

        combined: list[dict[str, Any]] = []

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
                inst = inst_map.get(r.source_key)
                disp_name = inst.display_name if inst else r.source_key.upper()
                if group_key not in grouped:
                    grouped[group_key] = {
                        "id": r.imdb_id or r.external_id,
                        "source_key": r.source_key,
                        "source_name": disp_name,
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
        """Trigger batch sync for a specific source instance or 'all' enabled instances."""
        cls.ensure_sources_registered(sources_session)
        adapters = cls.get_adapters_map()

        if source_key == "all":
            instances = list(
                sources_session.exec(
                    select(ExternalSourceRecord).where(ExternalSourceRecord.enabled == True)  # noqa: E712
                ).all()
            )
        else:
            rec = sources_session.get(ExternalSourceRecord, source_key.lower())
            if rec is None:
                raise ValueError(f"Fonte '{source_key}' não registrada no catálogo.")
            instances = [rec]

        results: dict[str, Any] = {}
        for inst in instances:
            adapter = adapters.get(inst.adapter_key)
            if not adapter:
                results[inst.source_key] = {
                    "status": "error",
                    "error": f"Adapter '{inst.adapter_key}' não encontrado.",
                }
                continue
            try:
                telemetry = await adapter.sync(
                    inst,
                    sources_session,
                    mainstream_session,
                    pages=pages,
                    enrich=enrich,
                )
                inst.status = "ready"
                inst.last_error = None
                inst.cooldown_until = None
                inst.last_sync_at = _utc_now()
                sources_session.add(inst)
                sources_session.commit()
                results[inst.source_key] = {"status": "success", "telemetry": telemetry}
            except Exception as exc:
                inst.status = "degraded"
                inst.last_error = str(exc)
                sources_session.add(inst)
                sources_session.commit()
                results[inst.source_key] = {"status": "error", "error": str(exc)}

        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return {"status": "completed", "results": results}
