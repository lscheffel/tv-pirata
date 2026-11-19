"""HTTP Sidecar adapter for Ryuk-me/Torrent-Api-py multi-site torrent search."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal, Optional
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
    extract_release_year_and_se,
    is_antibot_challenge,
    register_source_adapter,
    validate_safe_url,
)
from src.backend.services.entity_resolution import EntityResolutionService

TorrentApiPySite = Literal[
    "1337x",
    "tgx",
    "nyaasi",
    "piratebay",
    "bitsearch",
    "kickass",
    "limetorrent",
    "torlock",
]


def _parse_human_size(raw: Any) -> int:
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw or "").strip().upper()
    match = re.search(r"([\d.,]+)\s*(TB|GB|MB|KB|B)", text)
    if not match:
        return 0
    try:
        num = float(match.group(1).replace(",", ""))
    except ValueError:
        return 0
    unit = match.group(2)
    mult = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}.get(unit, 1)
    return int(num * mult)


def _infer_quality(name: str) -> str:
    low = (name or "").lower()
    if "2160p" in low or "4k" in low:
        return "4K"
    if "1080p" in low:
        return "1080p"
    if "720p" in low:
        return "720p"
    if "480p" in low or "hdtv" in low:
        return "SD"
    return "Unknown"


class TorrentApiPyConfig(BaseModel):
    """Configuration schema for Torrent-Api-py sidecar instances."""

    base_url: str = Field(
        default="http://127.0.0.1:8009",
        title="URL do Sidecar Torrent-Api-py",
    )
    site: TorrentApiPySite = Field(
        default="1337x",
        title="Indexador / Site no Sidecar",
    )
    mirrors: list[str] = Field(
        default_factory=list,
        title="Mirrors Alternativos do Sidecar",
    )
    public_web_Search_url: str = Field(
        default="https://1337x.to/search/{query}/1/",
        title="URL Web Pública para Fallback Manual no Navegador",
    )
    api_key: str = Field(
        default="",
        title="Token / API Key Opcional",
        json_schema_extra={"secret": True},
    )
    timeout_seconds: float = Field(default=6.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


@register_source_adapter
class TorrentApiPySourceAdapter(BaseSourceAdapter):
    """Adapter connecting TV Pirata to a Ryuk-me/Torrent-Api-py compatible HTTP sidecar."""

    adapter_key = "torrent_api_py"
    display_name = "Torrent-Api-py Sidecar (1337x, TGx, Nyaa...)"
    description = (
        "Conector HTTP enxuto para instâncias do Ryuk-me/Torrent-Api-py "
        "suportando múltiplos indexadores (1337x, TorrentGalaxy, Nyaa, PirateBay)."
    )
    default_source_kind = "torrent_mirrorable"
    default_media_types = "movie,tvSeries,animation"
    supports_sync = False
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return TorrentApiPyConfig

    @staticmethod
    def _parse_cfg(instance: ExternalSourceRecord) -> TorrentApiPyConfig:
        try:
            raw = json.loads(instance.config_json or "{}")
        except Exception:
            raw = {}
        if instance.base_url and not raw.get("base_url"):
            raw["base_url"] = instance.base_url
        if not raw.get("site") and instance.source_key in (
            "1337x",
            "tgx",
            "nyaasi",
            "piratebay",
            "bitsearch",
        ):
            raw["site"] = instance.source_key
        return TorrentApiPyConfig.model_validate(raw)

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
        if not query_str:
            return AdapterSearchOutcome(status="ok", releases=[])

        hosts = [cfg.base_url, *cfg.mirrors]
        valid_hosts = [
            u.rstrip("/")
            for u in (validate_safe_url(h, ("http", "https")) for h in hosts)
            if u
        ] or ["http://127.0.0.1:8009"]

        headers: dict[str, str] = {}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        target_imdb = EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
        manual_url = validate_safe_url(
            cfg.public_web_Search_url.replace("{query}", quote_plus(query_str)),
            ("http", "https"),
        )
        last_status: Literal["challenge_required", "timeout", "error"] = "error"
        last_msg: Optional[str] = None

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            for host in valid_hosts:
                endpoint = f"{host}/api/v1/search"
                try:
                    resp = await client.get(
                        endpoint,
                        params={
                            "site": cfg.site,
                            "query": query_str,
                            "limit": min(query_ctx.limit, 50),
                        },
                        headers=headers,
                    )
                    if is_antibot_challenge(resp.status_code, resp.text, dict(resp.headers)):
                        last_status = "challenge_required"
                        last_msg = f"Desafio anti-bot/CAPTCHA detectado no site {cfg.site}."
                        continue
                    resp.raise_for_status()
                    payload = resp.json()
                    if isinstance(payload, dict) and payload.get("error"):
                        err_txt = str(payload["error"])
                        if is_antibot_challenge(403, err_txt):
                            last_status = "challenge_required"
                            last_msg = err_txt
                            continue
                        last_msg = err_txt
                        continue

                    raw_items = (
                        payload.get("data")
                        if isinstance(payload, dict)
                        else (payload if isinstance(payload, list) else [])
                    ) or []

                    releases: list[NormalizedReleaseCandidate] = []
                    for item in raw_items:
                        if not isinstance(item, dict):
                            continue
                        name = str(item.get("name") or item.get("title") or "").strip()
                        if not name:
                            continue
                        magnet = validate_safe_url(item.get("magnet"), ("magnet",))
                        tor_url = validate_safe_url(item.get("torrent"), ("http", "https"))
                        ext_url = validate_safe_url(item.get("url"), ("http", "https"))
                        if not (magnet or tor_url or ext_url):
                            continue

                        info_hash = str(item.get("hash") or "").strip() or None
                        if not info_hash and magnet:
                            hm = re.search(r"btih:([a-fA-F0-9]{32,40})", magnet)
                            if hm:
                                info_hash = hm.group(1).lower()

                        yr, season, episode = extract_release_year_and_se(name)
                        item_imdb = EntityResolutionService.normalize_imdb_id(item.get("imdb_id"))
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
                                candidate_title=name,
                                candidate_year=yr,
                            )

                        digest = hashlib.sha1(
                            f"{cfg.site}:{info_hash or ext_url or name}".encode("utf-8")
                        ).hexdigest()[:16]
                        seed_val = int(
                            str(item.get("seeders") or item.get("seeds") or 0).replace(",", "")
                            or 0
                        )
                        peer_val = int(
                            str(item.get("leechers") or item.get("peers") or 0).replace(",", "")
                            or 0
                        )
                        rel_type: Literal["magnet", "torrent", "link"] = (
                            "magnet" if magnet else ("torrent" if tor_url else "link")
                        )
                        w_type = "tvSeries" if season > 0 else (query_ctx.work_type or "movie")
                        releases.append(
                            NormalizedReleaseCandidate(
                                external_id=f"{cfg.site}:{digest}",
                                imdb_id=target_imdb if conf >= 0.85 else item_imdb,
                                title=name,
                                work_type=w_type,
                                season=season,
                                episode=episode,
                                quality=_infer_quality(name),
                                seeds=seed_val,
                                peers=peer_val,
                                size_bytes=_parse_human_size(item.get("size")),
                                release_type=rel_type,
                                magnet_url=magnet,
                                torrent_url=tor_url,
                                external_url=ext_url,
                                info_hash=info_hash,
                                year=yr,
                                matched_by=matched_by,
                                match_confidence=conf,
                            )
                        )
                    return AdapterSearchOutcome(status="ok", releases=releases)
                except httpx.TimeoutException:
                    last_status = "timeout"
                    last_msg = f"Timeout ao consultar sidecar {host} ({cfg.site})."
                except httpx.ConnectError as exc:
                    raise exc
                except Exception as exc:
                    last_msg = str(exc)

        return AdapterSearchOutcome(
            status=last_status,
            message=last_msg,
            challenge_url=manual_url if last_status == "challenge_required" else None,
            releases=[],
        )
