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
from sqlalchemy import func, text
from sqlmodel import Session, col, delete, select

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.domain_concurrency import create_shared_http_client, domain_semaphores
from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.db import CatalogRelease, CatalogShow, ShowRecord
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord
from src.backend.providers.sources import (
    ADAPTER_LOAD_ERRORS,
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceDiagnostic,
    SourceQueryContext,
    compute_title_match_confidence,
    discover_source_adapters,
    parse_release_title_and_year,
    validate_safe_url,
)
from src.backend.providers.sources.base import (
    mask_secret_config,
    merge_preserving_secrets,
)
from src.backend.providers.sources.torrent_api_py_adapter import (
    TORRENT_API_PY_SITE_CATALOG,
    TorrentApiPySourceAdapter,
)
from src.backend.providers.sources.yify_adapter import (
    DEFAULT_YTS_BASE_URL,
    DEFAULT_YTS_MIRRORS,
    YIFYSourceAdapter,
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
            "rss_url": "https://myrss.org/eztv",
            "status_url": "https://eztvstatus.org/",
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
        "base_url": DEFAULT_YTS_BASE_URL,
        "priority": 20,
        "config": {
            "base_url": DEFAULT_YTS_BASE_URL,
            "mirrors": list(DEFAULT_YTS_MIRRORS),
            "default_quality": "All",
            "minimum_rating": 0,
            "sort_by": "date_added",
            "with_rt_ratings": True,
            "timeout_seconds": 8.0,
            "ttl_hours": 24,
        },
    },
    *(
        {
            "source_key": site_key,
            "display_name": TORRENT_API_PY_SITE_CATALOG[site_key]["display_name"],
            "adapter_key": "torrent_api_py",
            "source_kind": "torrent_mirrorable",
            "kind": "scrape_index",
            "media_types": TORRENT_API_PY_SITE_CATALOG[site_key]["media_types"],
            "base_url": "http://127.0.0.1:8009",
            "priority": idx,
            "config": {
                "base_url": "http://127.0.0.1:8009",
                "site": site_key,
                "mirrors": [],
                "public_web_Search_url": TORRENT_API_PY_SITE_CATALOG[site_key][
                    "public_web_Search_url"
                ],
                "timeout_seconds": 5.0,
                "ttl_hours": 24,
            },
        }
        for idx, site_key in ((30, "tgx"), (35, "nyaasi"), (40, "bitsearch"), (45, "glodls"))
    ),
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
        """Idempotently seed default source instances and migrate ADR-014 protocol endpoints."""
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
                if not getattr(rec, "adapter_key", None) or rec.adapter_key != spec["adapter_key"]:
                    rec.adapter_key = spec["adapter_key"]
                    changed = True
                if not getattr(rec, "config_json", None) or rec.config_json == "{}":
                    rec.config_json = json.dumps(spec["config"], ensure_ascii=False)
                    changed = True

                # Idempotent ADR-014 YTS URL migration (yts.mx/yts.gg -> movies-api.accel.li)
                if spec["source_key"] == "yify":
                    try:
                        cfg_data = json.loads(rec.config_json or "{}")
                    except Exception:
                        cfg_data = {}
                    cur_url = str(rec.base_url or cfg_data.get("base_url") or "")
                    if any(old in cur_url for old in ("yts.mx", "yts.gg", "yts.lt")):
                        rec.base_url = DEFAULT_YTS_BASE_URL
                        cfg_data["base_url"] = DEFAULT_YTS_BASE_URL
                        cfg_data["mirrors"] = list(DEFAULT_YTS_MIRRORS)
                        rec.config_json = json.dumps(cfg_data, ensure_ascii=False)
                        changed = True

                # Idempotent ADR-014 EZTV RSS & health status enrichment
                if spec["source_key"] == "eztv":
                    try:
                        cfg_data = json.loads(rec.config_json or "{}")
                    except Exception:
                        cfg_data = {}
                    if not cfg_data.get("rss_url") or not cfg_data.get("status_url"):
                        cfg_data.setdefault("rss_url", "https://myrss.org/eztv")
                        cfg_data.setdefault("status_url", "https://eztvstatus.org/")
                        rec.config_json = json.dumps(cfg_data, ensure_ascii=False)
                        changed = True

        # Migrate legacy 1337x seed to torrent_api_py adapter and keep disabled if 0 releases
        legacy_1337 = sources_session.get(ExternalSourceRecord, "1337x")
        if legacy_1337 is not None:
            if legacy_1337.adapter_key != "torrent_api_py":
                legacy_1337.adapter_key = "torrent_api_py"
                changed = True
            if legacy_1337.enabled:
                cnt = int(
                    sources_session.exec(
                        select(func.count(ExternalRelease.id)).where(
                            ExternalRelease.source_key == "1337x"
                        )
                    ).one()
                    or 0
                )
                if cnt == 0:
                    legacy_1337.enabled = False
                sources_session.add(legacy_1337)
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
        *,
        replace_on_success: bool = False,
    ) -> tuple[list[ExternalRelease], list[dict[str, Any]]]:
        """Write-through candidates with confidence >= 0.85; keep 0.60-0.84 ephemeral."""
        persisted: list[ExternalRelease] = []
        approx_ephemeral: list[dict[str, Any]] = []
        now = _utc_now()
        wrote_any = False

        verified_ext_ids: set[str] = set()
        for cand in candidates:
            if cand.match_confidence >= 0.85:
                mag = validate_safe_url(cand.magnet_url, ("magnet",))
                tor = validate_safe_url(cand.torrent_url, ("http", "https"))
                ext = validate_safe_url(cand.external_url, ("http", "https"))
                if mag or tor or ext:
                    verified_ext_ids.add(cand.external_id)

        # Atomic Replace-on-Success (RT14-01): prune stale/dead releases of this work
        if replace_on_success and verified_ext_ids:
            stale_rows = list(
                sources_session.exec(
                    select(ExternalRelease).where(
                        ExternalRelease.source_key == source_key,
                        ExternalRelease.imdb_id == norm_imdb,
                    )
                ).all()
            )
            for stale in stale_rows:
                if stale.external_id not in verified_ext_ids:
                    sources_session.delete(stale)
                    wrote_any = True

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

        # 2. Determine which instances need live Lazy-Search (Stage 2 JIT with Format Routing)
        to_query_live: list[tuple[ExternalSourceRecord, BaseSourceAdapter, int]] = []
        for inst in instances:
            adapter = adapters.get(inst.adapter_key)
            if not adapter or not adapter.supports_search:
                continue

            # Format-aware routing when querying "all" sources (RT14-03)
            if target_src is None and not q_override and query_ctx.work_type:
                wt = query_ctx.work_type
                inst_mt = {m.strip() for m in (inst.media_types or "").split(",") if m.strip()}
                is_movie_work = wt in ("movie", "tvMovie", "short", "documentary")
                is_tv_work = wt in ("tvSeries", "tvMiniSeries", "tv_show", "mini_series")
                if (
                    is_movie_work
                    and inst_mt
                    and "movie" not in inst_mt
                    and "animation" not in inst_mt
                ):
                    continue
                if is_tv_work and inst_mt == {"movie"}:
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

            has_materialized_cache = any(
                not str(cr.external_id or "").startswith("yts:presence:") for cr in src_cached
            )
            is_fresh = bool(
                has_materialized_cache
                and latest_check
                and (now - latest_check) < timedelta(hours=max(1, ttl_hours))
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

            # Check 2-level circuit breaker (skip host cooldown for torrent_api_py native fallback)
            inst_cd = _as_utc(inst.cooldown_until)
            host_k = _host_key(cfg.get("base_url") or inst.base_url)
            host_cd = (
                None
                if inst.adapter_key == "torrent_api_py"
                else _as_utc(_HOST_COOLDOWN_UNTIL.get(host_k or ""))
            )
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
                        replace_on_success=True,
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
    def _hydrator_map(
        cls,
        mainstream_session: Optional[Session],
        imdb_ids: list[str],
    ) -> dict[str, IMDbCatalogShow]:
        """Batch Sovereign Join lookup in mainstream.db (RT14-02)."""
        if mainstream_session is None or not imdb_ids:
            return {}
        clean_ids = [i for i in {i.strip() for i in imdb_ids if i} if i.startswith("tt")]
        if not clean_ids:
            return {}
        try:
            rows = list(
                mainstream_session.exec(
                    select(IMDbCatalogShow).where(col(IMDbCatalogShow.imdb_id).in_(clean_ids))
                ).all()
            )
            return {r.imdb_id: r for r in rows}
        except Exception:
            return {}

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
        """List multi-source items with canonical imdb_id deduplication and Batch Sovereign Join."""
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
                        "media_sources": [r.source_key],
                        "qualities": [r.quality] if r.quality and r.quality != "Unknown" else [],
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
                    if r.quality and r.quality != "Unknown" and r.quality not in entry["qualities"]:
                        entry["qualities"].append(r.quality)
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
                        "media_sources": ["eztv"],
                        "qualities": [],
                        "release_type": "magnet",
                    }
                )

        # Canonical IMDb deduplication across sources when source="all" (R1: 9D)
        if target_src is None:
            merged_by_imdb: dict[str, dict[str, Any]] = {}
            no_imdb_items: list[dict[str, Any]] = []
            for item in combined:
                norm_id = EntityResolutionService.normalize_imdb_id(item.get("imdb_id"))
                if not norm_id:
                    no_imdb_items.append(item)
                    continue
                if norm_id not in merged_by_imdb:
                    merged_by_imdb[norm_id] = {
                        **item,
                        "imdb_id": norm_id,
                        "media_sources": list(item.get("media_sources") or [item["source_key"]]),
                        "qualities": list(item.get("qualities") or []),
                    }
                else:
                    ex = merged_by_imdb[norm_id]
                    ex["total_torrents"] = int(ex.get("total_torrents") or 0) + int(
                        item.get("total_torrents") or 0
                    )
                    if int(item.get("max_seeds") or 0) > int(ex.get("max_seeds") or 0):
                        ex["max_seeds"] = int(item.get("max_seeds") or 0)
                        ex["source_key"] = item["source_key"]
                    for sk in item.get("media_sources") or [item["source_key"]]:
                        if sk not in ex["media_sources"]:
                            ex["media_sources"].append(sk)
                    for q in item.get("qualities") or []:
                        if q not in ex["qualities"]:
                            ex["qualities"].append(q)
                    ex["media_sources"].sort()
                    ex["source_name"] = " + ".join(s.upper() for s in ex["media_sources"])
                    ex["poster_url"] = ex.get("poster_url") or item.get("poster_url")
                    ex["overview"] = ex.get("overview") or item.get("overview")
                    ex["rating"] = max(
                        float(ex.get("rating") or 0.0), float(item.get("rating") or 0.0)
                    )
            combined = [*merged_by_imdb.values(), *no_imdb_items]

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

        # Batch Sovereign Join against mainstream.db (Layer 1 owns rich metadata)
        hydrator = cls._hydrator_map(
            mainstream_session,
            [str(it.get("imdb_id") or "") for it in page_items],
        )
        for it in page_items:
            row = hydrator.get(str(it.get("imdb_id") or ""))
            if not row:
                continue
            it["title"] = row.title_ptbr or row.primary_title or it["title"]
            it["original_title"] = row.original_title or row.primary_title
            it["overview"] = row.synopsis_ptbr or row.synopsis or it.get("overview") or ""
            it["poster_url"] = row.poster_url or it.get("poster_url")
            it["backdrop_url"] = row.backdrop_url or it.get("backdrop_url")
            it["rating"] = float(row.rating_score or it.get("rating") or 0.0)
            it["genres"] = row.genres_ptbr or row.genres or it.get("genres") or ""
            if row.start_year:
                it["first_air_date"] = str(row.start_year)
            it["status"] = row.status or it.get("status")
            it["network"] = row.network or it.get("network")
            if row.streaming_providers:
                it["streaming_providers"] = [
                    p.strip() for p in row.streaming_providers.split(",") if p.strip()
                ]
            it["is_enriched"] = True

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
    def _resolve_imdb_id_against_mainstream(
        cls,
        mainstream_session: Optional[Session],
        raw_title: str,
        release_year: Optional[int] = None,
        work_type: Optional[str] = None,
    ) -> tuple[Optional[str], float, str]:
        """Resolve clean release title against sovereign IMDbCatalogShow in mainstream.db."""
        if mainstream_session is None or not raw_title.strip():
            return None, 0.0, "unresolved"
        clean_title, ext_year, _s, _e, _q = parse_release_title_and_year(raw_title)
        eff_year = release_year or ext_year
        probe = clean_title or raw_title
        if len(probe) < 2:
            return None, 0.0, "unresolved"

        if not clean_title:
            return None, 0.0, "unresolved"

        rows: list[IMDbCatalogShow] = []
        tokens = [
            re.sub(r"[^a-zA-Z0-9]", "", t)
            for t in probe.split()
            if len(re.sub(r"[^a-zA-Z0-9]", "", t)) >= 2
        ]
        # 1. Fast FTS5 index lookup in mainstream.db (< 15ms vs 1.5s full table scan)
        if tokens:
            fts_q = " AND ".join(f'"{t}"' for t in tokens[:4])
            try:
                fts_ids = [
                    str(r[0])
                    for r in mainstream_session.exec(
                        text(
                            "SELECT s.imdb_id FROM shows s "
                            "JOIN shows_fts f ON s.rowid = f.rowid "
                            "WHERE shows_fts MATCH :q "
                            "ORDER BY s.rating_votes DESC LIMIT 15"
                        ),
                        params={"q": fts_q},
                    ).all()
                    if r and r[0]
                ]
                if fts_ids:
                    rows = list(
                        mainstream_session.exec(
                            select(IMDbCatalogShow).where(
                                col(IMDbCatalogShow.imdb_id).in_(fts_ids)
                            )
                        ).all()
                    )
            except Exception:
                rows = []

        # 2. Fallback ONLY for tiny in-memory test databases (< 5k rows)
        if not rows:
            try:
                total_shows = int(
                    mainstream_session.exec(select(func.count(IMDbCatalogShow.imdb_id))).one() or 0
                )
                if total_shows < 5000:
                    fuzzy_pat = f"%{'%'.join(tokens)}%" if tokens else f"%{probe}%"
                    head_pat = f"{tokens[0]}%" if tokens else fuzzy_pat
                    rows = list(
                        mainstream_session.exec(
                            select(IMDbCatalogShow)
                            .where(
                                col(IMDbCatalogShow.primary_title).ilike(fuzzy_pat)
                                | col(IMDbCatalogShow.original_title).ilike(fuzzy_pat)
                                | col(IMDbCatalogShow.title_ptbr).ilike(fuzzy_pat)
                                | col(IMDbCatalogShow.primary_title).ilike(head_pat)
                            )
                            .limit(15)
                        ).all()
                    )
            except Exception:
                return None, 0.0, "unresolved"

        best_id: Optional[str] = None
        best_conf = 0.0
        for row in rows:
            conf = compute_title_match_confidence(
                query_title=row.primary_title,
                query_original_title=row.original_title,
                query_year=row.start_year if eff_year else None,
                query_work_type=row.title_type,
                candidate_title=clean_title or raw_title,
                candidate_year=eff_year,
            )
            if conf > best_conf:
                best_conf = conf
                best_id = row.imdb_id

        if best_id and best_conf >= 0.85:
            return best_id, best_conf, "canonical_title_match"
        return None, best_conf, "unresolved"

    @classmethod
    def _recompute_source_counters(cls, sources_session: Session) -> None:
        """Recompute ExternalSourceRecord total_titles and total_releases accurately."""
        rows = sources_session.exec(
            select(
                ExternalRelease.source_key,
                func.count(ExternalRelease.id),
                func.count(func.distinct(ExternalRelease.imdb_id)),
            ).group_by(ExternalRelease.source_key)
        ).all()
        counts = {str(s): (int(rel or 0), int(tit or 0)) for s, rel, tit in rows}
        for rec in sources_session.exec(select(ExternalSourceRecord)).all():
            if rec.source_key == "eztv":
                continue
            rel_cnt, tit_cnt = counts.get(rec.source_key, (0, 0))
            rec.total_releases = rel_cnt
            rec.total_titles = tit_cnt
            sources_session.add(rec)
        sources_session.commit()

    @classmethod
    def prune_obsolete_releases(
        cls,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        source_key: Optional[str] = None,
        min_seeds_floor: int = 1,
        max_zero_seed_hours: int = 48,
        max_stale_days: int = 14,
    ) -> dict[str, Any]:
        """Prune dead (0 seeds) or stale semi-ephemeral releases and propagate presence."""
        now = _utc_now()
        zero_cutoff = now - timedelta(hours=max(0, max_zero_seed_hours))
        stale_cutoff = now - timedelta(days=max(1, max_stale_days))

        stmt = select(ExternalRelease)
        if source_key and source_key != "all":
            stmt = stmt.where(ExternalRelease.source_key == source_key.lower())

        removed = 0
        for rel in sources_session.exec(stmt).all():
            checked_at = _as_utc(rel.last_checked_at or rel.created_at) or now
            is_dead = rel.seeds < max(1, min_seeds_floor) and (
                max_zero_seed_hours == 0 or checked_at <= zero_cutoff
            )
            is_stale = checked_at <= stale_cutoff and rel.seeds < 5
            if is_dead or is_stale:
                sources_session.delete(rel)
                removed += 1

        if removed > 0:
            sources_session.commit()
            cls._recompute_source_counters(sources_session)
            catalog_cache.invalidate()
            discovery_cache.invalidate()

        return {
            "status": "ok",
            "removed_releases": removed,
            "min_seeds_floor": min_seeds_floor,
            "max_zero_seed_hours": max_zero_seed_hours,
        }

    @classmethod
    async def get_yify_enrichment_for_imdb(
        cls,
        sources_session: Session,
        mainstream_session: Optional[Session],
        imdb_id: str,
    ) -> dict[str, Any]:
        """Fetch official YTS v2 details, 4 suggestions, and parental guides."""
        cls.ensure_sources_registered(sources_session)
        rec = sources_session.get(ExternalSourceRecord, "yify")
        adapter = cls.get_adapters_map().get("yify")
        if rec is None or not isinstance(adapter, YIFYSourceAdapter):
            return {
                "status": "unavailable",
                "imdb_id": imdb_id,
                "details": None,
                "suggestions": [],
                "parental_guides": [],
            }
        data = await adapter.fetch_movie_enrichment(rec, imdb_id=imdb_id)
        if mainstream_session is not None and data.get("suggestions"):
            s_ids = [s.get("imdb_id") for s in data["suggestions"] if s.get("imdb_id")]
            hydrator = cls._hydrator_map(mainstream_session, s_ids)
            for s in data["suggestions"]:
                row = hydrator.get(str(s.get("imdb_id") or ""))
                if row:
                    s["work_imdb_id"] = row.imdb_id
                    s["title_ptbr"] = row.title_ptbr or row.primary_title
                    s["poster_url"] = row.poster_url or s.get("poster_url")
        return data

    @classmethod
    async def live_ingest_query(
        cls,
        sources_session: Session,
        mainstream_session: Optional[Session],
        *,
        query: str,
        source_key: Optional[str] = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search active sources live from Fontes de Dados and ingest verified releases (4D)."""
        cls.ensure_sources_registered(sources_session)
        adapters = cls.get_adapters_map()
        q_clean = query.strip()
        if not q_clean:
            return {
                "status": "empty",
                "ingested_count": 0,
                "matched_imdb_ids": [],
                "diagnostics": {},
            }

        instances = list(
            sources_session.exec(
                select(ExternalSourceRecord).where(ExternalSourceRecord.enabled == True)  # noqa: E712
            ).all()
        )
        if source_key and source_key != "all":
            instances = [r for r in instances if r.source_key == source_key.lower()]

        ctx_imdb = EntityResolutionService.normalize_imdb_id(q_clean)
        q_ctx = SourceQueryContext(
            imdb_id=ctx_imdb, title=q_clean, custom_query=q_clean, limit=limit
        )
        ingested = 0
        matched_imdbs: set[str] = set()
        diagnostics: dict[str, Any] = {}

        for inst in instances:
            adapter = adapters.get(inst.adapter_key)
            if not adapter or not adapter.supports_search:
                continue
            cfg = cls._parse_instance_config(inst, adapter)
            host_k = _host_key(cfg.get("base_url") or inst.base_url)
            host_cd = _as_utc(_HOST_COOLDOWN_UNTIL.get(host_k or ""))
            if host_cd and host_cd > _utc_now():
                diagnostics[inst.source_key] = {"status": "cooldown", "message": "Sidecar offline."}
                continue
            try:
                outcome = await adapter.search(
                    inst,
                    q_ctx,
                    sources_session=sources_session,
                    mainstream_session=mainstream_session,
                )
            except httpx.ConnectError:
                if host_k:
                    _HOST_COOLDOWN_UNTIL[host_k] = _utc_now() + timedelta(seconds=120)
                diagnostics[inst.source_key] = {"status": "offline", "message": "Host inacessível."}
                continue
            except Exception as exc:
                diagnostics[inst.source_key] = {"status": "error", "message": str(exc)}
                continue

            diagnostics[inst.source_key] = {
                "status": outcome.status,
                "found": len(outcome.releases),
            }
            if outcome.status != "ok":
                continue

            for cand in outcome.releases:
                eff_imdb = cand.imdb_id
                eff_conf = cand.match_confidence
                if not eff_imdb:
                    r_imdb, r_conf, _ = cls._resolve_imdb_id_against_mainstream(
                        mainstream_session, cand.title, cand.year, cand.work_type
                    )
                    if r_imdb:
                        eff_imdb = r_imdb
                        eff_conf = max(eff_conf, r_conf)
                if eff_conf >= 0.85 and eff_imdb and cand.seeds >= 1:
                    cand.imdb_id = eff_imdb
                    cand.match_confidence = eff_conf
                    persisted, _ = cls._persist_verified_candidates(
                        sources_session, inst.source_key, eff_imdb, [cand], replace_on_success=False
                    )
                    if persisted:
                        ingested += len(persisted)
                        matched_imdbs.add(eff_imdb)

        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return {
            "status": "completed",
            "query": q_clean,
            "ingested_count": ingested,
            "matched_imdb_ids": sorted(matched_imdbs),
            "diagnostics": diagnostics,
        }

    @classmethod
    async def sync_source(
        cls,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        source_key: str = "eztv",
        pages: int = 5,
        start_page: int = 1,
        compact_presence: bool = False,
        enrich: bool = True,
        mode: str = "incremental",
        quality: Optional[str] = None,
        minimum_rating: Optional[int] = None,
        sort_by: Optional[str] = None,
        genre: Optional[str] = None,
        min_seeds_floor: int = 1,
        prune_after: bool = True,
    ) -> dict[str, Any]:
        """Stage 1 Bipartite Sync: incremental, baseline, library, or prune."""
        cls.ensure_sources_registered(sources_session)
        adapters = cls.get_adapters_map()
        eff_mode = (mode or "incremental").strip().lower()

        if eff_mode == "prune":
            prune_res = cls.prune_obsolete_releases(
                sources_session,
                mainstream_session,
                source_key=source_key,
                min_seeds_floor=min_seeds_floor,
                max_zero_seed_hours=0,
            )
            return {"status": "completed", "mode": "prune", "prune": prune_res, "results": {}}

        if eff_mode == "library":
            if mainstream_session is None:
                return {"status": "completed", "mode": "library", "results": {}}
            shows = list(mainstream_session.exec(select(ShowRecord)).all())
            synced_titles = 0
            total_found = 0
            for show in shows[:30]:
                if not show.imdb_id:
                    continue
                res = await cls.get_releases_for_imdb(
                    sources_session,
                    mainstream_session,
                    show.imdb_id,
                    source=None if source_key == "all" else source_key,
                    live_mode="force",
                    title=show.title,
                )
                synced_titles += 1
                total_found += int(res.get("total") or 0)
            catalog_cache.invalidate()
            discovery_cache.invalidate()
            return {
                "status": "completed",
                "mode": "library",
                "titles_scanned": synced_titles,
                "releases_found": total_found,
                "results": {
                    source_key: {
                        "status": "success",
                        "telemetry": {
                            "titles_scanned": synced_titles,
                            "releases_indexed": total_found,
                        },
                    }
                },
            }

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

            cfg = cls._parse_instance_config(inst, adapter)
            host_k = _host_key(cfg.get("base_url") or inst.base_url)

            try:
                if isinstance(adapter, YIFYSourceAdapter):
                    telemetry = await adapter.sync(
                        inst,
                        sources_session,
                        mainstream_session,
                        pages=pages,
                        start_page=start_page,
                        compact_presence=compact_presence,
                        enrich=enrich,
                        mode=eff_mode,
                        quality=quality,
                        minimum_rating=minimum_rating,
                        sort_by=sort_by,
                        genre=genre,
                    )
                elif isinstance(adapter, TorrentApiPySourceAdapter):
                    recent_cands = await adapter.fetch_recent_candidates(
                        inst, pages=min(pages, 10), limit=75, start_page=start_page
                    )
                    indexed = 0
                    matched_canonical = 0
                    for cand in recent_cands:
                        if cand.seeds < min_seeds_floor:
                            continue
                        imdb = cand.imdb_id
                        conf = cand.match_confidence
                        if not imdb:
                            r_id, r_conf, _ = cls._resolve_imdb_id_against_mainstream(
                                mainstream_session, cand.title, cand.year, cand.work_type
                            )
                            if r_id:
                                imdb = r_id
                                conf = max(conf, r_conf)
                                matched_canonical += 1
                        if imdb and conf >= 0.85:
                            cand.imdb_id = imdb
                            cand.match_confidence = conf
                            p_rows, _ = cls._persist_verified_candidates(
                                sources_session, inst.source_key, imdb, [cand]
                            )
                            indexed += len(p_rows)
                    is_exhausted = len(recent_cands) == 0 or (
                        eff_mode == "baseline" and start_page > 1 and indexed == 0
                    )
                    telemetry = {
                        "source": inst.source_key,
                        "mode": eff_mode,
                        "start_page": start_page,
                        "next_page": 1 if is_exhausted else (start_page + min(pages, 10)),
                        "exhausted": is_exhausted,
                        "candidates_scanned": len(recent_cands),
                        "canonical_matched": matched_canonical,
                        "releases_indexed": indexed,
                    }
                else:
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
            except httpx.ConnectError as exc:
                if host_k:
                    _HOST_COOLDOWN_UNTIL[host_k] = _utc_now() + timedelta(seconds=120)
                inst.status = "degraded"
                inst.last_error = f"Sidecar / Host {host_k or inst.base_url} offline."
                sources_session.add(inst)
                sources_session.commit()
                results[inst.source_key] = {
                    "status": "skipped_offline",
                    "error": str(exc),
                }
            except Exception as exc:
                inst.status = "degraded"
                inst.last_error = str(exc)
                sources_session.add(inst)
                sources_session.commit()
                results[inst.source_key] = {"status": "error", "error": str(exc)}

        prune_summary = None
        if prune_after:
            prune_summary = cls.prune_obsolete_releases(
                sources_session,
                mainstream_session,
                source_key=source_key,
                min_seeds_floor=min_seeds_floor,
                max_zero_seed_hours=48,
            )

        cls._recompute_source_counters(sources_session)
        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return {
            "status": "completed",
            "mode": eff_mode,
            "prune": prune_summary,
            "results": results,
        }

    @staticmethod
    def select_sweep_works(
        mainstream_session: Session,
        *,
        source_key: str,
        offset: int = 0,
        batch_size: int = 12,
    ) -> list[IMDbCatalogShow]:
        """Prepare-phase read: select canonical works for catalog presence sweep."""
        eff_offset = max(0, int(offset))
        eff_batch = max(1, min(int(batch_size), 50))
        stmt = select(IMDbCatalogShow).where(IMDbCatalogShow.rating_votes >= 1000)
        if source_key == "nyaasi":
            stmt = stmt.where(col(IMDbCatalogShow.genres).ilike("%Animation%"))
        stmt = (
            stmt.order_by(
                col(IMDbCatalogShow.rating_votes).desc(),
                col(IMDbCatalogShow.imdb_id).asc(),
            )
            .offset(eff_offset)
            .limit(eff_batch)
        )
        return list(mainstream_session.exec(stmt).all())

    @staticmethod
    async def fetch_sweep_batch_fanout(
        inst: ExternalSourceRecord,
        adapter: BaseSourceAdapter,
        works: list[IMDbCatalogShow],
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> list[tuple[IMDbCatalogShow, AdapterSearchOutcome | Exception]]:
        """Pure HTTP Fan-out for canonical catalog sweep under domain semaphore."""
        if not works:
            return []
        own_client = client is None
        http_client = client or create_shared_http_client(timeout=10.0)

        async def _query_one(
            work: IMDbCatalogShow,
        ) -> tuple[IMDbCatalogShow, AdapterSearchOutcome | Exception]:
            query_ctx = SourceQueryContext(
                imdb_id=work.imdb_id,
                title=work.primary_title,
                original_title=work.original_title,
                year=work.start_year,
                work_type=work.title_type,
                limit=10,
            )
            try:
                if isinstance(adapter, TorrentApiPySourceAdapter):
                    outcome = await adapter.search(inst, query_ctx, client=http_client)
                else:
                    async with domain_semaphores.get(inst.source_key):
                        outcome = await adapter.search(inst, query_ctx)
                return work, outcome
            except Exception as exc:
                return work, exc

        try:
            return list(await asyncio.gather(*(_query_one(w) for w in works)))
        finally:
            if own_client:
                await http_client.aclose()

    @classmethod
    def persist_sweep_batch_fanin(
        cls,
        sources_session: Session,
        inst: ExternalSourceRecord,
        outcomes: list[tuple[IMDbCatalogShow, AdapterSearchOutcome | Exception]],
        *,
        offset: int = 0,
        batch_size: int = 12,
        min_seeds_floor: int = 1,
    ) -> dict[str, Any]:
        """Fan-in SQLite write for parallel catalog sweep results."""
        eff_offset = max(0, int(offset))
        eff_batch = max(1, min(int(batch_size), 50))
        scanned = len(outcomes)
        matched_titles = 0
        releases_indexed = 0
        aborted_reason: Optional[str] = None

        for work, item in outcomes:
            if isinstance(item, Exception):
                aborted_reason = str(item)
                continue
            if item.status == "challenge_required":
                aborted_reason = item.message or "challenge_required"
                inst.status = "challenge_required"
                inst.last_error = aborted_reason
                inst.cooldown_until = _utc_now() + timedelta(seconds=60)
                continue
            if item.status == "error" and "429" in (item.message or ""):
                aborted_reason = item.message or "HTTP 429 rate limit"
                inst.status = "degraded"
                inst.last_error = aborted_reason
                inst.cooldown_until = _utc_now() + timedelta(seconds=60)
                continue
            verified = [
                c
                for c in item.releases
                if c.seeds >= min_seeds_floor and c.match_confidence >= 0.85
            ]
            if verified:
                for c in verified:
                    c.imdb_id = work.imdb_id
                persisted, _ = cls._persist_verified_candidates(
                    sources_session,
                    inst.source_key,
                    work.imdb_id,
                    verified[:3],
                    replace_on_success=False,
                )
                if persisted:
                    matched_titles += 1
                    releases_indexed += len(persisted)

        inst.last_sync_at = _utc_now()
        if not aborted_reason:
            inst.status = "ready"
            inst.last_error = None
        sources_session.add(inst)
        sources_session.commit()
        cls._recompute_source_counters(sources_session)
        catalog_cache.invalidate()
        discovery_cache.invalidate()

        return {
            "source": inst.source_key,
            "offset": eff_offset,
            "next_offset": eff_offset + scanned,
            "titles_scanned": scanned,
            "titles_matched": matched_titles,
            "releases_indexed": releases_indexed,
            "exhausted": scanned < eff_batch,
            "aborted_reason": aborted_reason,
        }

    @classmethod
    async def sweep_canonical_catalog_presence(
        cls,
        sources_session: Session,
        mainstream_session: Optional[Session],
        *,
        source_key: str,
        offset: int = 0,
        batch_size: int = 12,
        min_seeds_floor: int = 1,
        client: Optional[httpx.AsyncClient] = None,
    ) -> dict[str, Any]:
        """Stage 1B Resumable Canonical Catalog Presence Sweep for Sidecar/Search sources."""
        if mainstream_session is None:
            return {
                "source": source_key,
                "offset": offset,
                "next_offset": offset,
                "titles_scanned": 0,
                "titles_matched": 0,
                "releases_indexed": 0,
                "exhausted": True,
            }

        cls.ensure_sources_registered(sources_session)
        inst = sources_session.get(ExternalSourceRecord, source_key.lower())
        if inst is None or not inst.enabled:
            return {
                "source": source_key,
                "offset": offset,
                "next_offset": offset,
                "titles_scanned": 0,
                "titles_matched": 0,
                "releases_indexed": 0,
                "exhausted": True,
                "skipped": "disabled_or_missing",
            }

        adapters = cls.get_adapters_map()
        adapter = adapters.get(inst.adapter_key)
        if not adapter or not adapter.supports_search:
            return {
                "source": source_key,
                "offset": offset,
                "next_offset": offset,
                "titles_scanned": 0,
                "titles_matched": 0,
                "releases_indexed": 0,
                "exhausted": True,
                "skipped": "adapter_no_search",
            }

        works = cls.select_sweep_works(
            mainstream_session, source_key=inst.source_key, offset=offset, batch_size=batch_size
        )
        if not works:
            return {
                "source": inst.source_key,
                "offset": max(0, int(offset)),
                "next_offset": 0,
                "titles_scanned": 0,
                "titles_matched": 0,
                "releases_indexed": 0,
                "exhausted": True,
            }

        outcomes = await cls.fetch_sweep_batch_fanout(inst, adapter, works, client=client)
        return cls.persist_sweep_batch_fanin(
            sources_session,
            inst,
            outcomes,
            offset=offset,
            batch_size=batch_size,
            min_seeds_floor=min_seeds_floor,
        )
