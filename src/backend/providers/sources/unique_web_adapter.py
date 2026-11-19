"""Unique non-torrent web source adapter with explicit CAPTCHA/Challenge manual handoff."""

from __future__ import annotations

import hashlib
import json
from typing import Optional
from urllib.parse import quote_plus

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session

from src.backend.models.sources_db import ExternalSourceRecord
from src.backend.providers.sources.base import (
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceQueryContext,
    compute_title_match_confidence,
    is_antibot_challenge,
    register_source_adapter,
    validate_safe_url,
)
from src.backend.services.entity_resolution import EntityResolutionService


class UniqueWebAdapterConfig(BaseModel):
    """Configuration schema for a unique non-torrent web link source."""

    base_url: str = Field(
        default="https://example.org/api/search",
        title="URL de Consulta da Fonte Web",
    )
    browser_search_url: str = Field(
        default="https://example.org/search?q={query}",
        title="URL para Abertura Manual no Navegador (em caso de CAPTCHA)",
    )
    api_key: str = Field(
        default="",
        title="Chave / Token Opcional",
        json_schema_extra={"secret": True},
    )
    timeout_seconds: float = Field(default=6.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


@register_source_adapter
class UniqueWebSourceAdapter(BaseSourceAdapter):
    """Adapter for unique non-torrent web sources that require manual browser challenge handoff."""

    adapter_key = "unique_web"
    display_name = "Fonte Web Única (Links Diretos / Catálogo Web)"
    description = (
        "Conector para fontes únicas não-torrent; quando protegidas por reCAPTCHA ou Cloudflare, "
        "emite alerta explícito com link seguro para abertura manual no navegador."
    )
    default_source_kind = "unique_web_source"
    default_media_types = "movie,tvSeries"
    supports_sync = False
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return UniqueWebAdapterConfig

    @staticmethod
    def _parse_cfg(instance: ExternalSourceRecord) -> UniqueWebAdapterConfig:
        try:
            raw = json.loads(instance.config_json or "{}")
        except Exception:
            raw = {}
        if instance.base_url and not raw.get("base_url"):
            raw["base_url"] = instance.base_url
        return UniqueWebAdapterConfig.model_validate(raw)

    async def search(
        self,
        instance: ExternalSourceRecord,
        query_ctx: SourceQueryContext,
        sources_session: Optional[Session] = None,
        mainstream_session: Optional[Session] = None,
    ) -> AdapterSearchOutcome:
        cfg = self._parse_cfg(instance)
        query_str = (
            query_ctx.custom_query
            or query_ctx.original_title
            or query_ctx.title
        ).strip()
        safe_api_url = validate_safe_url(cfg.base_url, ("http", "https"))
        manual_url = validate_safe_url(
            cfg.browser_search_url.replace("{query}", quote_plus(query_str)),
            ("http", "https"),
        ) or safe_api_url

        if not safe_api_url:
            return AdapterSearchOutcome(
                status="error",
                message="URL da fonte web única inválida.",
                releases=[],
            )

        headers: dict[str, str] = {}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        target_imdb = EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            try:
                resp = await client.get(
                    safe_api_url,
                    params={"q": query_str, "imdb_id": target_imdb or ""},
                    headers=headers,
                )
                if is_antibot_challenge(resp.status_code, resp.text, dict(resp.headers)):
                    return AdapterSearchOutcome(
                        status="challenge_required",
                        message=(
                            "Verificação reCAPTCHA / Cloudflare detectada nesta fonte única. "
                            "Abra a página no navegador para acessar manualmente."
                        ),
                        challenge_url=manual_url,
                        releases=[],
                    )
                resp.raise_for_status()
                payload = resp.json()
                raw_items = (
                    payload.get("items") or payload.get("results") or payload.get("data") or []
                    if isinstance(payload, dict)
                    else (payload if isinstance(payload, list) else [])
                )

                releases: list[NormalizedReleaseCandidate] = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or item.get("name") or "").strip()
                    ext_url = validate_safe_url(
                        item.get("url") or item.get("external_url") or item.get("link"),
                        ("http", "https"),
                    )
                    mag_url = validate_safe_url(item.get("magnet_url"), ("magnet",))
                    if not title or not (ext_url or mag_url):
                        continue

                    item_imdb = EntityResolutionService.normalize_imdb_id(item.get("imdb_id"))
                    yr_raw = item.get("year")
                    yr = int(yr_raw) if yr_raw else None

                    if item_imdb and target_imdb and item_imdb == target_imdb:
                        matched_by = "exact_imdb"
                        conf = 1.0
                    else:
                        matched_by = "title_year_match"
                        conf = compute_title_match_confidence(
                            query_title=query_ctx.title,
                            query_original_title=query_ctx.original_title,
                            query_year=query_ctx.year,
                            query_work_type=query_ctx.work_type,
                            candidate_title=title,
                            candidate_year=yr,
                        )

                    digest = hashlib.sha1(
                        f"{instance.source_key}:{ext_url or mag_url}".encode("utf-8")
                    ).hexdigest()[:16]
                    releases.append(
                        NormalizedReleaseCandidate(
                            external_id=f"web:{digest}",
                            imdb_id=target_imdb if conf >= 0.85 else item_imdb,
                            title=title,
                            work_type=query_ctx.work_type or "movie",
                            quality=str(item.get("quality") or "Web Link"),
                            seeds=int(item.get("seeds") or 0),
                            peers=int(item.get("peers") or 0),
                            size_bytes=int(item.get("size_bytes") or 0),
                            release_type="link" if ext_url and not mag_url else "magnet",
                            magnet_url=mag_url,
                            external_url=ext_url,
                            year=yr,
                            matched_by=matched_by,
                            match_confidence=conf,
                        )
                    )
                return AdapterSearchOutcome(status="ok", releases=releases)
            except httpx.TimeoutException:
                return AdapterSearchOutcome(
                    status="timeout",
                    message=f"Timeout ao consultar fonte web {instance.display_name}.",
                    challenge_url=manual_url,
                    releases=[],
                )
            except httpx.ConnectError as exc:
                raise exc
            except Exception as exc:
                return AdapterSearchOutcome(
                    status="error",
                    message=str(exc),
                    challenge_url=manual_url,
                    releases=[],
                )
