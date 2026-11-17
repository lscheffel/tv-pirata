#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
import signal
import sqlite3
import sys
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests as std_requests
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# Lista de espelhos para failover automático caso um domínio retorne 403/5xx
MIRROR_DOMAINS = [
    "https://eztvx.to",
    "https://eztv1.xyz",
    "https://eztv.tf",
    "https://eztv.wf",
    "https://eztv.yt",
]
BASE_URL = MIRROR_DOMAINS[0]
SHOWLIST_URL = f"{BASE_URL}/showlist/"
DB_FILE = "data/sources.db"

STOP_REQUESTED = False
THREAD_LOCAL = threading.local()


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    if not STOP_REQUESTED:
        print("\n[!] Parada solicitada (Ctrl+C). Concluindo gravação das tarefas em voo...")
        STOP_REQUESTED = True
    else:
        print("\n[!!] Encerramento forçado imediato.")
        sys.exit(1)


signal.signal(signal.SIGINT, handle_sigint)


# =====================================================================
# 1. CAMADA DE PERSISTÊNCIA E MIGRAÇÃO (SQLITE)
# =====================================================================
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS shows (
            id INTEGER PRIMARY KEY,
            slug TEXT,
            name TEXT NOT NULL,
            status TEXT,
            status_note TEXT,
            rating_score REAL,
            rating_votes INTEGER DEFAULT 0,
            rating_raw TEXT,
            tooltip TEXT,
            url TEXT,
            -- Metadados de 2º e 3º Nível
            imdb_id TEXT,
            tvmaze_id INTEGER,
            poster_url TEXT,
            synopsis TEXT,
            network TEXT,
            air_day_time TEXT,
            premiered TEXT,
            genres TEXT,
            cast_members TEXT,
            -- Máquina de Estados: 0=Pendente, 1=Concluído, -1=Erro Permanente (404)
            details_fetched INTEGER DEFAULT 0,
            guide_synced INTEGER DEFAULT 0,
            last_error TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS episodes_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            show_id INTEGER NOT NULL,
            season INTEGER NOT NULL,
            episode INTEGER NOT NULL,
            title TEXT,
            airdate TEXT,
            runtime INTEGER,
            rating REAL,
            summary TEXT,
            source TEXT DEFAULT 'page', -- 'page' (2º nível) ou 'tvmaze' (3º nível)
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (show_id) REFERENCES shows(id) ON DELETE CASCADE,
            UNIQUE(show_id, season, episode)
        );

        CREATE INDEX IF NOT EXISTS idx_shows_queue_desc ON shows(details_fetched, id DESC);
        CREATE INDEX IF NOT EXISTS idx_shows_queue_asc ON shows(details_fetched, id ASC);
        CREATE INDEX IF NOT EXISTS idx_shows_status ON shows(status);
        CREATE INDEX IF NOT EXISTS idx_shows_imdb ON shows(imdb_id);
        CREATE INDEX IF NOT EXISTS idx_shows_network ON shows(network);
        CREATE INDEX IF NOT EXISTS idx_ep_catalog_show ON episodes_catalog(show_id, season, episode);
        """
    )

    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(shows);").fetchall()}
    migrations = {
        "last_error": "TEXT",
        "guide_synced": "INTEGER DEFAULT 0",
        "tvmaze_id": "INTEGER",
        "tmdb_id": "INTEGER",
        "thetvdb_id": "INTEGER",
        "backdrop_url": "TEXT",
        "streaming_providers": "TEXT",
        "metadata_sources": "TEXT",
        "episodes_count": "INTEGER DEFAULT 0",
        "max_season": "INTEGER",
        "max_episode": "INTEGER",
    }
    for col_name, col_type in migrations.items():
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE shows ADD COLUMN {col_name} {col_type};")

    conn.commit()
    return conn


def upsert_shows_level1(conn: sqlite3.Connection, shows: list[dict]) -> int:
    """Insert or update Level 1 catalog while preserving Level 2/3 progress."""
    normalized_shows = [{**s, "imdb_id": s.get("imdb_id")} for s in shows]
    query = """
        INSERT INTO shows (
            id, slug, name, status, status_note,
            rating_score, rating_votes, rating_raw, tooltip, url, imdb_id, updated_at
        ) VALUES (
            :id, :slug, :name, :status, :status_note,
            :rating_score, :rating_votes, :rating_raw, :tooltip, :url, :imdb_id, CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
            slug = excluded.slug,
            name = excluded.name,
            status = CASE
                WHEN shows.status IS NULL OR shows.status = 'Unknown' THEN excluded.status
                ELSE shows.status
            END,
            status_note = COALESCE(excluded.status_note, shows.status_note),
            rating_score = COALESCE(shows.rating_score, excluded.rating_score),
            rating_votes = CASE
                WHEN excluded.rating_votes > shows.rating_votes THEN excluded.rating_votes
                ELSE shows.rating_votes
            END,
            rating_raw = CASE
                WHEN shows.rating_raw IS NULL OR shows.rating_raw = 'N/A' THEN excluded.rating_raw
                ELSE shows.rating_raw
            END,
            tooltip = COALESCE(excluded.tooltip, shows.tooltip),
            url = excluded.url,
            imdb_id = COALESCE(shows.imdb_id, excluded.imdb_id),
            updated_at = CURRENT_TIMESTAMP;
    """
    with conn:
        conn.executemany(query, normalized_shows)
    return len(normalized_shows)


def commit_worker_result(conn: sqlite3.Connection, result: dict):
    """Grava de forma transacional na Main Thread o pacote retornado por um worker."""
    show_id = result["show_id"]
    status_type = result["status"]

    with conn:
        if status_type == "error":
            state_val = -1 if result.get("permanent") else 0
            conn.execute(
                """
                UPDATE shows
                SET details_fetched = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (state_val, (result.get("error") or "")[:500], show_id),
            )
            return

        details = result["details"]
        page_episodes = result.get("page_episodes") or []
        tvmaze_episodes = result.get("tvmaze_episodes") or []
        guide_synced = result.get("guide_synced", 0)

        conn.execute(
            """
            UPDATE shows SET
                imdb_id = COALESCE(:imdb_id, imdb_id),
                tvmaze_id = COALESCE(:tvmaze_id, tvmaze_id),
                tmdb_id = COALESCE(:tmdb_id, tmdb_id),
                thetvdb_id = COALESCE(:thetvdb_id, thetvdb_id),
                poster_url = COALESCE(:poster_url, poster_url),
                backdrop_url = COALESCE(:backdrop_url, backdrop_url),
                synopsis = COALESCE(:synopsis, synopsis),
                network = COALESCE(:network, network),
                streaming_providers = COALESCE(:streaming_providers, streaming_providers),
                metadata_sources = COALESCE(:metadata_sources, metadata_sources),
                air_day_time = COALESCE(:air_day_time, air_day_time),
                premiered = COALESCE(:premiered, premiered),
                genres = COALESCE(:genres, genres),
                cast_members = COALESCE(:cast_members, cast_members),
                status = COALESCE(:show_status, status),
                rating_score = COALESCE(:rating_score, rating_score),
                details_fetched = 1,
                guide_synced = CASE WHEN :guide_synced != 0 THEN :guide_synced ELSE guide_synced END,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :show_id
            """,
            {
                **details,
                "tmdb_id": details.get("tmdb_id"),
                "thetvdb_id": details.get("thetvdb_id"),
                "backdrop_url": details.get("backdrop_url"),
                "streaming_providers": details.get("streaming_providers"),
                "metadata_sources": details.get("metadata_sources"),
                "show_status": details.get("status"),
                "rating_score": details.get("rating_score"),
                "guide_synced": guide_synced,
                "show_id": show_id,
            },
        )

        if page_episodes:
            conn.executemany(
                """
                INSERT INTO episodes_catalog (
                    show_id, season, episode, title, airdate, source, updated_at
                ) VALUES (
                    :show_id, :season, :episode, :title, :airdate, 'page', CURRENT_TIMESTAMP
                )
                ON CONFLICT(show_id, season, episode) DO UPDATE SET
                    title = COALESCE(episodes_catalog.title, excluded.title),
                    airdate = COALESCE(episodes_catalog.airdate, excluded.airdate),
                    updated_at = CURRENT_TIMESTAMP;
                """,
                page_episodes,
            )

        if tvmaze_episodes:
            conn.executemany(
                """
                INSERT INTO episodes_catalog (
                    show_id, season, episode, title, airdate,
                    runtime, rating, summary, source, updated_at
                ) VALUES (
                    :show_id, :season, :episode, :title, :airdate,
                    :runtime, :rating, :summary, 'tvmaze', CURRENT_TIMESTAMP
                )
                ON CONFLICT(show_id, season, episode) DO UPDATE SET
                    title = excluded.title,
                    airdate = excluded.airdate,
                    runtime = excluded.runtime,
                    rating = excluded.rating,
                    summary = excluded.summary,
                    source = 'tvmaze',
                    updated_at = CURRENT_TIMESTAMP;
                """,
                tvmaze_episodes,
            )

        if page_episodes or tvmaze_episodes:
            conn.execute(
                """
                UPDATE shows
                SET
                    episodes_count = (
                        SELECT COUNT(id) FROM episodes_catalog WHERE show_id = :show_id
                    ),
                    max_season = (
                        SELECT MAX(season) FROM episodes_catalog WHERE show_id = :show_id
                    ),
                    max_episode = (
                        SELECT MAX(episode)
                        FROM episodes_catalog
                        WHERE show_id = :show_id
                          AND season = (
                              SELECT MAX(season) FROM episodes_catalog WHERE show_id = :show_id
                          )
                    )
                WHERE id = :show_id
                """,
                {"show_id": show_id},
            )


# =====================================================================
# 2. CLIENTE HTTP THREAD-SAFE COM TLS IMPERSONATION & MIRROR FAILOVER
# =====================================================================
def get_thread_session():
    if not hasattr(THREAD_LOCAL, "eztv_session"):
        if HAS_CURL_CFFI:
            # Mimetiza o handshake TLS (JA3/JA4) e HTTP/2 do Chrome real
            sess = cffi_requests.Session(impersonate="chrome124")
            sess.headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            })
        elif HAS_CLOUDSCRAPER:
            sess = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        else:
            if not getattr(THREAD_LOCAL, "warned_no_cffi", False):
                print(
                    "[!] AVISO: 'curl_cffi' não encontrado! Rode 'pip install curl_cffi' "
                    "para evitar bloqueio 403 do Cloudflare.",
                    file=sys.stderr,
                )
                THREAD_LOCAL.warned_no_cffi = True
            sess = std_requests.Session()
            sess.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            })
        THREAD_LOCAL.eztv_session = sess

    if not hasattr(THREAD_LOCAL, "api_session"):
        api_sess = std_requests.Session()
        api_sess.headers.update({"Accept": "application/json", "User-Agent": "MetadataCatalog/2.0"})
        THREAD_LOCAL.api_session = api_sess

    return THREAD_LOCAL.eztv_session, THREAD_LOCAL.api_session


def swap_mirror(url: str, new_base: str) -> str:
    """Substitui qualquer domínio de origem pelo espelho alvo preservando o path."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    return new_base.rstrip("/") + path


def is_cloudflare_challenge(resp) -> bool:
    """Detect whether an HTTP 403 response is a Cloudflare anti-bot challenge."""
    if resp.status_code != 403:
        return False
    cf_header = (resp.headers.get("cf-mitigated") or "").lower()
    if cf_header == "challenge":
        return True
    body_head = (resp.text or "")[:1500].lower()
    return "just a moment" in body_head or "challenge-platform" in body_head


def fetch_html_with_retry(
    session, url: str, max_retries: int = 5, fast_fail_on_cf: bool = False
) -> tuple[str | None, int]:
    last_exc = None

    for attempt in range(1, max_retries + 1):
        if STOP_REQUESTED:
            return None, 0

        # Na 1ª tentativa usa a URL original; nas seguintes rotaciona pelos mirrors
        mirror_base = MIRROR_DOMAINS[(attempt - 1) % len(MIRROR_DOMAINS)]
        target_url = swap_mirror(url, mirror_base) if attempt > 1 else url

        try:
            resp = session.get(target_url, timeout=25)

            if resp.status_code == 404:
                return None, 404

            if fast_fail_on_cf and is_cloudflare_challenge(resp):
                return None, 403

            if resp.status_code in (403, 429, 500, 502, 503, 504):
                wait = attempt * 2
                next_mirror = MIRROR_DOMAINS[attempt % len(MIRROR_DOMAINS)]
                print(
                    f"      [!] HTTP {resp.status_code} em {target_url}. "
                    f"Alternando para {next_mirror} em {wait}s ({attempt}/{max_retries})...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.text, resp.status_code

        except Exception as e:
            last_exc = e
            if attempt == max_retries:
                break
            time.sleep(attempt * 2)

    if last_exc:
        raise last_exc
    return None, 403


# =====================================================================
# 2B. CLIENTE OFICIAL DA API JSON DO EZTV (/api/get-torrents)
# =====================================================================
def normalize_imdb_id(raw_id: str | int | None) -> str | None:
    """Normalize numeric or 'tt'-prefixed IMDb ID to canonical 'ttXXXXXXX' format."""
    if raw_id is None:
        return None
    cleaned = str(raw_id).strip().lower()
    if not cleaned or cleaned == "0":
        return None
    digits = cleaned.lstrip("t")
    if not digits.isdigit():
        return None
    return f"tt{digits.zfill(7)}"


def extract_clean_show_title(raw_title: str, raw_filename: str = "") -> str:
    """Extract sanitized show name from an EZTV release title or filename."""
    source = (raw_title or raw_filename or "").strip()
    if not source:
        return "Unknown Show"

    clean = re.sub(r"[._]", " ", source).strip()
    pattern = re.compile(
        r"^(.*?)(?:\s+(?:s\d{1,2}(?:e\d{1,3})?|season\s+\d+|\d{1,2}x\d{1,3}"
        r"|480p|720p|1080p|2160p|4k|hdtv|web-dl|webrip|web|bluray|x264|x265|hevc|amzn|nf|dsnp))",
        re.IGNORECASE,
    )
    match = pattern.search(clean)
    if match:
        candidate = match.group(1).strip(" -_[]()")
        if candidate:
            return candidate

    clean = re.sub(r"\[.*?\]", "", clean)
    clean = re.sub(r"\b(?:EZTV|mSD|AFG|MeGusta|SYNCOPY)\b", "", clean, flags=re.IGNORECASE)
    return clean.strip(" -_[]()") or source


def slugify_show_name(name: str) -> str:
    """Build a deterministic URL-safe slug from a show name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown-show"


def compute_api_show_id(imdb_id: str | None, slug: str) -> int:
    """Derive a stable positive integer primary key for API-discovered shows."""
    if imdb_id and imdb_id.startswith("tt") and imdb_id[2:].isdigit():
        return int(imdb_id[2:])
    return (zlib.crc32(slug.encode("utf-8")) & 0x7FFFFFFF) + 1_000_000_000


def fetch_eztv_api_json(
    api_session: std_requests.Session,
    endpoint_path: str,
    params: dict | None = None,
    max_retries: int = 4,
) -> dict | None:
    """Query EZTV JSON API with automatic mirror failover."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        if STOP_REQUESTED:
            return None
        mirror_base = MIRROR_DOMAINS[(attempt - 1) % len(MIRROR_DOMAINS)]
        url = f"{mirror_base.rstrip('/')}/{endpoint_path.lstrip('/')}"
        try:
            resp = api_session.get(url, params=params, timeout=20)
            if resp.status_code in (403, 429, 500, 502, 503, 504):
                if attempt < max_retries:
                    time.sleep(attempt * 1.5)
                    continue
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(attempt * 1.5)
    if last_exc:
        raise last_exc
    return None


def _unix_to_airdate(unix_ts: int | str | None) -> str | None:
    if not unix_ts:
        return None
    try:
        ts = int(unix_ts)
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return None


def fetch_showlist_via_api(
    api_session: std_requests.Session,
    start_page: int = 1,
    max_pages: int = 20,
    delay: float = 0.2,
) -> tuple[list[dict], list[dict]]:
    """Discover unique shows and recent episodes by paginating /api/get-torrents."""
    shows_map: dict[int, dict] = {}
    episodes_map: dict[tuple[int, int, int], dict] = {}

    for offset in range(max_pages):
        if STOP_REQUESTED:
            break
        page = start_page + offset
        data = fetch_eztv_api_json(
            api_session, "/api/get-torrents", params={"limit": 100, "page": page}
        )
        if not data:
            print(f"      [!] Sem resposta da API na página {page}. Interrompendo paginação.", file=sys.stderr)
            break

        torrents = data.get("torrents") or []
        if not torrents:
            break

        for item in torrents:
            raw_title = item.get("title") or ""
            raw_filename = item.get("filename") or ""
            name = extract_clean_show_title(raw_title, raw_filename)
            slug = slugify_show_name(name)
            imdb_id = normalize_imdb_id(item.get("imdb_id"))
            show_id = compute_api_show_id(imdb_id, slug)

            if show_id not in shows_map:
                numeric_imdb = str(item.get("imdb_id") or "").strip()
                show_url = (
                    f"{BASE_URL}/api/get-torrents?imdb_id={numeric_imdb}"
                    if imdb_id and numeric_imdb.isdigit()
                    else f"{BASE_URL}/search/{slug}"
                )
                shows_map[show_id] = {
                    "id": show_id,
                    "slug": slug,
                    "name": name,
                    "status": "Unknown",
                    "status_note": None,
                    "rating_score": None,
                    "rating_votes": 0,
                    "rating_raw": "N/A",
                    "tooltip": None,
                    "url": show_url,
                    "imdb_id": imdb_id,
                }

            try:
                season = int(item.get("season") or 0)
                episode = int(item.get("episode") or 0)
            except (ValueError, TypeError):
                season, episode = 0, 0

            if season > 0 and episode > 0:
                ep_key = (show_id, season, episode)
                if ep_key not in episodes_map:
                    _, _, clean_ep_title = clean_episode_title(raw_title or raw_filename)
                    episodes_map[ep_key] = {
                        "show_id": show_id,
                        "season": season,
                        "episode": episode,
                        "title": clean_ep_title,
                        "airdate": _unix_to_airdate(item.get("date_released_unix")),
                    }

        total_count = data.get("torrents_count")
        print(
            f"  [API p.{page}/{start_page + max_pages - 1}] "
            f"{len(torrents)} torrents lidos | {len(shows_map)} séries únicas | "
            f"{len(episodes_map)} episódios (total EZTV: {total_count or '?'})"
        )

        if len(torrents) < 100:
            break
        if delay > 0 and offset + 1 < max_pages and not STOP_REQUESTED:
            time.sleep(delay)

    return list(shows_map.values()), list(episodes_map.values())


def fetch_show_torrents_via_api(
    api_session: std_requests.Session,
    show_id: int,
    imdb_id: str,
    max_pages: int = 5,
) -> list[dict]:
    """Fetch all episodes for a show from /api/get-torrents?imdb_id=..."""
    numeric_imdb = imdb_id.lower().lstrip("t").lstrip("0") or imdb_id.lower().lstrip("t")
    if not numeric_imdb or not numeric_imdb.isdigit():
        return []

    episodes_map: dict[tuple[int, int], dict] = {}
    for page in range(1, max_pages + 1):
        if STOP_REQUESTED:
            break
        data = fetch_eztv_api_json(
            api_session,
            "/api/get-torrents",
            params={"imdb_id": numeric_imdb, "limit": 100, "page": page},
        )
        if not data:
            break
        torrents = data.get("torrents") or []
        if not torrents:
            break

        for item in torrents:
            try:
                season = int(item.get("season") or 0)
                episode = int(item.get("episode") or 0)
            except (ValueError, TypeError):
                continue
            if season <= 0 or episode <= 0:
                continue

            key = (season, episode)
            _, _, clean_title = clean_episode_title(
                item.get("title") or item.get("filename") or ""
            )
            if key not in episodes_map or (not episodes_map[key]["title"] and clean_title):
                episodes_map[key] = {
                    "show_id": show_id,
                    "season": season,
                    "episode": episode,
                    "title": clean_title,
                    "airdate": _unix_to_airdate(item.get("date_released_unix")),
                }

        if len(torrents) < 100:
            break

    return list(episodes_map.values())


# =====================================================================
# 3. PARSERS (1º, 2º E 3º NÍVEL)
# =====================================================================
def parse_showlist_full(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    shows = []

    rows = soup.select('table.forum_header_border tr[name="hover"]')
    if not rows:
        rows = soup.select("table.forum_header_border tr")

    for row in rows:
        cols = row.find_all("td", class_="forum_thread_post")
        if len(cols) < 3:
            continue

        name_tag = cols[0].find("a", class_="thread_link") or cols[0].find("a")
        if not name_tag:
            continue

        name = name_tag.get_text(strip=True)
        raw_href = name_tag.get("href", "").strip()
        tooltip = name_tag.get("title", "").strip() or None

        route_match = re.search(r"/shows/(\d+)/([^/]+)/?", raw_href)
        if not route_match:
            continue

        show_id = int(route_match.group(1))
        slug = route_match.group(2)

        status_raw = " ".join(cols[1].get_text().split())
        status_parts = [p.strip() for p in status_raw.split("-", 1)]
        status_clean = status_parts[0] if status_parts else status_raw
        status_note = status_parts[1] if len(status_parts) > 1 else None

        rating_raw = " ".join(cols[2].get_text().split())
        score_match = re.search(r"(\d+(?:\.\d+)?)", rating_raw)
        votes_match = re.search(r"\((\d+)\s*votes?\)", rating_raw, re.IGNORECASE)

        shows.append({
            "id": show_id,
            "slug": slug,
            "name": name,
            "status": status_clean,
            "status_note": status_note,
            "rating_score": float(score_match.group(1)) if score_match else None,
            "rating_votes": int(votes_match.group(1)) if votes_match else 0,
            "rating_raw": rating_raw or "N/A",
            "tooltip": tooltip,
            "url": urljoin(BASE_URL, raw_href),
        })

    return shows


def clean_episode_title(raw_release_name: str) -> tuple[int | None, int | None, str | None]:
    pattern = re.compile(
        r"^(?P<show>.*?)\s*(?:S(?P<s1>\d{1,2})E(?P<e1>\d{1,3})|(?P<s2>\d{1,2})x(?P<e2>\d{1,3}))\s*(?P<rest>.*)$",
        re.IGNORECASE,
    )
    match = pattern.search(raw_release_name)
    if not match:
        return None, None, None

    s = match.group("s1") or match.group("s2")
    e = match.group("e1") or match.group("e2")
    season, episode = int(s), int(e)

    rest = match.group("rest") or ""
    tech_cutoff = re.split(
        r"\b(480p|720p|1080p|2160p|4k|WEB-DL|WEBRip|HDTV|BluRay|x264|x265|HEVC|H264|AAC|PROPER|REPACK)\b",
        rest,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    ep_title = tech_cutoff.replace(".", " ").strip(" -_[]()")
    return season, episode, (ep_title if ep_title else None)


def parse_show_metadata_page(html: str, show_id: int) -> tuple[dict, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")

    imdb_tag = soup.find("a", href=re.compile(r"imdb\.com/title/(tt\d+)", re.IGNORECASE))
    imdb_id = None
    if imdb_tag:
        m = re.search(r"(tt\d+)", imdb_tag["href"], re.IGNORECASE)
        imdb_id = m.group(1) if m else None

    poster_tag = (
        soup.select_one("td.show_info_banner_logo img")
        or soup.select_one("div.show_info_description img")
        or soup.find("img", src=re.compile(r"/ezimg/thumbs/", re.IGNORECASE))
    )
    poster_url = urljoin(BASE_URL, poster_tag["src"]) if (poster_tag and poster_tag.get("src")) else None

    desc_node = (
        soup.select_one("td.show_info_description")
        or soup.find("div", itemprop="description")
        or soup.find("meta", attrs={"name": "description"})
    )
    if desc_node:
        synopsis = (
            desc_node.get("content", "").strip()
            if desc_node.name == "meta"
            else " ".join(desc_node.get_text().split())
        )
    else:
        synopsis = None

    header_text = "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )

    def extract_field(label_pattern: str) -> str | None:
        m = re.search(rf"(?:{label_pattern})\s*:\s*([^\n\r]+)", header_text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    details = {
        "imdb_id": imdb_id,
        "tvmaze_id": None,
        "poster_url": poster_url,
        "synopsis": synopsis,
        "network": extract_field(r"Network|Channel"),
        "air_day_time": extract_field(r"Air\s*Day|Airs|Schedule"),
        "premiered": extract_field(r"Premiered|First\s*Aired|Release\s*Date"),
        "genres": extract_field(r"Genres?|Category"),
        "cast_members": extract_field(r"Cast|Stars|Starring"),
    }

    episodes_map: dict[tuple[int, int], dict] = {}
    ep_rows = soup.select('table.forum_header_border tr[name="hover"]')

    for row in ep_rows:
        ep_info_tag = row.find("a", class_="epinfo")
        if not ep_info_tag:
            continue

        raw_title = ep_info_tag.get_text(strip=True)
        season, episode, clean_title = clean_episode_title(raw_title)
        if season is None or episode is None:
            continue

        cols = row.find_all("td", class_="forum_thread_post")
        released = cols[4].get_text(strip=True) if len(cols) > 4 else None

        key = (season, episode)
        if key not in episodes_map or (not episodes_map[key]["title"] and clean_title):
            episodes_map[key] = {
                "show_id": show_id,
                "season": season,
                "episode": episode,
                "title": clean_title,
                "airdate": released,
            }

    return details, list(episodes_map.values())


def _parse_tvmaze_show_payload(
    api_session: std_requests.Session, show_id: int, show_data: dict
) -> tuple[dict, list[dict], int]:
    """Extract normalized show metadata and official episodes from a TVMaze show payload."""
    tvmaze_id = show_data.get("id")
    if not tvmaze_id:
        return {}, [], -1

    web_channel = (show_data.get("webChannel") or {}).get("name")
    tv_network = (show_data.get("network") or {}).get("name")
    network_name = web_channel or tv_network
    providers_list = list(dict.fromkeys(p for p in (web_channel, tv_network) if p))
    schedule = show_data.get("schedule") or {}
    days = ", ".join(schedule.get("days") or [])
    time_str = schedule.get("time") or ""
    air_schedule = f"{days} {time_str}".strip() or None

    genres_str = ", ".join(show_data.get("genres") or []) or None
    premiered = show_data.get("premiered")
    poster_hi = (show_data.get("image") or {}).get("original")
    clean_synopsis = (
        BeautifulSoup(show_data.get("summary") or "", "html.parser").get_text(" ", strip=True)
        or None
    )
    externals = show_data.get("externals") or {}
    imdb_ext = externals.get("imdb")

    enriched = {
        "imdb_id": normalize_imdb_id(imdb_ext),
        "tvmaze_id": tvmaze_id,
        "thetvdb_id": externals.get("thetvdb"),
        "poster_url": poster_hi,
        "synopsis": clean_synopsis,
        "network": network_name,
        "streaming_providers": ", ".join(providers_list) or None,
        "metadata_sources": "tvmaze",
        "air_day_time": air_schedule,
        "premiered": premiered,
        "genres": genres_str,
        "status": show_data.get("status"),
        "rating_score": (show_data.get("rating") or {}).get("average"),
    }

    ep_resp = api_session.get(f"https://api.tvmaze.com/shows/{tvmaze_id}/episodes", timeout=25)
    if ep_resp.status_code == 429:
        time.sleep(3)
        ep_resp = api_session.get(f"https://api.tvmaze.com/shows/{tvmaze_id}/episodes", timeout=25)
    ep_resp.raise_for_status()

    ep_records = []
    for ep in ep_resp.json():
        s = ep.get("season")
        n = ep.get("number")
        if s is None or n is None:
            continue

        ep_summary = (
            BeautifulSoup(ep.get("summary") or "", "html.parser").get_text(" ", strip=True)
            or None
        )
        ep_records.append({
            "show_id": show_id,
            "season": int(s),
            "episode": int(n),
            "title": ep.get("name"),
            "airdate": ep.get("airdate"),
            "runtime": ep.get("runtime"),
            "rating": (ep.get("rating") or {}).get("average"),
            "summary": ep_summary,
        })

    return enriched, ep_records, 1


def fetch_tvmaze_cascade(
    api_session: std_requests.Session, show_id: int, imdb_id: str
) -> tuple[dict, list[dict], int]:
    """Query TVMaze public API by IMDb ID and return (metadata, episodes, status_flag)."""
    for attempt in range(1, 4):
        resp = api_session.get(
            "https://api.tvmaze.com/lookup/shows",
            params={"imdb": imdb_id},
            timeout=20,
        )
        if resp.status_code == 404:
            return {}, [], -1
        if resp.status_code == 429:
            time.sleep(attempt * 2.5)
            continue
        resp.raise_for_status()
        break
    else:
        return {}, [], 0

    return _parse_tvmaze_show_payload(api_session, show_id, resp.json())


def fetch_tvmaze_by_name(
    api_session: std_requests.Session, show_id: int, name: str
) -> tuple[dict, list[dict], int]:
    """Resolve show metadata and IMDb ID on TVMaze by show name."""
    for attempt in range(1, 4):
        resp = api_session.get(
            "https://api.tvmaze.com/singlesearch/shows",
            params={"q": name},
            timeout=20,
        )
        if resp.status_code == 404:
            return {}, [], -1
        if resp.status_code == 429:
            time.sleep(attempt * 2.5)
            continue
        resp.raise_for_status()
        break
    else:
        return {}, [], 0

    return _parse_tvmaze_show_payload(api_session, show_id, resp.json())


def fetch_tmdb_enrichment(
    api_session: std_requests.Session, imdb_id: str, tmdb_api_key: str
) -> dict:
    """Cross-enrich show metadata, networks, and watch providers from TMDB when key is set."""
    if not tmdb_api_key or not imdb_id:
        return {}
    find_resp = api_session.get(
        f"https://api.themoviedb.org/3/find/{imdb_id}",
        params={"api_key": tmdb_api_key, "external_source": "imdb_id"},
        timeout=15,
    )
    if not find_resp.ok:
        return {}
    tv_results = find_resp.json().get("tv_results") or []
    if not tv_results:
        return {}
    tmdb_id = tv_results[0].get("id")
    if not tmdb_id:
        return {}

    detail_resp = api_session.get(
        f"https://api.themoviedb.org/3/tv/{tmdb_id}",
        params={"api_key": tmdb_api_key, "append_to_response": "watch/providers,credits"},
        timeout=15,
    )
    if not detail_resp.ok:
        return {"tmdb_id": tmdb_id}
    data = detail_resp.json()

    providers: list[str] = []
    wp_results = (data.get("watch/providers") or {}).get("results") or {}
    for region in ("BR", "US"):
        for item in (wp_results.get(region) or {}).get("flatrate") or []:
            if item.get("provider_name"):
                providers.append(item["provider_name"])
    for net in data.get("networks") or []:
        if net.get("name"):
            providers.append(net["name"])
    dedup_providers = list(dict.fromkeys(providers))

    cast_names = [
        c.get("name")
        for c in ((data.get("credits") or {}).get("cast") or [])[:6]
        if c.get("name")
    ]
    backdrop = data.get("backdrop_path")
    poster = data.get("poster_path")
    genres = [g.get("name") for g in (data.get("genres") or []) if g.get("name")]

    return {
        "tmdb_id": tmdb_id,
        "backdrop_url": f"https://image.tmdb.org/t/p/original{backdrop}" if backdrop else None,
        "poster_url": f"https://image.tmdb.org/t/p/w500{poster}" if poster else None,
        "synopsis": data.get("overview") or None,
        "status": data.get("status") or None,
        "network": dedup_providers[0] if dedup_providers else None,
        "streaming_providers": ", ".join(dedup_providers) or None,
        "genres": ", ".join(genres) or None,
        "cast_members": ", ".join(cast_names) or None,
        "rating_score": data.get("vote_average") or None,
        "premiered": data.get("first_air_date") or None,
    }


# =====================================================================
# 4. WORKER UNITÁRIO E POOL CONCORRENTE (2º + 3º NÍVEL EM CASCATA)
# =====================================================================
def process_single_show_task(
    show_id: int,
    name: str,
    url: str,
    with_level3: bool,
    delay: float,
    imdb_id: str | None = None,
    source_mode: str = "auto",
) -> dict:
    if STOP_REQUESTED:
        return {"status": "aborted", "show_id": show_id, "name": name}

    eztv_session, api_session = get_thread_session()

    try:
        details = {
            "imdb_id": imdb_id,
            "tvmaze_id": None,
            "poster_url": None,
            "synopsis": None,
            "network": None,
            "air_day_time": None,
            "premiered": None,
            "genres": None,
            "cast_members": None,
        }
        page_episodes: list[dict] = []
        tvmaze_episodes: list[dict] = []
        guide_synced = 0

        use_api_only = source_mode == "api" or (
            source_mode == "auto" and ("/api/" in (url or "") or "/search/" in (url or ""))
        )

        if not use_api_only:
            html, status_code = fetch_html_with_retry(
                eztv_session, url, max_retries=2 if source_mode == "auto" else 5,
                fast_fail_on_cf=(source_mode == "auto"),
            )
            if STOP_REQUESTED:
                return {"status": "aborted", "show_id": show_id, "name": name}

            if status_code == 404:
                return {
                    "status": "error",
                    "show_id": show_id,
                    "name": name,
                    "error": "HTTP 404 Not Found",
                    "permanent": True,
                }

            if html:
                details, page_episodes = parse_show_metadata_page(html, show_id)
                if not details.get("imdb_id") and imdb_id:
                    details["imdb_id"] = imdb_id
            elif source_mode == "html":
                return {
                    "status": "error",
                    "show_id": show_id,
                    "name": name,
                    "error": f"HTTP {status_code} on HTML page",
                    "permanent": False,
                }
            else:
                use_api_only = True

        if use_api_only:
            # Resolve missing IMDb ID (and full metadata) via TVMaze name lookup
            if not details.get("imdb_id") or with_level3:
                try:
                    if details.get("imdb_id"):
                        enriched, tvmaze_episodes, guide_synced = fetch_tvmaze_cascade(
                            api_session, show_id, details["imdb_id"]
                        )
                    else:
                        enriched, tvmaze_episodes, guide_synced = fetch_tvmaze_by_name(
                            api_session, show_id, name
                        )
                    for k, v in enriched.items():
                        if v is not None:
                            details[k] = v
                except Exception:
                    guide_synced = 0

            if details.get("imdb_id"):
                page_episodes = fetch_show_torrents_via_api(
                    api_session, show_id, details["imdb_id"]
                )
        elif with_level3 and details.get("imdb_id"):
            try:
                enriched, tvmaze_episodes, guide_synced = fetch_tvmaze_cascade(
                    api_session, show_id, details["imdb_id"]
                )
                for k, v in enriched.items():
                    if v is not None:
                        details[k] = v
            except Exception:
                guide_synced = 0

        tmdb_key = os.getenv("TMDB_API_KEY", "").strip()
        if tmdb_key and details.get("imdb_id"):
            try:
                tmdb_data = fetch_tmdb_enrichment(api_session, details["imdb_id"], tmdb_key)
                if tmdb_data:
                    for k, v in tmdb_data.items():
                        if v is not None and not details.get(k):
                            details[k] = v
                    if tmdb_data.get("streaming_providers"):
                        existing = [
                            p.strip()
                            for p in (details.get("streaming_providers") or "").split(",")
                            if p.strip()
                        ]
                        merged = list(
                            dict.fromkeys(
                                existing
                                + [
                                    p.strip()
                                    for p in tmdb_data["streaming_providers"].split(",")
                                    if p.strip()
                                ]
                            )
                        )
                        details["streaming_providers"] = ", ".join(merged)
                    sources = {
                        s.strip()
                        for s in (details.get("metadata_sources") or "").split(",")
                        if s.strip()
                    }
                    sources.add("tmdb")
                    details["metadata_sources"] = ", ".join(sorted(sources))
            except Exception:
                pass

        if delay > 0 and not STOP_REQUESTED:
            time.sleep(delay)

        return {
            "status": "ok",
            "show_id": show_id,
            "name": name,
            "details": details,
            "page_episodes": page_episodes,
            "tvmaze_episodes": tvmaze_episodes,
            "guide_synced": guide_synced,
        }

    except Exception as e:
        return {
            "status": "error",
            "show_id": show_id,
            "name": name,
            "error": str(e),
            "permanent": False,
        }


def get_progress_stats(conn: sqlite3.Connection, status_filter: str | None = None) -> dict:
    where = "WHERE LOWER(status) = LOWER(?)" if status_filter else ""
    params = (status_filter,) if status_filter else ()

    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN details_fetched = 1 THEN 1 ELSE 0 END) AS done_l2,
            SUM(CASE WHEN details_fetched = 0 THEN 1 ELSE 0 END) AS pending_l2,
            SUM(CASE WHEN details_fetched < 0 THEN 1 ELSE 0 END) AS failed_l2,
            SUM(CASE WHEN guide_synced = 1 THEN 1 ELSE 0 END) AS done_l3
        FROM shows
        {where}
        """,
        params,
    ).fetchone()

    return {
        "total": row[0] or 0,
        "done_l2": row[1] or 0,
        "pending_l2": row[2] or 0,
        "failed_l2": row[3] or 0,
        "done_l3": row[4] or 0,
    }


def run_concurrent_pipeline(
    conn: sqlite3.Connection,
    workers: int = 5,
    order: str = "newest",
    limit: int | None = None,
    delay: float = 0.5,
    status_filter: str | None = None,
    specific_ids: list[int] | None = None,
    with_level3: bool = False,
    source_mode: str = "auto",
):
    stats = get_progress_stats(conn, status_filter)
    if order == "newest":
        order_clause = "id DESC"
    elif order == "oldest":
        order_clause = "id ASC"
    else:
        order_clause = "rating_votes DESC, rating_score DESC"

    params = []
    if specific_ids:
        placeholders = ",".join("?" for _ in specific_ids)
        query = (
            f"SELECT id, name, url, imdb_id FROM shows WHERE id IN ({placeholders}) "
            f"ORDER BY {order_clause}"
        )
        params.extend(specific_ids)
    else:
        query = "SELECT id, name, url, imdb_id FROM shows WHERE details_fetched = 0"
        if status_filter:
            query += " AND LOWER(status) = LOWER(?)"
            params.append(status_filter)
        query += f" ORDER BY {order_clause}"
        if limit and limit > 0:
            query += " LIMIT ?"
            params.append(limit)

    targets = conn.execute(query, params).fetchall()
    total_batch = len(targets)

    if total_batch == 0:
        print("[*] Nenhuma série pendente na fila para os critérios informados.")
        return

    cascade_label = "ATIVADA (2º -> 3º Nível TVMaze)" if with_level3 else "DESATIVADA (Apenas 2º Nível)"
    engine_label = "curl_cffi (Chrome TLS)" if HAS_CURL_CFFI else ("cloudscraper" if HAS_CLOUDSCRAPER else "requests")
    print(
        f"\n[*] Iniciando Worker Pool ({engine_label} | source={source_mode}): {workers} workers | "
        f"Lote: {total_batch} série(s) | Ordem: {order.upper()} | Cascata L3: {cascade_label}"
    )

    start_time = time.time()
    completed_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        target_iter = iter(targets)
        active_futures = {}

        for _ in range(min(total_batch, workers * 2)):
            item = next(target_iter, None)
            if item:
                fut = executor.submit(
                    process_single_show_task,
                    item[0],
                    item[1],
                    item[2],
                    with_level3,
                    delay,
                    item[3],
                    source_mode,
                )
                active_futures[fut] = item

        while active_futures:
            for fut in as_completed(list(active_futures.keys())):
                active_futures.pop(fut)
                res = fut.result()

                if res["status"] == "aborted":
                    continue

                commit_worker_result(conn, res)
                completed_count += 1

                elapsed = time.time() - start_time
                rate = completed_count / elapsed if elapsed > 0 else 0
                remaining = total_batch - completed_count
                eta_str = str(timedelta(seconds=int(remaining / rate))) if rate > 0 else "--:--:--"

                global_done = stats["done_l2"] + completed_count
                global_pct = (global_done / stats["total"] * 100) if stats["total"] else 100.0

                if res["status"] == "ok":
                    det = res["details"]
                    ep_l2 = len(res["page_episodes"])
                    ep_l3 = len(res["tvmaze_episodes"])
                    l3_tag = f" | L3(TVMaze): {ep_l3} eps" if with_level3 else ""
                    print(
                        f"  [{completed_count}/{total_batch} | Global: {global_pct:.1f}% | {rate:.2f} s/s | ETA: {eta_str}] "
                        f"ID={res['show_id']} '{res['name']}' -> IMDb: {det['imdb_id'] or 'N/A'} | "
                        f"L2: {ep_l2} eps{l3_tag}"
                    )
                else:
                    tag = "404 Ignorado" if res.get("permanent") else f"Erro Temp: {res.get('error')}"
                    print(f"  [{completed_count}/{total_batch}] ID={res['show_id']} '{res['name']}' -> [{tag}]")

                if not STOP_REQUESTED:
                    next_item = next(target_iter, None)
                    if next_item:
                        new_fut = executor.submit(
                            process_single_show_task,
                            next_item[0],
                            next_item[1],
                            next_item[2],
                            with_level3,
                            delay,
                            next_item[3],
                            source_mode,
                        )
                        active_futures[new_fut] = next_item

                break

    final_stats = get_progress_stats(conn, status_filter)
    print(
        f"\n[+] Sessão salva! 2º Nível: {final_stats['done_l2']}/{final_stats['total']} concluídos | "
        f"3º Nível (TVMaze): {final_stats['done_l3']} sincronizados | "
        f"Pendentes na fila: {final_stats['pending_l2']}"
    )


# =====================================================================
# 5. DIAGNÓSTICO E INSPEÇÃO DO BANCO (--stats)
# =====================================================================
def print_database_diagnostics(conn: sqlite3.Connection):
    overview = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN details_fetched = 1 THEN 1 ELSE 0 END) AS l2_done,
            SUM(CASE WHEN details_fetched = 0 THEN 1 ELSE 0 END) AS l2_pending,
            SUM(CASE WHEN details_fetched < 0 THEN 1 ELSE 0 END) AS l2_failed,
            SUM(CASE WHEN imdb_id IS NOT NULL AND imdb_id != '' THEN 1 ELSE 0 END) AS has_imdb,
            SUM(CASE WHEN details_fetched = 1 AND (imdb_id IS NULL OR imdb_id = '') THEN 1 ELSE 0 END) AS missing_imdb,
            SUM(CASE WHEN guide_synced = 1 THEN 1 ELSE 0 END) AS l3_done,
            SUM(CASE WHEN guide_synced < 0 THEN 1 ELSE 0 END) AS l3_not_found
        FROM shows;
        """
    ).fetchone()

    ep_stats = conn.execute(
        """
        SELECT
            COUNT(*) AS total_eps,
            COUNT(DISTINCT show_id) AS shows_with_eps,
            SUM(CASE WHEN source = 'tvmaze' THEN 1 ELSE 0 END) AS from_tvmaze,
            SUM(CASE WHEN source = 'page' THEN 1 ELSE 0 END) AS from_page
        FROM episodes_catalog;
        """
    ).fetchone()

    total = overview[0] or 0
    l2_done = overview[1] or 0
    pct_l2 = (l2_done / total * 100) if total else 0.0

    print("\n" + "=" * 72)
    print(" DIAGNÓSTICO E INSPEÇÃO DO CATÁLOGO SQLITE")
    print("=" * 72)
    print(f" Total de Séries (1º Nível)       : {total:,}")
    print(f" 2º Nível Concluído (Ficha EZTV)  : {l2_done:,} ({pct_l2:.1f}%)")
    print(f" 2º Nível Pendente na Fila        : {overview[2] or 0:,}")
    print(f" 2º Nível com Erro 404            : {overview[3] or 0:,}")
    print(f" Séries com IMDb ID Identificado  : {overview[4] or 0:,} (Sem IMDb após L2: {overview[5] or 0:,})")
    print(f" 3º Nível Sincronizado (TVMaze)   : {overview[6] or 0:,} (Não localizadas na API: {overview[7] or 0:,})")
    print("-" * 72)
    print(f" Total de Episódios Catalogados   : {ep_stats[0] or 0:,} (em {ep_stats[1] or 0:,} séries)")
    print(f"   ├─ Origem 3º Nível (TVMaze)    : {ep_stats[2] or 0:,}")
    print(f"   └─ Origem 2º Nível (Página)    : {ep_stats[3] or 0:,}")

    print("\n [Distribuição por Status]")
    for status, qty in conn.execute(
        "SELECT COALESCE(status, 'N/A'), COUNT(*) FROM shows GROUP BY status ORDER BY COUNT(*) DESC LIMIT 6;"
    ):
        print(f"   • {status:<18}: {qty:,}")

    networks = conn.execute(
        """
        SELECT network, COUNT(*) AS qtd
        FROM shows
        WHERE network IS NOT NULL AND network != ''
        GROUP BY network
        ORDER BY qtd DESC
        LIMIT 10;
        """
    ).fetchall()
    if networks:
        print("\n [Top 10 Emissoras / Networks (Séries Processadas)]")
        for net, qty in networks:
            print(f"   • {net:<28}: {qty:,} séries")

    years = conn.execute(
        """
        SELECT SUBSTR(premiered, 1, 4) AS ano, COUNT(*) AS qtd
        FROM shows
        WHERE premiered IS NOT NULL AND LENGTH(premiered) >= 4
        GROUP BY ano
        HAVING ano GLOB '[1-2][0-9][0-9][0-9]'
        ORDER BY ano DESC
        LIMIT 10;
        """
    ).fetchall()
    if years:
        print("\n [Séries por Ano de Estreia (10 Anos Mais Recentes)]")
        for yr, qty in years:
            print(f"   • {yr}: {qty:,} séries")

    print("=" * 72 + "\n")


# =====================================================================
# 6. CLI PRINCIPAL
# =====================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Catálogo Concorrente e Resumível de Metadados de Séries em SQLite"
    )
    parser.add_argument("--db", default=DB_FILE, help="Arquivo do banco SQLite (padrão: eztv_metadata.db)")
    parser.add_argument("--stats", action="store_true", help="Exibe relatório completo de diagnóstico e inspeção do banco")
    parser.add_argument("--skip-level1", action="store_true", help="Pula a atualização da /showlist/ e retoma direto a fila")
    parser.add_argument("--deep-all", action="store_true", help="Roda o 2º nível em TODAS as séries pendentes do catálogo")
    parser.add_argument("--deep", type=int, default=0, help="Roda o 2º nível em um lote específico de N séries pendentes")
    parser.add_argument("--workers", type=int, default=5, help="Número de workers paralelos (padrão: 5)")
    parser.add_argument(
        "--with-level3",
        action="store_true",
        help="Sincroniza automaticamente o 3º nível (TVMaze) em cascata para cada série com imdb_id",
    )
    parser.add_argument(
        "--sync-pending-level3",
        type=int,
        default=0,
        help="Sincroniza o 3º nível (TVMaze) para N séries que já têm 2º nível concluído",
    )
    parser.add_argument(
        "--order",
        choices=["newest", "oldest", "rating"],
        default="newest",
        help="Ordem da fila: 'newest' (mais recentes primeiro), 'oldest' (cronológica ID #1+) ou 'rating'",
    )
    parser.add_argument("--status", type=str, help="Filtra a fila por status (ex: Airing, Ended)")
    parser.add_argument("--ids", type=int, nargs="+", help="Força o processamento de IDs específicos")
    parser.add_argument("--retry-failed", action="store_true", help="Reinsere na fila séries marcadas com erro (-1)")
    parser.add_argument("--reset-level2", action="store_true", help="Zera o status de 2º nível de todo o banco")
    parser.add_argument("--delay", type=float, default=0.5, help="Intervalo por worker entre requisições (padrão: 0.5s)")
    parser.add_argument(
        "--source",
        choices=["auto", "api", "html"],
        default="auto",
        help="Fonte de dados EZTV: 'auto' (tenta HTML e cai para API /get-torrents se Cloudflare bloquear), 'api' ou 'html'",
    )
    parser.add_argument(
        "--api-pages",
        type=int,
        default=20,
        help="Número de páginas (100 torrents/página) a varrer na API /get-torrents no 1º nível (padrão: 20)",
    )
    parser.add_argument(
        "--api-start-page",
        type=int,
        default=1,
        help="Página inicial da API /get-torrents no 1º nível (padrão: 1)",
    )
    parser.add_argument(
        "--refresh-stale",
        type=int,
        default=0,
        help="Reenfileira séries ativas/incompletas ou sem atualização há N dias",
    )
    args = parser.parse_args()

    conn = init_db(args.db)

    if args.stats:
        print_database_diagnostics(conn)
        conn.close()
        return

    if args.reset_level2:
        with conn:
            conn.execute("UPDATE shows SET details_fetched = 0, last_error = NULL;")
        print("[*] Fila de 2º nível reiniciada (todas as séries marcadas como pendentes).")

    if args.retry_failed:
        with conn:
            c1 = conn.execute("UPDATE shows SET details_fetched = 0 WHERE details_fetched < 0;").rowcount
            c2 = conn.execute("UPDATE shows SET guide_synced = 0 WHERE guide_synced < 0;").rowcount
        print(f"[*] Reagendados: {c1} no 2º nível e {c2} no 3º nível.")

    if args.refresh_stale > 0:
        with conn:
            refreshed = conn.execute(
                """
                UPDATE shows
                SET details_fetched = 0
                WHERE details_fetched = 1
                  AND (
                    status IN ('Running', 'To Be Determined', 'In Development', 'Unknown')
                    OR status IS NULL
                    OR network IS NULL
                    OR streaming_providers IS NULL
                    OR updated_at < datetime('now', ?)
                  );
                """,
                (f"-{args.refresh_stale} days",),
            ).rowcount
        print(f"[*] Reagendadas {refreshed} série(s) desatualizadas/em andamento para refresh.")

    existing_count = conn.execute("SELECT COUNT(*) FROM shows;").fetchone()[0]
    has_l2_action = args.deep_all or args.deep > 0 or bool(args.ids) or args.sync_pending_level3 > 0

    if not args.skip_level1 and (existing_count == 0 or not has_l2_action):
        eztv_sess, api_sess = get_thread_session()
        shows: list[dict] = []
        api_episodes: list[dict] = []

        if args.source in ("auto", "html"):
            engine_name = "curl_cffi" if HAS_CURL_CFFI else ("cloudscraper" if HAS_CLOUDSCRAPER else "requests")
            print(f"[*] [1º Nível] Sincronizando catálogo base de {SHOWLIST_URL} (motor: {engine_name})...")
            try:
                html, status_code = fetch_html_with_retry(
                    eztv_sess,
                    SHOWLIST_URL,
                    max_retries=2 if args.source == "auto" else 5,
                    fast_fail_on_cf=(args.source == "auto"),
                )
            except Exception as exc:
                html, status_code = None, 0
                print(f"[!] Erro ao acessar {SHOWLIST_URL}: {exc}", file=sys.stderr)

            if html:
                shows = parse_showlist_full(html)
                if not shows and args.source == "html":
                    print("[!] HTML retornado não contém a tabela de séries (possível desafio Cloudflare).", file=sys.stderr)
                    sys.exit(1)
            elif args.source == "html":
                print("[!] Falha ao baixar a /showlist/ em todos os mirrors.", file=sys.stderr)
                sys.exit(1)
            else:
                print(
                    f"[!] /showlist/ bloqueado (HTTP {status_code or 'ERR'} - Cloudflare). "
                    "Alternando automaticamente para a API oficial /api/get-torrents..."
                )

        if not shows and args.source in ("auto", "api"):
            print(
                f"[*] [1º Nível - API] Varrendo {args.api_pages} página(s) em "
                f"{BASE_URL}/api/get-torrents (início: p.{args.api_start_page})..."
            )
            shows, api_episodes = fetch_showlist_via_api(
                api_sess,
                start_page=args.api_start_page,
                max_pages=args.api_pages,
                delay=min(args.delay, 0.3),
            )

        if not shows:
            print("[!] Nenhuma série obtida no 1º nível (HTML e API falharam).", file=sys.stderr)
            sys.exit(1)

        total = upsert_shows_level1(conn, shows)
        if api_episodes:
            with conn:
                conn.executemany(
                    """
                    INSERT INTO episodes_catalog (
                        show_id, season, episode, title, airdate, source, updated_at
                    ) VALUES (
                        :show_id, :season, :episode, :title, :airdate, 'page', CURRENT_TIMESTAMP
                    )
                    ON CONFLICT(show_id, season, episode) DO UPDATE SET
                        title = COALESCE(episodes_catalog.title, excluded.title),
                        airdate = COALESCE(episodes_catalog.airdate, excluded.airdate),
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    api_episodes,
                )
        print(f"[+] [1º Nível] {total} séries sincronizadas em '{args.db}'.")

    if args.ids:
        run_concurrent_pipeline(
            conn, workers=args.workers, order=args.order, delay=args.delay,
            specific_ids=args.ids, with_level3=args.with_level3, source_mode=args.source,
        )
    elif args.deep_all:
        run_concurrent_pipeline(
            conn, workers=args.workers, order=args.order, limit=None, delay=args.delay,
            status_filter=args.status, with_level3=args.with_level3, source_mode=args.source,
        )
    elif args.deep > 0:
        run_concurrent_pipeline(
            conn, workers=args.workers, order=args.order, limit=args.deep, delay=args.delay,
            status_filter=args.status, with_level3=args.with_level3, source_mode=args.source,
        )

    if args.sync_pending_level3 > 0:
        rows = conn.execute(
            """
            SELECT id, name, imdb_id FROM shows
            WHERE details_fetched = 1 AND imdb_id IS NOT NULL AND imdb_id != '' AND guide_synced = 0
            ORDER BY id DESC LIMIT ?
            """,
            (args.sync_pending_level3,),
        ).fetchall()
        print(f"[*] Sincronizando 3º nível retroativo para {len(rows)} série(s)...")
        _, api_sess = get_thread_session()
        for idx, (sid, sname, imdb) in enumerate(rows, 1):
            if STOP_REQUESTED:
                break
            try:
                enriched, eps, flag = fetch_tvmaze_cascade(api_sess, sid, imdb)
                commit_worker_result(conn, {
                    "status": "ok",
                    "show_id": sid,
                    "details": {
                        "imdb_id": imdb, "poster_url": None, "synopsis": None, "network": None,
                        "air_day_time": None, "premiered": None, "genres": None, "cast_members": None,
                        "tvmaze_id": None, **enriched
                    },
                    "page_episodes": [],
                    "tvmaze_episodes": eps,
                    "guide_synced": flag,
                })
                print(f"  [{idx}/{len(rows)}] ID={sid} '{sname}' ({imdb}) -> {len(eps)} episódios oficiais.")
                time.sleep(0.3)
            except Exception as e:
                print(f"  [!] Falha em '{sname}': {e}", file=sys.stderr)

    conn.close()


if __name__ == "__main__":
    main()