"""Strict 6-Tier Hierarchical Bilingual Metadata Waterfall & Cross-DB Self-Healing (ADR-015)."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx
from sqlalchemy import or_
from sqlmodel import Session, col, select

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.canonical_taxonomy import extract_tmdb_watch_providers
from src.backend.core.domain_concurrency import create_shared_http_client, domain_semaphores
from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.db import ShowRecord
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease
from src.backend.providers.sources.base import validate_safe_url

logger = logging.getLogger(__name__)

DEFAULT_BOT_HEADERS = {
    "User-Agent": (
        "TVPirata/0.8 (Audiovisual Discovery Engine; +https://github.com/loupan/tv-pirata)"
    ),
    "Accept": "application/json",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_html(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = re.sub(r"<[^>]+>", " ", html.unescape(raw))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def resolve_tmdb_credential() -> tuple[Optional[str], Optional[str]]:
    """Resolve TMDB bearer read token or v3 API key from environment without hardcoding secrets."""
    token_keys = (
        "TMDB_READ_TOKEN",
        "TMDB_READ_ACCESS_TOKEN",
        "TMDB_ACCESS_TOKEN",
        "TMDB_BEARER_TOKEN",
        "TMDB_TOKEN",
    )
    api_keys = ("TMDB_API_KEY", "TMDB_KEY")
    read_token = next(
        (os.environ[k].strip() for k in token_keys if os.environ.get(k, "").strip()),
        None,
    )
    api_key = None
    for k in api_keys:
        v = os.environ.get(k, "").strip()
        if v:
            if (v.startswith("eyJ") or len(v) > 40) and not read_token:
                read_token = v
            else:
                api_key = v
            break
    return read_token, api_key


def _needs_poster(show: IMDbCatalogShow) -> bool:
    return not (show.poster_url or "").strip()


def _needs_synopsis_ptbr(show: IMDbCatalogShow) -> bool:
    return not (show.synopsis_ptbr or "").strip()


def _needs_synopsis_en(show: IMDbCatalogShow) -> bool:
    return not (show.synopsis or "").strip()


def _is_complete_for_waterfall(show: IMDbCatalogShow) -> bool:
    return not (_needs_poster(show) or _needs_synopsis_ptbr(show) or _needs_synopsis_en(show))


def _apply_coalesce(
    show: IMDbCatalogShow,
    candidate: dict[str, Any],
    provenance: dict[str, int],
    tier_key: str,
) -> bool:
    """Fill only currently missing metadata fields on IMDbCatalogShow (RT15-02)."""
    changed = False
    poster = validate_safe_url(candidate.get("poster_url"), ("http", "https"))
    if poster and _needs_poster(show):
        show.poster_url = poster
        changed = True

    backdrop = validate_safe_url(candidate.get("backdrop_url"), ("http", "https"))
    if backdrop and not (show.backdrop_url or "").strip():
        show.backdrop_url = backdrop
        changed = True

    title_ptbr = str(candidate.get("title_ptbr") or "").strip()
    if title_ptbr and not (show.title_ptbr or "").strip():
        show.title_ptbr = title_ptbr
        changed = True

    syn_pt = _strip_html(candidate.get("synopsis_ptbr"))
    if syn_pt and len(syn_pt) >= 15 and _needs_synopsis_ptbr(show):
        show.synopsis_ptbr = syn_pt
        changed = True

    syn_en = _strip_html(candidate.get("synopsis"))
    if syn_en and len(syn_en) >= 15 and _needs_synopsis_en(show):
        show.synopsis = syn_en
        changed = True

    trailer = validate_safe_url(candidate.get("trailer_url"), ("http", "https"))
    if trailer and not (show.trailer_url or "").strip():
        show.trailer_url = trailer
        changed = True

    for scalar_attr in ("status", "network", "content_rating", "streaming_providers"):
        val = candidate.get(scalar_attr)
        if val and not (getattr(show, scalar_attr, None) or "").strip():
            setattr(show, scalar_attr, str(val).strip())
            changed = True

    if candidate.get("tmdb_id") and not show.tmdb_id:
        show.tmdb_id = int(candidate["tmdb_id"])
        changed = True
    if candidate.get("tvmaze_id") and not show.tvmaze_id:
        show.tvmaze_id = int(candidate["tvmaze_id"])
        changed = True

    if changed:
        provenance[tier_key] = provenance.get(tier_key, 0) + 1
        show.updated_at = _utc_iso()
    return changed


class CascadingMetadataEnricher:
    """Executes Cross-DB Self-Healing and the Strict 6-Tier Bilingual Waterfall (DEC-004)."""

    @staticmethod
    def cross_db_self_heal(
        mainstream_session: Session,
        sources_session: Optional[Session],
        *,
        limit: int = 500,
    ) -> dict[str, int]:
        """Bidirectionally reconcile poster/synopsis/status between EZTVShow and IMDbCatalogShow."""
        if sources_session is None:
            return {"eztv_to_mainstream": 0, "mainstream_to_eztv": 0}

        eztv_rows = list(
            sources_session.exec(
                select(EZTVShow).where(col(EZTVShow.imdb_id).is_not(None)).limit(limit)
            ).all()
        )
        if not eztv_rows:
            return {"eztv_to_mainstream": 0, "mainstream_to_eztv": 0}

        imdb_ids = list({str(r.imdb_id).strip() for r in eztv_rows if r.imdb_id})
        main_map = {
            row.imdb_id: row
            for row in mainstream_session.exec(
                select(IMDbCatalogShow).where(col(IMDbCatalogShow.imdb_id).in_(imdb_ids))
            ).all()
        }

        eztv_to_main = 0
        main_to_eztv = 0
        now_iso = _utc_iso()

        for ez in eztv_rows:
            show = main_map.get(str(ez.imdb_id or "").strip())
            if show is None:
                continue

            main_changed = False
            if ez.poster_url and not (show.poster_url or "").strip():
                safe_p = validate_safe_url(ez.poster_url, ("http", "https"))
                if safe_p:
                    show.poster_url = safe_p
                    main_changed = True
            if ez.synopsis and not (show.synopsis or "").strip():
                show.synopsis = _strip_html(ez.synopsis)
                main_changed = True
            if ez.network and not (show.network or "").strip():
                show.network = ez.network
                main_changed = True
            if ez.status and not (show.status or "").strip():
                show.status = ez.status
                main_changed = True
            if ez.streaming_providers and not (show.streaming_providers or "").strip():
                show.streaming_providers = ez.streaming_providers
                main_changed = True
            if ez.tvmaze_id and not show.tvmaze_id:
                show.tvmaze_id = ez.tvmaze_id
                main_changed = True
            if not show.has_eztv:
                show.has_eztv = 1
                show.eztv_id = ez.id
                show.eztv_slug = ez.slug
                main_changed = True
            if main_changed:
                if show.poster_url and (show.synopsis or show.synopsis_ptbr):
                    show.details_fetched = 1
                elif show.poster_url or show.synopsis or show.synopsis_ptbr:
                    show.details_fetched = max(show.details_fetched, 2)
                show.updated_at = now_iso
                mainstream_session.add(show)
                eztv_to_main += 1

            ez_changed = False
            if show.poster_url and not (ez.poster_url or "").strip():
                ez.poster_url = show.poster_url
                ez_changed = True
            best_syn = show.synopsis or show.synopsis_ptbr
            if best_syn and not (ez.synopsis or "").strip():
                ez.synopsis = best_syn
                ez_changed = True
            if show.network and not (ez.network or "").strip():
                ez.network = show.network
                ez_changed = True
            if show.status and not (ez.status or "").strip():
                ez.status = show.status
                ez_changed = True
            if show.streaming_providers and not (ez.streaming_providers or "").strip():
                ez.streaming_providers = show.streaming_providers
                ez_changed = True
            if show.tvmaze_id and not ez.tvmaze_id:
                ez.tvmaze_id = show.tvmaze_id
                ez_changed = True
            if ez_changed:
                if ez.poster_url and ez.synopsis:
                    ez.details_fetched = 1
                    ez.last_error = None
                ez.updated_at = now_iso
                sources_session.add(ez)
                main_to_eztv += 1

        if eztv_to_main:
            mainstream_session.commit()
        if main_to_eztv:
            sources_session.commit()
        if eztv_to_main or main_to_eztv:
            catalog_cache.invalidate()
            discovery_cache.invalidate()
        return {"eztv_to_mainstream": eztv_to_main, "mainstream_to_eztv": main_to_eztv}

    @staticmethod
    def _select_priority_queue(
        mainstream_session: Session,
        sources_session: Optional[Session],
        *,
        batch_size: int = 20,
    ) -> list[IMDbCatalogShow]:
        """Pick gap candidates prioritizing Media-First works: Sem Capa first, then Sem Sinopse."""
        eff_batch = max(1, min(batch_size, 100))
        priority_ids: list[str] = []
        lib_ids = [
            str(x).strip()
            for x in mainstream_session.exec(
                select(ShowRecord.imdb_id).where(col(ShowRecord.imdb_id).is_not(None))
            ).all()
            if x
        ]
        priority_ids.extend(lib_ids)

        if sources_session is not None:
            ext_ids = [
                str(x).strip()
                for x in sources_session.exec(
                    select(ExternalRelease.imdb_id)
                    .where(col(ExternalRelease.imdb_id).is_not(None))
                    .distinct()
                    .limit(400)
                ).all()
                if x
            ]
            priority_ids.extend(ext_ids)
        priority_ids = list(dict.fromkeys(priority_ids))[:500]

        missing_poster_cond = or_(
            col(IMDbCatalogShow.poster_url).is_(None),
            IMDbCatalogShow.poster_url == "",
        )
        missing_synopsis_cond = or_(
            col(IMDbCatalogShow.synopsis_ptbr).is_(None),
            IMDbCatalogShow.synopsis_ptbr == "",
            col(IMDbCatalogShow.synopsis).is_(None),
            IMDbCatalogShow.synopsis == "",
        )

        selected: list[IMDbCatalogShow] = []
        seen_imdbs: set[str] = set()

        def _append_unique(rows: list[IMDbCatalogShow]) -> None:
            for r in rows:
                if len(selected) >= eff_batch:
                    break
                if r.imdb_id not in seen_imdbs:
                    seen_imdbs.add(r.imdb_id)
                    selected.append(r)

        if priority_ids:
            p_posters = list(
                mainstream_session.exec(
                    select(IMDbCatalogShow)
                    .where(
                        col(IMDbCatalogShow.imdb_id).in_(priority_ids),
                        IMDbCatalogShow.details_fetched == 0,
                        missing_poster_cond,
                    )
                    .order_by(col(IMDbCatalogShow.rating_votes).desc())
                    .limit(eff_batch)
                ).all()
            )
            _append_unique(p_posters)

            if len(selected) < eff_batch:
                p_syn = list(
                    mainstream_session.exec(
                        select(IMDbCatalogShow)
                        .where(
                            col(IMDbCatalogShow.imdb_id).in_(priority_ids),
                            IMDbCatalogShow.details_fetched == 0,
                            missing_synopsis_cond,
                        )
                        .order_by(col(IMDbCatalogShow.rating_votes).desc())
                        .limit(eff_batch - len(selected))
                    ).all()
                )
                _append_unique(p_syn)

        if len(selected) < eff_batch:
            g_posters = list(
                mainstream_session.exec(
                    select(IMDbCatalogShow)
                    .where(
                        IMDbCatalogShow.details_fetched == 0,
                        missing_poster_cond,
                    )
                    .order_by(col(IMDbCatalogShow.rating_votes).desc())
                    .limit(eff_batch - len(selected))
                ).all()
            )
            _append_unique(g_posters)

        if len(selected) < eff_batch:
            g_syn = list(
                mainstream_session.exec(
                    select(IMDbCatalogShow)
                    .where(
                        IMDbCatalogShow.details_fetched == 0,
                        missing_synopsis_cond,
                    )
                    .order_by(col(IMDbCatalogShow.rating_votes).desc())
                    .limit(eff_batch - len(selected))
                ).all()
            )
            _append_unique(g_syn)

        return selected

    @staticmethod
    async def _fetch_tier1_imdb(client: httpx.AsyncClient, imdb_id: str) -> dict[str, Any]:
        """Tier 1: IMDb public JSON-LD + og:image HTML metadata extractor."""
        try:
            async with domain_semaphores.get("imdb"):
                resp = await client.get(
                    f"https://www.imdb.com/title/{imdb_id}/",
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        ),
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
            if resp.status_code != 200:
                return {}
            body = resp.text
            out: dict[str, Any] = {}
            ld_m = re.search(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                body,
                re.DOTALL | re.IGNORECASE,
            )
            if ld_m:
                data = json.loads(ld_m.group(1).strip())
                if isinstance(data, dict):
                    out["poster_url"] = data.get("image")
                    out["synopsis"] = data.get("description")
                    out["content_rating"] = data.get("contentRating")
                    trailer = data.get("trailer")
                    if isinstance(trailer, dict):
                        out["trailer_url"] = trailer.get("embedUrl") or trailer.get("url")
            if not out.get("poster_url"):
                og_m = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                    body,
                    re.IGNORECASE,
                )
                if og_m:
                    out["poster_url"] = og_m.group(1).strip()
            return out
        except Exception:
            return {}

    @staticmethod
    async def _fetch_tier2_tmdb(
        client: httpx.AsyncClient,
        imdb_id: str,
        read_token: Optional[str],
        api_key: Optional[str],
    ) -> dict[str, Any]:
        """Tier 2: TMDB /find + pt-BR + en-US + watch/providers."""
        if not read_token and not api_key:
            return {}
        headers = {"Accept": "application/json"}
        base_params: dict[str, str] = {}
        if read_token:
            headers["Authorization"] = f"Bearer {read_token}"
        elif api_key:
            base_params["api_key"] = api_key

        try:
            async with domain_semaphores.get("tmdb"):
                find_resp = await client.get(
                    f"https://api.themoviedb.org/3/find/{imdb_id}",
                    params={**base_params, "external_source": "imdb_id", "language": "pt-BR"},
                    headers=headers,
                )
                if find_resp.status_code != 200:
                    return {}
                f_data = find_resp.json()
                movies = f_data.get("movie_results") or []
                tvs = f_data.get("tv_results") or []
                is_movie = bool(movies)
                item = movies[0] if movies else (tvs[0] if tvs else None)
                if not isinstance(item, dict) or not item.get("id"):
                    return {}

                tmdb_id = int(item["id"])
                media_path = "movie" if is_movie else "tv"
                out: dict[str, Any] = {
                    "tmdb_id": tmdb_id,
                    "title_ptbr": item.get("title") or item.get("name"),
                    "synopsis_ptbr": item.get("overview"),
                    "poster_url": (
                        f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
                        if item.get("poster_path")
                        else None
                    ),
                    "backdrop_url": (
                        f"https://image.tmdb.org/t/p/original{item['backdrop_path']}"
                        if item.get("backdrop_path")
                        else None
                    ),
                }

                det_resp = await client.get(
                    f"https://api.themoviedb.org/3/{media_path}/{tmdb_id}",
                    params={
                        **base_params,
                        "language": "en-US",
                        "append_to_response": "watch/providers,videos",
                    },
                    headers=headers,
                )
            if det_resp.status_code == 200:
                det = det_resp.json()
                out["synopsis"] = det.get("overview")
                out["status"] = det.get("status")
                networks = det.get("networks") or []
                if networks and isinstance(networks[0], dict):
                    out["network"] = networks[0].get("name")
                wp = extract_tmdb_watch_providers(det)
                if wp:
                    out["streaming_providers"] = ", ".join(wp)
                for vid in (det.get("videos") or {}).get("results") or []:
                    if (
                        isinstance(vid, dict)
                        and vid.get("site") == "YouTube"
                        and vid.get("type") == "Trailer"
                        and vid.get("key")
                    ):
                        out["trailer_url"] = f"https://www.youtube.com/watch?v={vid['key']}"
                        break
            return out
        except Exception:
            return {}

    @staticmethod
    async def _fetch_tier3_tvmaze(client: httpx.AsyncClient, imdb_id: str) -> dict[str, Any]:
        """Tier 3: TVMaze lookup by IMDb ID."""
        try:
            async with domain_semaphores.get("tvmaze"):
                resp = await client.get(
                    "https://api.tvmaze.com/lookup/shows",
                    params={"imdb": imdb_id},
                )
            if resp.status_code != 200:
                return {}
            data = resp.json()
            if not isinstance(data, dict):
                return {}
            img = data.get("image") or {}
            net = data.get("network") or data.get("webChannel") or {}
            return {
                "tvmaze_id": data.get("id"),
                "poster_url": img.get("original") or img.get("medium"),
                "synopsis": _strip_html(data.get("summary")),
                "status": data.get("status"),
                "network": net.get("name") if isinstance(net, dict) else None,
            }
        except Exception:
            return {}

    @staticmethod
    async def _fetch_tier5_yify(client: httpx.AsyncClient, imdb_id: str) -> dict[str, Any]:
        """Tier 5: YIFY / YTS movie_details.json fallback."""
        try:
            async with domain_semaphores.get("yify"):
                resp = await client.get(
                    "https://movies-api.accel.li/api/v2/movie_details.json",
                    params={"imdb_id": imdb_id, "with_images": "true", "with_cast": "true"},
                )
            if resp.status_code != 200:
                return {}
            movie = (resp.json().get("data") or {}).get("movie") or {}
            if not isinstance(movie, dict) or not movie.get("id"):
                return {}
            yt = str(movie.get("yt_trailer_code") or "").strip()
            return {
                "poster_url": movie.get("large_cover_image") or movie.get("medium_cover_image"),
                "backdrop_url": movie.get("background_image_original"),
                "synopsis": movie.get("description_full") or movie.get("summary"),
                "trailer_url": f"https://www.youtube.com/watch?v={yt}" if yt else None,
                "content_rating": movie.get("mpa_rating"),
            }
        except Exception:
            return {}

    @staticmethod
    async def _fetch_tier6_wikidata_batch(
        client: httpx.AsyncClient, imdb_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        """Tier 6A: Batch SPARQL query on Wikidata P345 for up to 40 IMDb IDs."""
        if not imdb_ids:
            return {}
        values_clause = " ".join(f'"{i}"' for i in imdb_ids[:40])
        sparql = f"""
        SELECT ?imdb ?image ?descPt ?descEn ?ptTitle ?enTitle WHERE {{
          VALUES ?imdb {{ {values_clause} }}
          ?item wdt:P345 ?imdb .
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item schema:description ?descPt . FILTER(LANG(?descPt) = "pt") }}
          OPTIONAL {{ ?item schema:description ?descEn . FILTER(LANG(?descEn) = "en") }}
          OPTIONAL {{
            ?ptArticle schema:about ?item ;
                       schema:isPartOf <https://pt.wikipedia.org/> ;
                       schema:name ?ptTitle .
          }}
          OPTIONAL {{
            ?enArticle schema:about ?item ;
                       schema:isPartOf <https://en.wikipedia.org/> ;
                       schema:name ?enTitle .
          }}
        }}
        """
        try:
            async with domain_semaphores.get("wikidata"):
                resp = await client.get(
                    "https://query.wikidata.org/sparql",
                    params={"query": sparql, "format": "json"},
                    headers={
                        "User-Agent": DEFAULT_BOT_HEADERS["User-Agent"],
                        "Accept": "application/sparql-results+json",
                    },
                )
            if resp.status_code != 200:
                return {}
            bindings = (resp.json().get("results") or {}).get("bindings") or []
            out: dict[str, dict[str, str]] = {}
            for row in bindings:
                imdb_val = (row.get("imdb") or {}).get("value")
                if not imdb_val:
                    continue
                entry = out.setdefault(imdb_val, {})
                for src_k, dst_k in (
                    ("image", "poster_url"),
                    ("descPt", "desc_pt"),
                    ("descEn", "desc_en"),
                    ("ptTitle", "pt_title"),
                    ("enTitle", "en_title"),
                ):
                    v = (row.get(src_k) or {}).get("value")
                    if v and dst_k not in entry:
                        entry[dst_k] = v
            return out
        except Exception:
            return {}

    @staticmethod
    async def _fetch_tier6_wikipedia_summary(
        client: httpx.AsyncClient, lang: str, page_title: str
    ) -> dict[str, Any]:
        """Tier 6B: Wikipedia REST summary API for PT-BR and EN-US extracts and thumbnails."""
        try:
            slug = quote(page_title.replace(" ", "_"), safe="")
            async with domain_semaphores.get("wikipedia"):
                resp = await client.get(
                    f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}",
                    headers={"User-Agent": DEFAULT_BOT_HEADERS["User-Agent"]},
                )
            if resp.status_code != 200:
                return {}
            data = resp.json()
            extract = str(data.get("extract") or "").strip()
            thumb = (data.get("thumbnail") or {}).get("source")
            out: dict[str, Any] = {"poster_url": thumb}
            if extract:
                if lang == "pt":
                    out["synopsis_ptbr"] = extract
                else:
                    out["synopsis"] = extract
            return out
        except Exception:
            return {}

    @staticmethod
    async def _fetch_tier6_jikan(client: httpx.AsyncClient, title: str) -> dict[str, Any]:
        """Tier 6C: Jikan v4 open anime metadata fallback."""
        try:
            async with domain_semaphores.get("jikan"):
                resp = await client.get(
                    "https://api.jikan.moe/v4/anime",
                    params={"q": title, "limit": 1},
                )
            if resp.status_code != 200:
                return {}
            rows = resp.json().get("data") or []
            if not rows or not isinstance(rows[0], dict):
                return {}
            anime = rows[0]
            imgs = (anime.get("images") or {}).get("jpg") or {}
            return {
                "poster_url": imgs.get("large_image_url") or imgs.get("image_url"),
                "synopsis": anime.get("synopsis"),
            }
        except Exception:
            return {}

    @classmethod
    def prepare_metadata_batch(
        cls,
        mainstream_session: Session,
        sources_session: Optional[Session] = None,
        *,
        batch_size: int = 12,
        metadata_mode: str = "pending",
        ptbr_offset: int = 0,
        target_provider: Optional[str] = None,
    ) -> tuple[dict[str, int], list[IMDbCatalogShow], dict[str, EZTVShow]]:
        """Phase 1 (Prepare DB): run cross-DB self-heal and pick priority queue."""
        heal_stats = cls.cross_db_self_heal(mainstream_session, sources_session)
        if metadata_mode == "missing_synopsis_ptbr":
            stmt = select(IMDbCatalogShow).where(
                or_(
                    col(IMDbCatalogShow.synopsis_ptbr).is_(None),
                    col(IMDbCatalogShow.synopsis_ptbr) == "",
                ),
                col(IMDbCatalogShow.id) > max(0, ptbr_offset),
            )
            if target_provider == "tvmaze":
                stmt = stmt.where(
                    col(IMDbCatalogShow.title_type).in_(
                        ["tvSeries", "tvMiniSeries", "tv_show", "mini_series"]
                    ),
                    col(IMDbCatalogShow.tvmaze_id).is_(None),
                )
            elif target_provider == "tmdb":
                stmt = stmt.where(col(IMDbCatalogShow.tmdb_id).is_(None))
            candidates = list(
                mainstream_session.exec(
                    stmt.order_by(col(IMDbCatalogShow.id).asc()).limit(batch_size)
                ).all()
            )
        else:
            candidates = cls._select_priority_queue(
                mainstream_session, sources_session, batch_size=batch_size
            )
        ez_by_imdb: dict[str, EZTVShow] = {}
        if candidates and sources_session is not None:
            cand_ids = [c.imdb_id for c in candidates]
            for ez in sources_session.exec(
                select(EZTVShow).where(col(EZTVShow.imdb_id).in_(cand_ids))
            ).all():
                if ez.imdb_id:
                    ez_by_imdb[ez.imdb_id] = ez
        return heal_stats, candidates, ez_by_imdb

    @classmethod
    async def fetch_metadata_fanout(
        cls,
        candidates: list[IMDbCatalogShow],
        ez_by_imdb: dict[str, EZTVShow],
        *,
        timeout: float = 8.0,
        client: Optional[httpx.AsyncClient] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
        target_provider: Optional[str] = None,
    ) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        """Phase 2 (Pure HTTP Fan-out): parallel Tiers 1-5 + batch Tier 6 without DB writes."""
        if not candidates:
            return {}

        read_token, api_key = resolve_tmdb_credential()
        own_client = client is None
        http_client = client or create_shared_http_client(
            timeout=timeout, headers=DEFAULT_BOT_HEADERS
        )

        snapshots: dict[str, dict[str, Any]] = {
            s.imdb_id: {
                "imdb_id": s.imdb_id,
                "title_type": s.title_type,
                "primary_title": s.primary_title,
                "original_title": s.original_title,
                "genres": s.genres or "",
                "has_poster": not _needs_poster(s),
                "has_syn_pt": not _needs_synopsis_ptbr(s),
                "has_syn_en": not _needs_synopsis_en(s),
            }
            for s in candidates
        }
        collected: dict[str, list[tuple[str, dict[str, Any]]]] = {
            s.imdb_id: [] for s in candidates
        }

        def _mark_filled(snap: dict[str, Any], payload: dict[str, Any]) -> None:
            if payload.get("poster_url"):
                snap["has_poster"] = True
            syn_pt_clean = _strip_html(payload.get("synopsis_ptbr")) or ""
            if len(syn_pt_clean) >= 15:
                snap["has_syn_pt"] = True
            syn_en_clean = _strip_html(payload.get("synopsis")) or ""
            if len(syn_en_clean) >= 15:
                snap["has_syn_en"] = True

        def _is_done(snap: dict[str, Any]) -> bool:
            return snap["has_poster"] and snap["has_syn_pt"] and snap["has_syn_en"]

        async def _process_tiers_1_to_5(show_id: str) -> None:
            snap = snapshots[show_id]
            if on_progress is not None:
                on_progress("metadata", f"{snap['primary_title']} ({show_id})")

            if target_provider == "tmdb":
                t2 = await cls._fetch_tier2_tmdb(http_client, show_id, read_token, api_key)
                if t2:
                    collected[show_id].append(("tmdb", t2))
                    _mark_filled(snap, t2)
                return

            if target_provider == "tvmaze":
                is_tv_only = snap["title_type"] in (
                    "tvSeries",
                    "tvMiniSeries",
                    "tv_show",
                    "mini_series",
                )
                if is_tv_only:
                    t3 = await cls._fetch_tier3_tvmaze(http_client, show_id)
                    if t3:
                        collected[show_id].append(("tvmaze", t3))
                        _mark_filled(snap, t3)
                return

            if not snap["has_poster"] or not snap["has_syn_en"]:
                t1 = await cls._fetch_tier1_imdb(http_client, show_id)
                if t1:
                    collected[show_id].append(("imdb", t1))
                    _mark_filled(snap, t1)

            if not _is_done(snap):
                t2 = await cls._fetch_tier2_tmdb(http_client, show_id, read_token, api_key)
                if t2:
                    collected[show_id].append(("tmdb", t2))
                    _mark_filled(snap, t2)

            is_tv_like = snap["title_type"] in (
                "tvSeries",
                "tvMiniSeries",
                "tv_show",
                "mini_series",
            )
            if is_tv_like and (not snap["has_poster"] or not snap["has_syn_en"]):
                t3 = await cls._fetch_tier3_tvmaze(http_client, show_id)
                if t3:
                    collected[show_id].append(("tvmaze", t3))
                    _mark_filled(snap, t3)

            ez = ez_by_imdb.get(show_id)
            if ez is not None and not _is_done(snap):
                t4 = {
                    "poster_url": ez.poster_url,
                    "synopsis": ez.synopsis,
                    "status": ez.status,
                    "network": ez.network,
                    "streaming_providers": ez.streaming_providers,
                    "tvmaze_id": ez.tvmaze_id,
                }
                collected[show_id].append(("eztv", t4))
                _mark_filled(snap, t4)

            if snap["title_type"] in ("movie", "tvMovie") and (
                not snap["has_poster"] or not snap["has_syn_en"]
            ):
                t5 = await cls._fetch_tier5_yify(http_client, show_id)
                if t5:
                    collected[show_id].append(("yify", t5))
                    _mark_filled(snap, t5)

        try:
            await asyncio.gather(
                *(_process_tiers_1_to_5(s.imdb_id) for s in candidates),
                return_exceptions=True,
            )

            incomplete_ids = (
                []
                if target_provider in ("tmdb", "tvmaze")
                else [sid for sid, snap in snapshots.items() if not _is_done(snap)]
            )
            if incomplete_ids:
                wd_map = await cls._fetch_tier6_wikidata_batch(http_client, incomplete_ids)

                async def _process_tier_6(show_id: str) -> None:
                    snap = snapshots[show_id]
                    wd = wd_map.get(show_id) or {}
                    t6_payload: dict[str, Any] = {}
                    if wd.get("poster_url"):
                        img_u = wd["poster_url"]
                        if img_u.startswith("http://"):
                            img_u = "https://" + img_u[7:]
                        t6_payload["poster_url"] = img_u
                    if wd.get("pt_title") and not snap["has_syn_pt"]:
                        wp_pt = await cls._fetch_tier6_wikipedia_summary(
                            http_client, "pt", wd["pt_title"]
                        )
                        t6_payload.update({k: v for k, v in wp_pt.items() if v})
                    if wd.get("en_title") and not snap["has_syn_en"]:
                        wp_en = await cls._fetch_tier6_wikipedia_summary(
                            http_client, "en", wd["en_title"]
                        )
                        for k, v in wp_en.items():
                            if v and k not in t6_payload:
                                t6_payload[k] = v
                    if not t6_payload.get("synopsis_ptbr") and wd.get("desc_pt"):
                        t6_payload["synopsis_ptbr"] = wd["desc_pt"]
                    if not t6_payload.get("synopsis") and wd.get("desc_en"):
                        t6_payload["synopsis"] = wd["desc_en"]

                    is_anim = "animation" in snap["genres"].lower()
                    if is_anim and (
                        (not snap["has_poster"] and not t6_payload.get("poster_url"))
                        or (not snap["has_syn_en"] and not t6_payload.get("synopsis"))
                    ):
                        jk = await cls._fetch_tier6_jikan(
                            http_client, snap["original_title"] or snap["primary_title"]
                        )
                        for k, v in jk.items():
                            if v and k not in t6_payload:
                                t6_payload[k] = v

                    if t6_payload:
                        collected[show_id].append(("open_sources", t6_payload))

                await asyncio.gather(
                    *(_process_tier_6(sid) for sid in incomplete_ids),
                    return_exceptions=True,
                )
        finally:
            if own_client:
                await http_client.aclose()

        return collected

    @classmethod
    def apply_metadata_fanin(
        cls,
        mainstream_session: Session,
        sources_session: Optional[Session],
        heal_stats: dict[str, int],
        candidates: list[IMDbCatalogShow],
        ez_by_imdb: dict[str, EZTVShow],
        collected: dict[str, list[tuple[str, dict[str, Any]]]],
    ) -> dict[str, Any]:
        """Phase 3 (Fan-in DB): coalesce fetched tier payloads sequentially & commit once."""
        if not candidates:
            return {
                "processed": 0,
                "updated": 0,
                "self_heal": heal_stats,
                "provenance": {},
                "exhausted": True,
            }

        provenance: dict[str, int] = {
            "imdb": 0,
            "tmdb": 0,
            "tvmaze": 0,
            "eztv": heal_stats.get("eztv_to_mainstream", 0),
            "yify": 0,
            "open_sources": 0,
        }
        updated_count = 0

        for show in candidates:
            for tier_key, payload in collected.get(show.imdb_id, []):
                if _apply_coalesce(show, payload, provenance, tier_key) and tier_key == "tmdb":
                    show.tmdb_synced = 1

            has_p = not _needs_poster(show)
            has_s = bool((show.synopsis_ptbr or "").strip() or (show.synopsis or "").strip())
            if has_p and has_s:
                show.details_fetched = 1
            elif has_p or has_s:
                show.details_fetched = 2
            else:
                show.details_fetched = -1
            show.updated_at = _utc_iso()
            mainstream_session.add(show)
            if has_p or has_s:
                updated_count += 1

            ez = ez_by_imdb.get(show.imdb_id)
            if ez is not None and sources_session is not None:
                ez_dirty = False
                if show.poster_url and not (ez.poster_url or "").strip():
                    ez.poster_url = show.poster_url
                    ez_dirty = True
                best_s = show.synopsis or show.synopsis_ptbr
                if best_s and not (ez.synopsis or "").strip():
                    ez.synopsis = best_s
                    ez_dirty = True
                if ez_dirty:
                    ez.details_fetched = 1 if (ez.poster_url and ez.synopsis) else 2
                    ez.updated_at = _utc_iso()
                    sources_session.add(ez)

        mainstream_session.commit()
        if sources_session is not None:
            sources_session.commit()

        catalog_cache.invalidate()
        discovery_cache.invalidate()
        return {
            "processed": len(candidates),
            "updated": updated_count,
            "self_heal": heal_stats,
            "provenance": provenance,
            "exhausted": False,
        }

    @classmethod
    async def enrich_batch(
        cls,
        mainstream_session: Session,
        sources_session: Optional[Session] = None,
        *,
        batch_size: int = 12,
        timeout: float = 8.0,
        client: Optional[httpx.AsyncClient] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> dict[str, Any]:
        """Run Cross-DB Self-Healing + Strict 6-Tier Parallel Bilingual Waterfall."""
        heal_stats, candidates, ez_by_imdb = cls.prepare_metadata_batch(
            mainstream_session, sources_session, batch_size=batch_size
        )
        if not candidates:
            return {
                "processed": 0,
                "updated": 0,
                "self_heal": heal_stats,
                "provenance": {},
                "exhausted": True,
            }
        collected = await cls.fetch_metadata_fanout(
            candidates,
            ez_by_imdb,
            timeout=timeout,
            client=client,
            on_progress=on_progress,
        )
        return cls.apply_metadata_fanin(
            mainstream_session,
            sources_session,
            heal_stats,
            candidates,
            ez_by_imdb,
            collected,
        )
