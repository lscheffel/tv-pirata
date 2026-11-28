"""Torznab protocol adapter for Prowlarr and Jackett multi-indexer feeds."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from typing import Optional
from xml.etree.ElementTree import Element

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
    extract_release_year_and_se,
    is_antibot_challenge,
    register_source_adapter,
    validate_safe_url,
)
from src.backend.services.entity_resolution import EntityResolutionService


class TorznabAdapterConfig(BaseModel):
    """Configuration schema for Torznab indexers (Prowlarr / Jackett)."""

    base_url: str = Field(
        default="http://127.0.0.1:9696/1/api",
        title="Endpoint Torznab (Prowlarr / Jackett)",
    )
    api_key: str = Field(
        default="",
        title="Torznab API Key",
        json_schema_extra={"secret": True},
    )
    categories: str = Field(
        default="2000,5000",
        title="Categorias Torznab (2000=Movies, 5000=TV)",
    )
    timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


def _parse_torznab_xml_item(
    item: Element,
    query_ctx: SourceQueryContext,
    source_key: str,
) -> Optional[NormalizedReleaseCandidate]:
    title = (item.findtext("title") or "").strip()
    if not title:
        return None

    link = (item.findtext("link") or "").strip()
    guid = (item.findtext("guid") or link or title).strip()
    size_text = item.findtext("size") or "0"
    enclosure = item.find("enclosure")

    attrs: dict[str, str] = {}
    for elem in item.iter():
        if elem.tag.endswith("attr"):
            k = (elem.attrib.get("name") or "").lower()
            v = elem.attrib.get("value") or ""
            if k:
                attrs[k] = v

    magnet_raw = attrs.get("magneturl") or (link if link.startswith("magnet:") else None)
    if not magnet_raw and enclosure is not None:
        enc_url = enclosure.attrib.get("url") or ""
        if enc_url.startswith("magnet:"):
            magnet_raw = enc_url
    tor_raw = link if link.startswith(("http://", "https://")) else None
    if not tor_raw and enclosure is not None:
        enc_url = enclosure.attrib.get("url") or ""
        if enc_url.startswith(("http://", "https://")):
            tor_raw = enc_url

    magnet = validate_safe_url(magnet_raw, ("magnet",))
    tor_url = validate_safe_url(tor_raw, ("http", "https"))
    comments_url = validate_safe_url(item.findtext("comments"), ("http", "https"))
    if not (magnet or tor_url or comments_url):
        return None

    try:
        size_bytes = int(attrs.get("size") or size_text or 0)
    except ValueError:
        size_bytes = 0
    try:
        seeds = int(attrs.get("seeders") or attrs.get("seeds") or 0)
    except ValueError:
        seeds = 0
    try:
        peers = int(attrs.get("peers") or attrs.get("leechers") or 0)
    except ValueError:
        peers = 0

    raw_imdb = attrs.get("imdbid") or attrs.get("imdb")
    item_imdb = (
        EntityResolutionService.normalize_imdb_id(
            f"tt{raw_imdb}" if raw_imdb and not str(raw_imdb).startswith("tt") else raw_imdb
        )
        if raw_imdb
        else None
    )
    target_imdb = EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
    yr, season, episode = extract_release_year_and_se(title)

    if item_imdb and target_imdb and item_imdb == target_imdb:
        matched_by = "exact_imdb"
        conf = 1.0
    elif item_imdb and target_imdb and item_imdb != target_imdb:
        return None
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

    low_title = title.lower()
    quality = (
        "4K"
        if ("2160p" in low_title or "4k" in low_title)
        else ("1080p" if "1080p" in low_title else ("720p" if "720p" in low_title else "Unknown"))
    )
    digest = hashlib.sha1(f"{source_key}:{guid}".encode("utf-8")).hexdigest()[:16]

    return NormalizedReleaseCandidate(
        external_id=f"tzn:{digest}",
        imdb_id=target_imdb if conf >= 0.85 else item_imdb,
        title=title,
        work_type="tvSeries" if season > 0 else (query_ctx.work_type or "movie"),
        season=season,
        episode=episode,
        quality=quality,
        seeds=seeds,
        peers=peers,
        size_bytes=size_bytes,
        release_type="magnet" if magnet else ("torrent" if tor_url else "link"),
        magnet_url=magnet,
        torrent_url=tor_url,
        external_url=comments_url,
        info_hash=attrs.get("infohash"),
        year=yr,
        matched_by=matched_by,
        match_confidence=conf,
    )


@register_source_adapter
class TorznabSourceAdapter(BaseSourceAdapter):
    """Standardized Torznab XML/JSON feed adapter for Prowlarr and Jackett."""

    adapter_key = "torznab"
    display_name = "Torznab (Prowlarr / Jackett)"
    description = (
        "Protocolo padrão Torznab compatível com dezenas de indexadores "
        "gerenciados pelo Prowlarr ou Jackett."
    )
    default_source_kind = "torrent_mirrorable"
    default_media_types = "movie,tvSeries,animation,documentary"
    supports_sync = False
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return TorznabAdapterConfig

    @staticmethod
    def _parse_cfg(instance: ExternalSourceRecord) -> TorznabAdapterConfig:
        try:
            raw = json.loads(instance.config_json or "{}")
        except Exception:
            raw = {}
        if instance.base_url and not raw.get("base_url"):
            raw["base_url"] = instance.base_url
        return TorznabAdapterConfig.model_validate(raw)

    async def search(
        self,
        instance: ExternalSourceRecord,
        query_ctx: SourceQueryContext,
        sources_session: Optional[Session] = None,
        mainstream_session: Optional[Session] = None,
    ) -> AdapterSearchOutcome:
        cfg = self._parse_cfg(instance)
        safe_url = validate_safe_url(cfg.base_url, ("http", "https"))
        if not safe_url:
            return AdapterSearchOutcome(
                status="error",
                message="URL Torznab inválida ou ausente.",
                releases=[],
            )

        q_term = (query_ctx.custom_query or query_ctx.original_title or query_ctx.title).strip()
        params: dict[str, str] = {"t": "search", "q": q_term}
        if cfg.api_key:
            params["apikey"] = cfg.api_key
        if cfg.categories:
            params["cat"] = cfg.categories

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            try:
                resp = await client.get(safe_url, params=params)
                if is_antibot_challenge(resp.status_code, resp.text, dict(resp.headers)):
                    return AdapterSearchOutcome(
                        status="challenge_required",
                        message="Desafio anti-bot retornado pelo indexador Torznab.",
                        challenge_url=safe_url,
                        releases=[],
                    )
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                items: list[NormalizedReleaseCandidate] = []
                for item_elem in root.findall(".//item"):
                    parsed = _parse_torznab_xml_item(item_elem, query_ctx, instance.source_key)
                    if parsed is not None:
                        items.append(parsed)
                return AdapterSearchOutcome(status="ok", releases=items[: query_ctx.limit])
            except httpx.TimeoutException:
                return AdapterSearchOutcome(
                    status="timeout",
                    message=f"Timeout ao consultar feed Torznab ({safe_url}).",
                    releases=[],
                )
            except httpx.ConnectError as exc:
                raise exc
            except Exception as exc:
                return AdapterSearchOutcome(
                    status="error",
                    message=str(exc),
                    releases=[],
                )
