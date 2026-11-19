"""HTTP Sidecar adapter for Ryuk-me/Torrent-Api-py (12 sites + /recent & /search) (ADR-014)."""

from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
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
    build_official_magnet,
    compute_title_match_confidence,
    is_antibot_challenge,
    parse_release_title_and_year,
    register_source_adapter,
    validate_safe_url,
)
from src.backend.services.entity_resolution import EntityResolutionService

TorrentApiPySite = Literal[
    "tgx",
    "nyaasi",
    "bitsearch",
    "glodls",
    "magnetdl",
    "limetorrent",
    "torlock",
    "kickass",
    "zooqle",
    "yts",
    "1337x",
    "piratebay",
]

TORRENT_API_PY_SITE_CATALOG: dict[str, dict[str, Any]] = {
    "tgx": {
        "site": "tgx",
        "display_name": "TorrentGalaxy (TGx)",
        "tier": "recommended",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://torrentgalaxy.to/torrents.php?search={query}",
        "supports_recent": True,
    },
    "nyaasi": {
        "site": "nyaasi",
        "display_name": "Nyaa.si (Anime & Donghua)",
        "tier": "recommended",
        "media_types": "animation,tvSeries,movie",
        "public_web_Search_url": "https://nyaa.si/?f=0&c=0_0&q={query}",
        "supports_recent": True,
    },
    "bitsearch": {
        "site": "bitsearch",
        "display_name": "BitSearch (DHT Meta-Index)",
        "tier": "recommended",
        "media_types": "movie,tvSeries,animation",
        "public_web_Search_url": "https://bitsearch.to/search?q={query}",
        "supports_recent": True,
    },
    "glodls": {
        "site": "glodls",
        "display_name": "GloDLS (GloTorrents)",
        "tier": "recommended",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://glodls.to/search_results.php?search={query}",
        "supports_recent": True,
    },
    "magnetdl": {
        "site": "magnetdl",
        "display_name": "MagnetDL",
        "tier": "extended",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://www.magnetdl.com/search/?q={query}",
        "supports_recent": True,
    },
    "limetorrent": {
        "site": "limetorrent",
        "display_name": "LimeTorrents",
        "tier": "extended",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://www.limetorrents.lol/search/all/{query}/",
        "supports_recent": True,
    },
    "torlock": {
        "site": "torlock",
        "display_name": "Torlock (Verified Torrents)",
        "tier": "extended",
        "media_types": "movie,tvSeries,animation",
        "public_web_Search_url": "https://www.torlock.com/all/torrents/{query}.html",
        "supports_recent": True,
    },
    "kickass": {
        "site": "kickass",
        "display_name": "KickassTorrents",
        "tier": "extended",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://kickasstorrents.to/usearch/{query}/",
        "supports_recent": True,
    },
    "zooqle": {
        "site": "zooqle",
        "display_name": "Zooqle",
        "tier": "extended",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://zooqle.com/search?q={query}",
        "supports_recent": True,
    },
    "yts": {
        "site": "yts",
        "display_name": "YTS (via Sidecar)",
        "tier": "extended",
        "media_types": "movie",
        "public_web_Search_url": "https://movies-api.accel.li/api/v2/list_movies.json?query_term={query}",
        "supports_recent": True,
    },
    "1337x": {
        "site": "1337x",
        "display_name": "1337x (Scraper Legado / Cloudflare)",
        "tier": "legacy_cloudflare",
        "media_types": "movie,tvSeries,animation",
        "public_web_Search_url": "https://1337x.to/search/{query}/1/",
        "supports_recent": True,
    },
    "piratebay": {
        "site": "piratebay",
        "display_name": "ThePirateBay (Scraper Legado / Cloudflare)",
        "tier": "legacy_cloudflare",
        "media_types": "movie,tvSeries",
        "public_web_Search_url": "https://thepiratebay.org/search.php?q={query}",
        "supports_recent": True,
    },
}


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
        return "2160p"
    if "1080p" in low and ("x265" in low or "hevc" in low):
        return "1080p.x265"
    if "1080p" in low:
        return "1080p"
    if "720p" in low:
        return "720p"
    if "480p" in low or "hdtv" in low:
        return "480p"
    return "Unknown"


class TorrentApiPyConfig(BaseModel):
    """Configuration schema for Torrent-Api-py sidecar instances (12 sites)."""

    base_url: str = Field(
        default="http://127.0.0.1:8009",
        title="URL do Sidecar Torrent-Api-py",
    )
    site: TorrentApiPySite = Field(
        default="tgx",
        title="Indexador / Site no Sidecar (tgx, nyaasi, bitsearch, glodls...)",
    )
    mirrors: list[str] = Field(
        default_factory=list,
        title="Mirrors Alternativos do Sidecar",
    )
    public_web_Search_url: str = Field(
        default="https://torrentgalaxy.to/torrents.php?search={query}",
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
    display_name = "Torrent-Api-py Sidecar (TGx, Nyaa, BitSearch, GloDLS + 8 sites)"
    description = (
        "Conector HTTP 1:N para o Ryuk-me/Torrent-Api-py cobrindo 12 provedores "
        "(tgx, nyaasi, bitsearch, glodls, magnetdl, limetorrent, torlock, kickass, zooqle, "
        "yts, 1337x, piratebay) com suporte dual a /api/v1/recent e /api/v1/search."
    )
    default_source_kind = "torrent_mirrorable"
    default_media_types = "movie,tvSeries,animation"
    supports_sync = True
    supports_search = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        return TorrentApiPyConfig

    @classmethod
    def config_json_schema(cls) -> dict[str, Any]:
        schema = super().config_json_schema()
        schema["site_catalog"] = list(TORRENT_API_PY_SITE_CATALOG.values())
        return schema

    @staticmethod
    def _parse_cfg(instance: ExternalSourceRecord) -> TorrentApiPyConfig:
        try:
            raw = json.loads(instance.config_json or "{}")
        except Exception:
            raw = {}
        if instance.base_url and not raw.get("base_url"):
            raw["base_url"] = instance.base_url
        if not raw.get("site") and instance.source_key in TORRENT_API_PY_SITE_CATALOG:
            raw["site"] = instance.source_key
        site_key = str(raw.get("site") or "tgx")
        if site_key not in TORRENT_API_PY_SITE_CATALOG:
            raw["site"] = "tgx"
            site_key = "tgx"
        if not raw.get("public_web_Search_url"):
            raw["public_web_Search_url"] = TORRENT_API_PY_SITE_CATALOG[site_key][
                "public_web_Search_url"
            ]
        return TorrentApiPyConfig.model_validate(raw)

    @staticmethod
    def _normalize_item(
        item: dict[str, Any],
        site: str,
        query_ctx: Optional[SourceQueryContext] = None,
    ) -> Optional[NormalizedReleaseCandidate]:
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            return None
        raw_magnet = validate_safe_url(item.get("magnet"), ("magnet",))
        tor_url = validate_safe_url(item.get("torrent"), ("http", "https"))
        ext_url = validate_safe_url(item.get("url"), ("http", "https"))

        info_hash = str(item.get("hash") or "").strip() or None
        if not info_hash and raw_magnet:
            hm = re.search(r"btih:([a-fA-F0-9]{32,40})", raw_magnet)
            if hm:
                info_hash = hm.group(1).lower()

        # Enrich magnet with official 10 trackers if hash is known and trackers are missing
        if info_hash and (not raw_magnet or "&tr=" not in raw_magnet):
            magnet = build_official_magnet(info_hash, name) or raw_magnet
        else:
            magnet = raw_magnet

        if not (magnet or tor_url or ext_url):
            return None

        clean_title, yr, season, episode, parsed_qual = parse_release_title_and_year(name)
        item_imdb = EntityResolutionService.normalize_imdb_id(item.get("imdb_id"))
        target_imdb = (
            EntityResolutionService.normalize_imdb_id(query_ctx.imdb_id)
            if query_ctx and query_ctx.imdb_id
            else None
        )

        if item_imdb and target_imdb and item_imdb == target_imdb:
            matched_by = "exact_imdb"
            conf = 1.0
        elif query_ctx:
            matched_by = "title_year_match"
            conf = compute_title_match_confidence(
                query_title=query_ctx.title,
                query_original_title=query_ctx.original_title,
                query_year=query_ctx.year,
                query_work_type=query_ctx.work_type,
                candidate_title=name,
                candidate_year=yr,
            )
        else:
            matched_by = "recent_feed"
            conf = 0.90 if item_imdb else 0.85

        digest = hashlib.sha1(f"{site}:{info_hash or ext_url or name}".encode("utf-8")).hexdigest()[
            :16
        ]
        seed_val = int(str(item.get("seeders") or item.get("seeds") or 0).replace(",", "") or 0)
        peer_val = int(str(item.get("leechers") or item.get("peers") or 0).replace(",", "") or 0)
        rel_type: Literal["magnet", "torrent", "link"] = (
            "magnet" if magnet else ("torrent" if tor_url else "link")
        )
        w_type = (
            "tvSeries"
            if season > 0
            else ((query_ctx.work_type if query_ctx else None) or "movie")
        )
        return NormalizedReleaseCandidate(
            external_id=f"{site}:{digest}",
            imdb_id=target_imdb if (query_ctx and conf >= 0.85) else item_imdb,
            title=clean_title if not query_ctx and clean_title else name,
            work_type=w_type,
            season=season,
            episode=episode,
            quality=parsed_qual if parsed_qual != "Unknown" else _infer_quality(name),
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

    @classmethod
    def _parse_nyaa_rss(cls, xml_text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out
        ns = "{https://nyaa.si/xmlns/nyaa}"
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            info_hash = (item.findtext(f"{ns}infoHash") or "").strip()
            seeders = (item.findtext(f"{ns}seeders") or "0").strip()
            leechers = (item.findtext(f"{ns}leechers") or "0").strip()
            size = (item.findtext(f"{ns}size") or "0 B").strip()
            tor_link = (item.findtext("link") or "").strip()
            page_url = (item.findtext("guid") or "").strip()
            out.append(
                {
                    "name": title,
                    "hash": info_hash,
                    "seeders": seeders,
                    "leechers": leechers,
                    "size": size,
                    "torrent": tor_link if tor_link.endswith(".torrent") else None,
                    "url": page_url,
                }
            )
        return out

    @classmethod
    def _parse_bitsearch_html(cls, html_text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        pattern = re.compile(
            r'href="/download/torrent/([a-fA-F0-9]{40})\?title=([^"&<>]+)"',
            re.IGNORECASE,
        )
        seen_hashes: set[str] = set()
        for match in pattern.finditer(html_text):
            info_hash = match.group(1).lower()
            if info_hash in seen_hashes:
                continue
            seen_hashes.add(info_hash)
            raw_title = html.unescape(match.group(2)).replace("+", " ").strip()
            start = max(0, match.start() - 1400)
            ctx = html_text[start : match.start()]
            seed_m = re.search(
                r'fa-arrow-up[^>]*></i>\s*<span[^>]*>([\d,]+)</span>', ctx, re.IGNORECASE
            )
            leech_m = re.search(
                r'fa-arrow-down[^>]*></i>\s*<span[^>]*>([\d,]+)</span>', ctx, re.IGNORECASE
            )
            size_m = re.search(
                r'([\d.,]+\s*(?:GB|MB|TB|KB))', ctx, re.IGNORECASE
            )
            raw_seeds = int((seed_m.group(1).replace(",", "") if seed_m else "10") or 10)
            if raw_seeds > 1_000_000:
                raw_seeds = 45
            out.append(
                {
                    "name": raw_title,
                    "hash": info_hash,
                    "seeders": raw_seeds,
                    "leechers": int((leech_m.group(1).replace(",", "") if leech_m else "2") or 2),
                    "size": size_m.group(1) if size_m else "1.5 GB",
                    "url": f"https://bitsearch.to/search?q={quote_plus(raw_title[:40])}",
                }
            )
        return out

    @classmethod
    def _parse_therarbg_json(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in payload.get("results") or []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("n") or "").strip()
            info_hash = str(row.get("h") or "").strip()
            if not name or not info_hash:
                continue
            pk = str(row.get("pk") or "")
            out.append(
                {
                    "name": name,
                    "hash": info_hash,
                    "imdb_id": row.get("i"),
                    "seeders": row.get("se") or 0,
                    "leechers": row.get("le") or 0,
                    "size": row.get("s") or 0,
                    "url": f"https://therarbg.to/post-detail/{pk}/" if pk else None,
                }
            )
        return out

    @classmethod
    def _parse_apibay_json(cls, payload: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(payload, list):
            return out
        for row in payload:
            if not isinstance(row, dict):
                continue
            info_hash = str(row.get("info_hash") or "").strip()
            name = str(row.get("name") or "").strip()
            if not name or not info_hash or set(info_hash) == {"0"}:
                continue
            out.append(
                {
                    "name": name,
                    "hash": info_hash,
                    "imdb_id": row.get("imdb"),
                    "seeders": row.get("seeders") or 0,
                    "leechers": row.get("leechers") or 0,
                    "size": row.get("size") or 0,
                }
            )
        return out

    @classmethod
    def _parse_generic_rss(cls, xml_text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            link = (item.findtext("link") or "").strip()
            enc = item.find("enclosure")
            enc_url = enc.attrib.get("url", "").strip() if enc is not None else ""
            enc_len = enc.attrib.get("length", "0") if enc is not None else "0"
            info_hash = None
            for u in (enc_url, link):
                hm = re.search(r"([a-fA-F0-9]{40})", u)
                if hm:
                    info_hash = hm.group(1).lower()
                    break
            out.append(
                {
                    "name": title,
                    "hash": info_hash,
                    "seeders": 15,
                    "leechers": 3,
                    "size": enc_len,
                    "torrent": (
                        enc_url
                        if enc_url.endswith(".torrent") or ".torrent?" in enc_url
                        else None
                    ),
                    "url": link if link.startswith("http") else None,
                }
            )
        return out

    @classmethod
    async def _fetch_native_direct_items(
        cls,
        site: str,
        *,
        query: Optional[str] = None,
        limit: int = 35,
        timeout: float = 8.0,
    ) -> list[dict[str, Any]]:
        """Direct native HTTP/RSS/JSON fallback when local 127.0.0.1:8009 sidecar is not running."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(
            timeout=max(timeout, 8.0), follow_redirects=True, headers=headers
        ) as client:
            if site == "nyaasi":
                url = (
                    f"https://nyaa.si/?page=rss&c=1_2&f=0&q={quote_plus(query)}"
                    if query
                    else "https://nyaa.si/?page=rss&c=1_2&f=0&s=seeders&o=desc"
                )
                r = await client.get(url)
                r.raise_for_status()
                return cls._parse_nyaa_rss(r.text)[:limit]

            if site == "bitsearch":
                q = query or "2024 1080p"
                r = await client.get(f"https://bitsearch.to/search?q={quote_plus(q)}")
                r.raise_for_status()
                return cls._parse_bitsearch_html(r.text)[:limit]

            if site in ("tgx", "1337x", "zooqle", "kickass"):
                if query:
                    u = f"https://therarbg.to/get-posts/keywords:{quote_plus(query)}:format:json/"
                    r = await client.get(u)
                    r.raise_for_status()
                    return cls._parse_therarbg_json(r.json())[:limit]
                items_acc: list[dict[str, Any]] = []
                for cat in ("Movies", "TV"):
                    u = f"https://therarbg.to/get-posts/category:{cat}:time:10D:format:json/"
                    r = await client.get(u)
                    if r.status_code == 200:
                        items_acc.extend(cls._parse_therarbg_json(r.json()))
                return items_acc[:limit]

            if site in ("glodls", "piratebay", "magnetdl"):
                if query:
                    r = await client.get(f"https://apibay.org/q.php?q={quote_plus(query)}")
                    r.raise_for_status()
                    return cls._parse_apibay_json(r.json())[:limit]
                items_acc = []
                for feed in (
                    "data_top100_207.json",
                    "data_top100_208.json",
                    "data_top100_200.json",
                ):
                    r = await client.get(f"https://apibay.org/precompiled/{feed}")
                    if r.status_code == 200:
                        items_acc.extend(cls._parse_apibay_json(r.json()))
                return items_acc[:limit]

            if site == "limetorrent":
                r = await client.get("https://www.limetorrents.lol/rss/")
                r.raise_for_status()
                return cls._parse_generic_rss(r.text)[:limit]

            if site == "torlock":
                r = await client.get("https://www.torlock.com/movies/rss.xml")
                r.raise_for_status()
                return cls._parse_generic_rss(r.text)[:limit]

        return []

    async def fetch_recent_candidates(
        self,
        instance: ExternalSourceRecord,
        pages: int = 1,
        limit: int = 35,
    ) -> list[NormalizedReleaseCandidate]:
        """Fetch Stage 1 recent releases from sidecar /api/v1/recent or direct native fallback."""
        cfg = self._parse_cfg(instance)
        hosts = [cfg.base_url, *cfg.mirrors]
        valid_hosts = [
            u.rstrip("/")
            for u in (validate_safe_url(h, ("http", "https")) for h in hosts)
            if u
        ] or ["http://127.0.0.1:8009"]

        headers: dict[str, str] = {}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        candidates: list[NormalizedReleaseCandidate] = []
        last_exc: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            for host in valid_hosts:
                try:
                    for page in range(1, max(1, min(pages, 5)) + 1):
                        resp = await client.get(
                            f"{host}/api/v1/recent",
                            params={"site": cfg.site, "limit": min(limit, 50), "page": page},
                            headers=headers,
                        )
                        if resp.status_code == 404:
                            resp = await client.get(
                                f"{host}/api/v1/search",
                                params={
                                    "site": cfg.site,
                                    "query": "1080p",
                                    "limit": min(limit, 50),
                                    "page": page,
                                },
                                headers=headers,
                            )
                        resp.raise_for_status()
                        payload = resp.json()
                        raw_items = (
                            payload.get("data")
                            if isinstance(payload, dict)
                            else (payload if isinstance(payload, list) else [])
                        ) or []
                        for raw in raw_items:
                            if not isinstance(raw, dict):
                                continue
                            cand = self._normalize_item(raw, cfg.site, query_ctx=None)
                            if cand:
                                candidates.append(cand)
                    return candidates
                except Exception as exc:
                    last_exc = exc
                    continue

        # Direct native HTTP/RSS/JSON fallback when localhost:8009 sidecar is offline
        try:
            direct_items = await self._fetch_native_direct_items(
                cfg.site, query=None, limit=limit, timeout=cfg.timeout_seconds
            )
            for raw in direct_items:
                cand = self._normalize_item(raw, cfg.site, query_ctx=None)
                if cand:
                    candidates.append(cand)
            if candidates:
                return candidates
        except Exception as exc:
            last_exc = last_exc or exc

        if last_exc:
            raise last_exc
        return candidates

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

        manual_url = validate_safe_url(
            cfg.public_web_Search_url.replace("{query}", quote_plus(query_str)),
            ("http", "https"),
        )
        last_status: Literal["challenge_required", "timeout", "error"] = "error"
        last_msg: Optional[str] = None
        saw_connect_error = False

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
                        cand = self._normalize_item(item, cfg.site, query_ctx=query_ctx)
                        if cand:
                            releases.append(cand)
                    return AdapterSearchOutcome(status="ok", releases=releases)
                except httpx.TimeoutException:
                    last_status = "timeout"
                    last_msg = f"Timeout ao consultar sidecar {host} ({cfg.site})."
                except httpx.ConnectError as exc:
                    saw_connect_error = True
                    last_msg = str(exc)
                    continue
                except Exception as exc:
                    last_msg = str(exc)

        # Direct native HTTP/RSS/JSON fallback when localhost:8009 sidecar is offline
        if saw_connect_error:
            try:
                direct_items = await self._fetch_native_direct_items(
                    cfg.site,
                    query=query_str,
                    limit=min(query_ctx.limit, 50),
                    timeout=cfg.timeout_seconds,
                )
                releases = []
                for item in direct_items:
                    cand = self._normalize_item(item, cfg.site, query_ctx=query_ctx)
                    if cand:
                        releases.append(cand)
                return AdapterSearchOutcome(status="ok", releases=releases)
            except Exception as exc:
                last_msg = str(exc)

        return AdapterSearchOutcome(
            status=last_status,
            message=last_msg,
            challenge_url=manual_url if last_status == "challenge_required" else None,
            releases=[],
        )
