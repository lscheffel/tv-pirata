#!/usr/bin/env python3
"""Synchronize EZTV sources, TMDB watch providers, canonical PT-BR genres, and global facets.

Runs idempotently against data/mainstream.db and data/sources.db to:
1. Cross-link and upsert 100% of EZTV shows/catalog rows from sources.db into mainstream.db.
2. Harvest real BR/US streaming availability via TMDB /discover for movies and TV series.
3. Canonicalize genres_ptbr (31 categories) and streaming_providers across all 279k+ titles.
4. Rebuild covering indexes, run ANALYZE, and precompute global_facets_v2 in sync_state.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import Session  # noqa: E402

from src.backend.core.canonical_taxonomy import (  # noqa: E402
    TMDB_DISCOVER_PROVIDERS,
    merge_canonical_genres,
    merge_canonical_providers,
)
from src.backend.core.database import (  # noqa: E402
    get_eztv_engine,
    get_mainstream_engine,
    init_db,
)
from src.backend.repositories.discovery_engine import DiscoveryEngineRepository  # noqa: E402
from src.backend.services.entity_resolution import EntityResolutionService  # noqa: E402

TMDB_API_BASE = "https://api.themoviedb.org/3"
_THREAD_LOCAL = threading.local()


def _load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def _resolve_tmdb_creds() -> tuple[Optional[str], Optional[str]]:
    _load_env()
    token = next(
        (
            os.environ[k].strip()
            for k in ("TMDB_READ_TOKEN", "TMDB_READ_ACCESS_TOKEN", "TMDB_ACCESS_TOKEN")
            if os.environ.get(k, "").strip()
        ),
        None,
    )
    api_key = next(
        (
            os.environ[k].strip()
            for k in ("TMDB_API_KEY", "TMDB_KEY")
            if os.environ.get(k, "").strip()
        ),
        None,
    )
    return token, api_key


def _get_http_session(token: Optional[str], api_key: Optional[str]) -> requests.Session:
    if not hasattr(_THREAD_LOCAL, "sess"):
        sess = requests.Session()
        headers = {"Accept": "application/json", "User-Agent": "TVPirataFacetSync/1.0"}
        params: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token.removeprefix('Bearer ').strip()}"
        elif api_key:
            params["api_key"] = api_key
        sess.headers.update(headers)
        _THREAD_LOCAL.sess = sess
        _THREAD_LOCAL.base_params = params
    return _THREAD_LOCAL.sess


def _normalize_title_key(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()


def crosslink_sources_into_mainstream(
    main_conn: sqlite3.Connection, src_conn: sqlite3.Connection
) -> tuple[int, int]:
    """Ensure every show in sources.db exists in mainstream.db with has_eztv=1."""
    print("[1/4] Cruzando e garantindo 100% de sources.db em mainstream.db...")

    by_imdb: dict[str, str] = {}
    by_tvmaze: dict[int, str] = {}
    by_title: dict[str, str] = {}

    for imdb_id, title_type, primary_title, original_title, tvmaze_id in main_conn.execute(
        "SELECT imdb_id, title_type, primary_title, original_title, tvmaze_id FROM shows"
    ):
        norm = EntityResolutionService.normalize_imdb_id(imdb_id)
        if norm:
            by_imdb[norm] = imdb_id
        if tvmaze_id:
            by_tvmaze[int(tvmaze_id)] = imdb_id
        if title_type in ("tvSeries", "tvMiniSeries"):
            for t in (primary_title, original_title):
                k = _normalize_title_key(t)
                if k and k not in by_title:
                    by_title[k] = imdb_id

    updated_links = 0
    inserted_stubs = 0
    updates: list[tuple[object, ...]] = []
    inserts: list[tuple[object, ...]] = []

    ez_rows = src_conn.execute(
        """
        SELECT id, slug, name, imdb_id, tvmaze_id, status, network,
               streaming_providers, poster_url, synopsis, genres,
               rating_score, rating_votes, premiered
        FROM shows
        """
    ).fetchall()

    for (
        ez_id,
        slug,
        name,
        raw_imdb,
        tvmaze_id,
        status,
        network,
        sp,
        poster_url,
        synopsis,
        genres,
        rating_score,
        rating_votes,
        premiered,
    ) in ez_rows:
        norm_imdb = EntityResolutionService.normalize_imdb_id(raw_imdb) if raw_imdb else ""
        target_imdb: Optional[str] = None
        match_type = "exact_imdb"

        if norm_imdb and norm_imdb in by_imdb:
            target_imdb = by_imdb[norm_imdb]
            match_type = "exact_imdb"
        elif tvmaze_id and int(tvmaze_id) in by_tvmaze:
            target_imdb = by_tvmaze[int(tvmaze_id)]
            match_type = "exact_tvmaze"
        else:
            title_k = _normalize_title_key(name)
            slug_k = _normalize_title_key((slug or "").replace("-", " "))
            if title_k and title_k in by_title:
                target_imdb = by_title[title_k]
                match_type = "title_slug"
            elif slug_k and slug_k in by_title:
                target_imdb = by_title[slug_k]
                match_type = "title_slug"

        canon_sp = ", ".join(merge_canonical_providers(sp, network)) or None
        canon_genres = ", ".join(merge_canonical_genres(genres)) or None

        if target_imdb:
            updates.append(
                (
                    ez_id,
                    slug,
                    match_type,
                    status,
                    tvmaze_id,
                    network,
                    canon_sp,
                    poster_url,
                    canon_genres,
                    target_imdb,
                )
            )
            updated_links += 1
        else:
            new_imdb = norm_imdb if norm_imdb else f"tt99{int(ez_id):010d}"
            digits = new_imdb.lstrip("t")
            imdb_num = int(digits) if digits.isdigit() else None
            start_yr = (
                int(premiered[:4])
                if premiered and len(premiered) >= 4 and premiered[:4].isdigit()
                else None
            )
            inserts.append(
                (
                    new_imdb,
                    imdb_num,
                    "tvSeries",
                    name or slug or new_imdb,
                    name or slug or new_imdb,
                    start_yr,
                    genres,
                    canon_genres,
                    float(rating_score or 0.0),
                    int(rating_votes or 0),
                    poster_url,
                    synopsis,
                    premiered,
                    network,
                    tvmaze_id,
                    status or "Running",
                    canon_sp,
                    1,
                    ez_id,
                    slug,
                    "eztv_native" if not norm_imdb else "exact_imdb",
                )
            )
            by_imdb[new_imdb] = new_imdb
            inserted_stubs += 1

    # Also cross-check active P2P CatalogShow entries in sources.db
    for (
        cat_imdb,
        cat_title,
        cat_orig,
        cat_status,
        cat_poster,
        cat_backdrop,
        cat_genres,
        cat_rating,
    ) in src_conn.execute(
        """
        SELECT imdb_id, title, original_title, status, poster_url, backdrop_url, genres, rating
        FROM catalogshow
        WHERE imdb_id IS NOT NULL AND imdb_id != ''
        """
    ):
        norm = EntityResolutionService.normalize_imdb_id(cat_imdb)
        if not norm:
            continue
        if norm in by_imdb:
            updates.append(
                (
                    None,
                    None,
                    "catalogshow_imdb",
                    cat_status,
                    None,
                    None,
                    None,
                    cat_poster,
                    ", ".join(merge_canonical_genres(cat_genres)) or None,
                    by_imdb[norm],
                )
            )
        else:
            digits = norm.lstrip("t")
            imdb_num = int(digits) if digits.isdigit() else None
            canon_genres = ", ".join(merge_canonical_genres(cat_genres)) or None
            inserts.append(
                (
                    norm,
                    imdb_num,
                    "tvSeries",
                    cat_title or norm,
                    cat_orig or cat_title or norm,
                    None,
                    cat_genres,
                    canon_genres,
                    float(cat_rating or 0.0),
                    100,
                    cat_poster,
                    None,
                    None,
                    None,
                    None,
                    cat_status,
                    None,
                    1,
                    None,
                    None,
                    "catalogshow_imdb",
                )
            )
            by_imdb[norm] = norm
            inserted_stubs += 1

    with main_conn:
        if updates:
            main_conn.executemany(
                """
                UPDATE shows SET
                    has_eztv = 1,
                    eztv_id = COALESCE(?, eztv_id),
                    eztv_slug = COALESCE(?, eztv_slug),
                    eztv_match_type = COALESCE(eztv_match_type, ?),
                    status = COALESCE(?, status),
                    tvmaze_id = COALESCE(tvmaze_id, ?),
                    network = COALESCE(network, ?),
                    streaming_providers = COALESCE(streaming_providers, ?),
                    poster_url = COALESCE(poster_url, ?),
                    genres_ptbr = COALESCE(genres_ptbr, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE imdb_id = ?
                """,
                updates,
            )
        if inserts:
            main_conn.executemany(
                """
                INSERT OR IGNORE INTO shows (
                    imdb_id, imdb_num, title_type, primary_title, original_title,
                    start_year, genres, genres_ptbr, rating_score, rating_votes,
                    poster_url, synopsis, release_date, network, tvmaze_id, status,
                    streaming_providers, has_eztv, eztv_id, eztv_slug, eztv_match_type,
                    details_fetched, tmdb_synced, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    1, 2, CURRENT_TIMESTAMP
                )
                """,
                inserts,
            )

    print(f"    -> Vinculados: {updated_links:,} | Inseridos no canônico: {inserted_stubs:,}")
    return updated_links, inserted_stubs


def _fetch_discover_page(
    media_type: str,
    provider_name: str,
    provider_id: int,
    region: str,
    page: int,
    token: Optional[str],
    api_key: Optional[str],
) -> tuple[str, str, int, list[int]]:
    sess = _get_http_session(token, api_key)
    params = {
        **_THREAD_LOCAL.base_params,
        "watch_region": region,
        "with_watch_providers": str(provider_id),
        "sort_by": "popularity.desc",
        "page": str(page),
    }
    url = f"{TMDB_API_BASE}/discover/{media_type}"
    for attempt in range(3):
        try:
            resp = sess.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("Retry-After", 1.5)))
                continue
            if resp.status_code >= 400:
                return media_type, provider_name, 0, []
            data = resp.json()
            ids = [int(item["id"]) for item in (data.get("results") or []) if item.get("id")]
            total_pages = int(data.get("total_pages") or 0)
            return media_type, provider_name, total_pages, ids
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    return media_type, provider_name, 0, []


def harvest_tmdb_discover_providers(
    skip_network: bool = False,
) -> dict[tuple[str, int], set[str]]:
    """Query TMDB /discover/{movie,tv} for real BR/US watch availability across major services."""
    if skip_network:
        print("[2/4] Harvest TMDB Discover pulado (--skip-tmdb).")
        return {}

    token, api_key = _resolve_tmdb_creds()
    if not (token or api_key):
        print("[2/4] Credenciais TMDB ausentes no .env — seguindo apenas com networks locais.")
        return {}

    print("[2/4] Coletando catálogo real de streaming BR/US via TMDB /3/discover...")
    t0 = time.perf_counter()
    discovered: dict[tuple[str, int], set[str]] = {}

    first_tasks = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for canon_name, pid, region, max_pages in TMDB_DISCOVER_PROVIDERS:
            for mtype in ("movie", "tv"):
                fut = pool.submit(
                    _fetch_discover_page, mtype, canon_name, pid, region, 1, token, api_key
                )
                first_tasks.append((fut, canon_name, pid, region, mtype, max_pages))

        follow_ups = []
        for fut, canon_name, pid, region, mtype, max_pages in first_tasks:
            mt, pname, total_pages, ids = fut.result()
            for tid in ids:
                discovered.setdefault((mt, tid), set()).add(pname)
            cap = min(total_pages, max_pages)
            for pg in range(2, cap + 1):
                follow_ups.append((mt, pname, pid, region, pg))

        print(
            f"    -> Página 1 concluída ({len(discovered):,} pares iniciais); "
            f"buscando {len(follow_ups)} páginas restantes em paralelo..."
        )
        futs = [
            pool.submit(_fetch_discover_page, mt, pname, pid, region, pg, token, api_key)
            for mt, pname, pid, region, pg in follow_ups
        ]
        for fut in as_completed(futs):
            mt, pname, _, ids = fut.result()
            for tid in ids:
                discovered.setdefault((mt, tid), set()).add(pname)

    dt = time.perf_counter() - t0
    print(f"    -> TMDB Discover concluído em {dt:.1f}s ({len(discovered):,} títulos mapeados).")
    return discovered


def canonicalize_all_shows(
    main_conn: sqlite3.Connection,
    tmdb_discovered: dict[tuple[str, int], set[str]],
) -> int:
    """Normalize genres_ptbr (31 categories) and streaming_providers across all mainstream rows."""
    print(
        "[3/4] Normalizando genres_ptbr (31 categorias) e streaming_providers em mainstream.db..."
    )
    t0 = time.perf_counter()
    updates: list[tuple[Optional[str], Optional[str], str]] = []

    cursor = main_conn.execute(
        """
        SELECT imdb_id, tmdb_id, title_type, genres, genres_ptbr, streaming_providers, network
        FROM shows
        """
    )
    for imdb_id, tmdb_id, title_type, g_en, g_pt, sp, net in cursor:
        canon_genres = merge_canonical_genres(g_pt, g_en)
        new_g_pt = ", ".join(canon_genres) if canon_genres else g_pt

        m_group = "tv" if title_type in ("tvSeries", "tvMiniSeries") else "movie"
        extra_sp = (
            ", ".join(sorted(tmdb_discovered.get((m_group, int(tmdb_id)), ())))
            if tmdb_id
            else ""
        )
        canon_sp = merge_canonical_providers(sp, extra_sp, net, keep_unknown=False)
        new_sp = ", ".join(canon_sp) if canon_sp else sp

        if new_g_pt != g_pt or new_sp != sp:
            updates.append((new_g_pt, new_sp, imdb_id))

    if updates:
        for i in range(0, len(updates), 20000):
            with main_conn:
                main_conn.executemany(
                    "UPDATE shows SET genres_ptbr = ?, streaming_providers = ? WHERE imdb_id = ?",
                    updates[i : i + 20000],
                )
    dt = time.perf_counter() - t0
    print(f"    -> {len(updates):,} registros normalizados em {dt:.2f}s.")
    return len(updates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Canonical facets & streaming provider sync")
    parser.add_argument(
        "--skip-tmdb",
        action="store_true",
        help="Pula consultas à API /discover do TMDB e normaliza apenas o que há no SQLite.",
    )
    args = parser.parse_args()

    main_db_path = PROJECT_ROOT / "data" / "mainstream.db"
    src_db_path = PROJECT_ROOT / "data" / "sources.db"

    init_db(get_mainstream_engine())

    main_conn = sqlite3.connect(str(main_db_path), timeout=60.0)
    src_conn = sqlite3.connect(str(src_db_path), timeout=60.0)
    try:
        crosslink_sources_into_mainstream(main_conn, src_conn)
        discovered = harvest_tmdb_discover_providers(skip_network=args.skip_tmdb)
        canonicalize_all_shows(main_conn, discovered)
        print("[4/4] Executando ANALYZE e materializando global_facets_v2 em sync_state...")
        with main_conn:
            main_conn.execute("ANALYZE shows;")
    finally:
        src_conn.close()
        main_conn.close()

    with Session(get_mainstream_engine()) as ms, Session(get_eztv_engine()) as ss:
        facets = DiscoveryEngineRepository.refresh_global_facets_cache(
            ms, eztv_session=ss, persist_to_sync_state=True
        )

    print("\n=== RESUMO DE FACETAS REAIS EM data/mainstream.db ===")
    for sec in ("work_types", "data_sources", "genres", "streaming_providers", "statuses"):
        items = facets.get(sec, [])
        preview = ", ".join(f"{x['key']}={x['count']:,}" for x in items[:15])
        print(f"  {sec} ({len(items)}): {preview}")


if __name__ == "__main__":
    main()
