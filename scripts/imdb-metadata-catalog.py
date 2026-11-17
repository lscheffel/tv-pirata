#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import gzip
import hashlib
import json
import os
import signal
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bs4 import BeautifulSoup

import requests as std_requests

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.backend.core.canonical_taxonomy import (  # noqa: E402
    extract_tmdb_watch_providers,
    merge_canonical_genres,
)

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


# =====================================================================
# 0. CARREGADOR NATIVO DE .ENV E CREDENCIAIS TMDB
# =====================================================================
def load_project_env():
    script_dir = Path(__file__).resolve().parent
    candidates = [
        Path.cwd() / ".env",
        script_dir.parent / ".env",
        script_dir / ".env",
    ]
    for env_path in candidates:
        if env_path.is_file():
            with open(env_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if not (val.startswith('"') or val.startswith("'")) and " #" in val:
                        val = val.split(" #", 1)[0].strip()
                    val = val.strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
            break


load_project_env()


def resolve_tmdb_credentials(cli_override: str = "") -> tuple[str | None, str | None]:
    if cli_override:
        clean = cli_override.strip()
        if clean.startswith("eyJ") or len(clean) > 40:
            return clean, None
        return None, clean

    token_keys = (
        "TMDB_READ_TOKEN", "TMDB_READ_ACCESS_TOKEN", "TMDB_ACCESS_TOKEN",
        "TMDB_BEARER_TOKEN", "TMDB_TOKEN", "IMDB_READ_TOKEN",
        "IMDB_READ_ACCESS_TOKEN", "IMDB_ACCESS_TOKEN", "IMDB_TOKEN",
        "READ_ACCESS_TOKEN", "BEARER_TOKEN",
    )
    api_keys = ("TMDB_API_KEY", "TMDB_KEY", "IMDB_API_KEY", "IMDB_KEY", "API_KEY")

    read_token = next((os.environ[k].strip() for k in token_keys if os.environ.get(k, "").strip()), None)
    api_key = None

    for k in api_keys:
        v = os.environ.get(k, "").strip()
        if v:
            if (v.startswith("eyJ") or len(v) > 40) and not read_token:
                read_token = v
            else:
                api_key = v
            break

    if not read_token and not api_key:
        for k, v in os.environ.items():
            if any(p in k.upper() for p in ("TMDB", "IMDB", "TOKEN", "API_KEY")):
                val = v.strip()
                if val.startswith("eyJ") and len(val) > 100:
                    read_token = val
                elif len(val) == 32 and all(c in "0123456789abcdefABCDEF" for c in val):
                    api_key = val

    return read_token, api_key


DATASETS_BASE = "https://datasets.imdbws.com"
FILES = {
    "basics": f"{DATASETS_BASE}/title.basics.tsv.gz",
    "ratings": f"{DATASETS_BASE}/title.ratings.tsv.gz",
    "akas": f"{DATASETS_BASE}/title.akas.tsv.gz",
    "episodes": f"{DATASETS_BASE}/title.episode.tsv.gz",
}

DEFAULT_TITLE_TYPES = ("movie", "tvMovie", "tvSeries", "tvMiniSeries")
MOVIE_TYPES = ("movie", "tvMovie")
SERIES_TYPES = ("tvSeries", "tvMiniSeries")

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/original"

DB_FILE = "data/mainstream.db"
CACHE_DIR = Path(".imdb_cache")
STOP_REQUESTED = False
THREAD_LOCAL = threading.local()


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    if not STOP_REQUESTED:
        print("\n[!] Pausa solicitada (Ctrl+C). Finalizando gravação das requisições em andamento...")
        STOP_REQUESTED = True
    else:
        print("\n[!!] Encerramento forçado imediato.")
        sys.exit(1)


signal.signal(signal.SIGINT, handle_sigint)


# =====================================================================
# 1. CAMADA DE PERSISTÊNCIA SQLITE + CONTROLE DE ESTADO (SYNC_STATE)
# =====================================================================
def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shows (
            imdb_id TEXT PRIMARY KEY,
            imdb_num INTEGER,
            tmdb_id INTEGER,
            title_type TEXT,
            primary_title TEXT NOT NULL,
            original_title TEXT,
            title_ptbr TEXT,
            tagline TEXT,
            is_adult INTEGER DEFAULT 0,
            start_year INTEGER,
            end_year INTEGER,
            runtime_minutes INTEGER,
            genres TEXT,
            genres_ptbr TEXT,
            rating_score REAL,
            rating_votes INTEGER DEFAULT 0,
            poster_url TEXT,
            backdrop_url TEXT,
            trailer_url TEXT,
            synopsis TEXT,
            synopsis_ptbr TEXT,
            content_rating TEXT,
            release_date TEXT,
            countries TEXT,
            languages TEXT,
            network TEXT,
            directors TEXT,
            creators TEXT,
            cast_members TEXT,
            keywords TEXT,
            total_seasons INTEGER,
            -- Máquinas de Estado Resumíveis:
            -- details_fetched: 0=Pendente, 1=Concluído, -1=Erro 404
            -- tmdb_synced:     0=Pendente, 1=PT-BR OK, 2=Sem Plot BR no TMDB, -1=Inexistente no TMDB
            details_fetched INTEGER DEFAULT 0,
            tmdb_synced INTEGER DEFAULT 0,
            last_error TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS episodes_catalog (
            episode_imdb_id TEXT PRIMARY KEY,
            show_imdb_id TEXT NOT NULL,
            season INTEGER,
            episode INTEGER,
            title TEXT,
            start_year INTEGER,
            runtime_minutes INTEGER,
            rating_score REAL,
            rating_votes INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (show_imdb_id) REFERENCES shows(imdb_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_shows_type ON shows(title_type);
        CREATE INDEX IF NOT EXISTS idx_shows_tmdb_id ON shows(tmdb_id);
        CREATE INDEX IF NOT EXISTS idx_shows_queue_votes ON shows(tmdb_synced, rating_votes DESC, rating_score DESC);
        CREATE INDEX IF NOT EXISTS idx_shows_queue_newest ON shows(tmdb_synced, start_year DESC, imdb_num DESC);
        CREATE INDEX IF NOT EXISTS idx_shows_queue_oldest ON shows(tmdb_synced, start_year ASC, imdb_num ASC);
        CREATE INDEX IF NOT EXISTS idx_shows_year ON shows(start_year);
        CREATE INDEX IF NOT EXISTS idx_ep_show ON episodes_catalog(show_imdb_id, season, episode);
        """
    )

    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(shows);").fetchall()}
    migrations = {
        "directors": "TEXT",
        "title_ptbr": "TEXT",
        "synopsis_ptbr": "TEXT",
        "tmdb_id": "INTEGER",
        "backdrop_url": "TEXT",
        "trailer_url": "TEXT",
        "genres_ptbr": "TEXT",
        "tagline": "TEXT",
        "network": "TEXT",
        "tmdb_synced": "INTEGER DEFAULT 0",
        "tvmaze_id": "INTEGER",
        "status": "TEXT",
        "air_day_time": "TEXT",
        "streaming_providers": "TEXT",
        "has_eztv": "INTEGER DEFAULT 0",
        "eztv_id": "INTEGER",
        "eztv_slug": "TEXT",
        "eztv_match_type": "TEXT",
    }
    for col_name, col_def in migrations.items():
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE shows ADD COLUMN {col_name} {col_def};")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_shows_ptbr ON shows(title_ptbr);")
    conn.commit()
    return conn


def get_sync_state(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM sync_state WHERE key = ?;", (key,)).fetchone()
    return row[0] if row else default


def set_sync_state(conn: sqlite3.Connection, key: str, value: str):
    with conn:
        conn.execute(
            """
            INSERT INTO sync_state (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;
            """,
            (key, value),
        )


# =====================================================================
# 2. CACHE CONDICIONAL (HTTP HEAD ETAG) + IMPORTAÇÃO DELTA DO 1º NÍVEL
# =====================================================================
def _read_cache_meta(meta_path: Path) -> dict:
    if meta_path.is_file():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write_cache_meta(meta_path: Path, headers: dict, file_size: int) -> dict:
    meta = {
        "etag": (headers.get("ETag") or "").strip('"'),
        "last_modified": (headers.get("Last-Modified") or "").strip(),
        "content_length": file_size,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def download_dataset_if_needed(name: str, url: str, force: bool = False) -> tuple[Path, str]:
    """
    Valida via HTTP HEAD (ETag / Last-Modified / Content-Length) se o arquivo remoto
    é mais novo que o arquivo local em '.imdb_cache/'.
    Retorna (caminho_local, revision_token) onde revision_token identifica unicamente a revisão.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    dest = CACHE_DIR / f"{name}.tsv.gz"
    meta_path = CACHE_DIR / f"{name}.tsv.gz.meta.json"

    remote_headers = {}
    if not force:
        try:
            head_resp = std_requests.head(url, allow_redirects=True, timeout=15)
            head_resp.raise_for_status()
            remote_headers = dict(head_resp.headers)
        except Exception as e:
            if dest.is_file():
                local_meta = _read_cache_meta(meta_path)
                rev = local_meta.get("etag") or local_meta.get("last_modified") or str(dest.stat().st_size)
                print(f"  [!] Falha ao checar versão remota ({e}). Usando cache local: {dest}")
                return dest, rev
            raise

    if dest.is_file() and not force:
        local_size = dest.stat().st_size
        local_meta = _read_cache_meta(meta_path)

        remote_etag = (remote_headers.get("ETag") or "").strip('"')
        remote_lm = (remote_headers.get("Last-Modified") or "").strip()
        remote_len_str = remote_headers.get("Content-Length")
        remote_len = int(remote_len_str) if (remote_len_str and remote_len_str.isdigit()) else None

        local_etag = local_meta.get("etag", "")
        local_lm = local_meta.get("last_modified", "")

        same_by_etag = bool(remote_etag and local_etag and remote_etag == local_etag)
        same_by_lm = bool(
            remote_lm and local_lm and remote_lm == local_lm
            and (remote_len is None or remote_len == local_size)
        )
        same_legacy_size = bool(not local_meta and remote_len is not None and remote_len == local_size)

        if same_by_etag or same_by_lm or same_legacy_size:
            if not local_meta:
                local_meta = _write_cache_meta(meta_path, remote_headers, local_size)
            size_mb = local_size / (1024 * 1024)
            rev = remote_etag or remote_lm or str(local_size)
            print(
                f"  [*] Cache válido ({dest.name} | {size_mb:.1f} MB | "
                f"Mesma versão do servidor: {remote_lm or rev[:12]}). Pulando download."
            )
            return dest, rev

        print(f"  [*] Nova revisão detectada no servidor para {dest.name} ({remote_lm or remote_etag[:12]}). Baixando...")

    print(f"  [*] Baixando {url} ...")
    with std_requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_mb = int(r.headers.get("Content-Length", 0)) / (1024 * 1024)
        downloaded = 0.0
        tmp_dest = dest.with_suffix(".tmp")
        with open(tmp_dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if STOP_REQUESTED:
                    sys.exit(1)
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk) / (1024 * 1024)
                    print(f"\r      Progresso: {downloaded:.1f} MB / {total_mb:.1f} MB", end="", flush=True)
        print()
        tmp_dest.replace(dest)
        saved_meta = _write_cache_meta(meta_path, dict(r.headers), dest.stat().st_size)
        rev = saved_meta.get("etag") or saved_meta.get("last_modified") or str(dest.stat().st_size)

    return dest, rev


def parse_int(val: str) -> int | None:
    return int(val) if (val and val != r"\N" and val.isdigit()) else None


def compute_import_signature(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def sync_br_akas_streaming(
    conn: sqlite3.Connection,
    target_title_ids: set[str] | None = None,
    since_year: int = 0,
    force_download: bool = False,
):
    if target_title_ids is None:
        sql = "SELECT imdb_id FROM shows WHERE (title_ptbr IS NULL OR title_ptbr = '')"
        params = []
        if since_year > 0:
            sql += " AND start_year >= ?"
            params.append(since_year)
        target_title_ids = {row[0] for row in conn.execute(sql, params).fetchall()}

    if not target_title_ids:
        print("  [*] Nenhum título sem 'title_ptbr' pendente.")
        return

    akas_path, akas_rev = download_dataset_if_needed("akas", FILES["akas"], force=force_download)

    akas_sig = compute_import_signature("akas", akas_rev, len(target_title_ids), since_year)
    if not force_download and get_sync_state(conn, "last_akas_import_sig") == akas_sig:
        print("  [*] AKAs BR desta revisão já foram aplicados ao banco atual. Pulando leitura TSV.")
        return

    print(f"  [*] Extraindo títulos nacionais (region='BR') para {len(target_title_ids):,} alvos...")
    br_titles: dict[str, tuple[int, str]] = {}
    with gzip.open(akas_path, "rt", encoding="utf-8") as f:
        next(f, None)
        for line in f:
            if STOP_REQUESTED:
                return
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6 or parts[3] != "BR":
                continue
            title_id = parts[0]
            if title_id not in target_title_ids:
                continue
            localized_title = parts[2]
            if not localized_title or localized_title == r"\N":
                continue
            priority = 2 if "imdbDisplay" in parts[5] else 1
            existing = br_titles.get(title_id)
            if existing is None or priority > existing[0]:
                br_titles[title_id] = (priority, localized_title)

    if br_titles:
        update_batch = [(val[1], tid) for tid, val in br_titles.items()]
        for i in range(0, len(update_batch), 20000):
            if STOP_REQUESTED:
                break
            with conn:
                conn.executemany(
                    "UPDATE shows SET title_ptbr = ?, updated_at = CURRENT_TIMESTAMP WHERE imdb_id = ?;",
                    update_batch[i : i + 20000],
                )
        print(f"  [+] {len(br_titles):,} títulos nacionais (BR) gravados em 'title_ptbr'.")
    else:
        print("  [*] Nenhum novo título nacional (BR) encontrado nesta revisão.")

    if not STOP_REQUESTED:
        set_sync_state(conn, "last_akas_import_sig", akas_sig)


def sync_level1_datasets(
    conn: sqlite3.Connection,
    min_votes: int = 50,
    since_year: int = 0,
    allowed_types: tuple[str, ...] = DEFAULT_TITLE_TYPES,
    include_akas_br: bool = True,
    include_episodes: bool = False,
    force_download: bool = False,
):
    print(
        f"[*] [1º Nível] Verificando revisão dos datasets IMDb | "
        f"Tipos: {', '.join(allowed_types)} | Mín. votos: {min_votes}"
    )

    ratings_path, ratings_rev = download_dataset_if_needed("ratings", FILES["ratings"], force=force_download)
    basics_path, basics_rev = download_dataset_if_needed("basics", FILES["basics"], force=force_download)

    basics_sig = compute_import_signature(
        "basics", basics_rev, ratings_rev, min_votes, since_year, ",".join(sorted(allowed_types))
    )
    saved_basics_sig = get_sync_state(conn, "last_basics_import_sig")
    shows_count = conn.execute("SELECT COUNT(*) FROM shows;").fetchone()[0]

    ratings_map: dict[str, tuple[float, int]] | None = None

    def load_ratings_map() -> dict[str, tuple[float, int]]:
        nonlocal ratings_map
        if ratings_map is not None:
            return ratings_map
        print("  [*] Lendo mapa de avaliações (title.ratings)...")
        rmap: dict[str, tuple[float, int]] = {}
        with gzip.open(ratings_path, "rt", encoding="utf-8") as f:
            next(f, None)
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3:
                    votes = int(parts[2])
                    if votes >= min_votes:
                        rmap[parts[0]] = (float(parts[1]), votes)
        ratings_map = rmap
        return rmap

    # 1. Parsing do title.basics (pulado automaticamente se a revisão já foi importada no SQLite)
    if not force_download and shows_count > 0 and saved_basics_sig == basics_sig:
        print(
            f"  [*] Catálogo base ({shows_count:,} títulos) já está sincronizado com esta exata revisão do IMDb. "
            f"Pulando leitura de title.basics."
        )
    else:
        existing_shows: dict[str, tuple[float | None, int, int | None]] = {}
        for tid, score, votes, end_yr in conn.execute(
            "SELECT imdb_id, rating_score, rating_votes, end_year FROM shows;"
        ):
            existing_shows[tid] = (score, votes or 0, end_yr)

        rmap = load_ratings_map()
        print("  [*] Aplicando delta em streaming sobre title.basics...")

        valid_types = set(allowed_types)
        insert_batch = []
        update_batch = []
        total_inserted = 0
        total_updated = 0

        insert_sql = """
            INSERT OR IGNORE INTO shows (
                imdb_id, imdb_num, title_type, primary_title, original_title,
                is_adult, start_year, end_year, runtime_minutes, genres,
                rating_score, rating_votes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """
        update_sql = """
            UPDATE shows SET end_year = ?, rating_score = ?, rating_votes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE imdb_id = ?;
        """

        with gzip.open(basics_path, "rt", encoding="utf-8") as f:
            next(f, None)
            for line in f:
                if STOP_REQUESTED:
                    break
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 9 or parts[1] not in valid_types:
                    continue

                start_yr = parse_int(parts[5])
                if since_year > 0 and (not start_yr or start_yr < since_year):
                    continue

                tconst = parts[0]
                rating_info = rmap.get(tconst)
                if min_votes > 0 and not rating_info:
                    continue

                score = rating_info[0] if rating_info else None
                votes = rating_info[1] if rating_info else 0
                end_yr = parse_int(parts[6])

                prev = existing_shows.get(tconst)
                if prev is None:
                    imdb_num = int(tconst[2:]) if tconst[2:].isdigit() else None
                    insert_batch.append((
                        tconst, imdb_num, parts[1], parts[2],
                        parts[3] if parts[3] != r"\N" else None,
                        parse_int(parts[4]) or 0, start_yr, end_yr,
                        parse_int(parts[7]), parts[8] if parts[8] != r"\N" else None,
                        score, votes,
                    ))
                    if len(insert_batch) >= 15000:
                        with conn:
                            conn.executemany(insert_sql, insert_batch)
                        total_inserted += len(insert_batch)
                        insert_batch.clear()
                        print(f"\r      Inseridos: {total_inserted:,} | Atualizados: {total_updated:,}...", end="", flush=True)
                else:
                    if prev[1] != votes or prev[0] != score or prev[2] != end_yr:
                        update_batch.append((end_yr, score, votes, tconst))
                        if len(update_batch) >= 15000:
                            with conn:
                                conn.executemany(update_sql, update_batch)
                            total_updated += len(update_batch)
                            update_batch.clear()
                            print(f"\r      Inseridos: {total_inserted:,} | Atualizados: {total_updated:,}...", end="", flush=True)

        if insert_batch:
            with conn:
                conn.executemany(insert_sql, insert_batch)
            total_inserted += len(insert_batch)
        if update_batch:
            with conn:
                conn.executemany(update_sql, update_batch)
            total_updated += len(update_batch)

        print(f"\n  [+] [title.basics] Novos: {total_inserted:,} | Notas atualizadas: {total_updated:,}")
        if not STOP_REQUESTED:
            set_sync_state(conn, "last_basics_import_sig", basics_sig)

    # 2. AKAs BR (pulado automaticamente se já importado nesta revisão)
    if include_akas_br and not STOP_REQUESTED:
        sync_br_akas_streaming(conn, target_title_ids=None, since_year=since_year, force_download=force_download)

    # 3. Árvore de Episódios (pulado automaticamente se esta revisão já foi importada)
    if include_episodes and not STOP_REQUESTED:
        ep_path, ep_rev = download_dataset_if_needed("episodes", FILES["episodes"], force=force_download)
        ep_sig = compute_import_signature("episodes", ep_rev, ratings_rev, min_votes, since_year)
        ep_count = conn.execute("SELECT COUNT(*) FROM episodes_catalog;").fetchone()[0]

        if not force_download and ep_count > 0 and get_sync_state(conn, "last_episodes_import_sig") == ep_sig:
            print(
                f"  [*] Árvore de episódios ({ep_count:,} registros) já sincronizada nesta revisão. "
                f"Pulando leitura de title.episode."
            )
        else:
            rmap = load_ratings_map()
            series_placeholders = ",".join("?" for _ in SERIES_TYPES)
            valid_series_ids = {
                row[0]
                for row in conn.execute(
                    f"SELECT imdb_id FROM shows WHERE title_type IN ({series_placeholders});",
                    SERIES_TYPES,
                ).fetchall()
            }
            existing_ep_ids = {
                row[0] for row in conn.execute("SELECT episode_imdb_id FROM episodes_catalog;").fetchall()
            }
            print(f"  [*] Importando episódios inéditos para {len(valid_series_ids):,} séries...")

            ep_insert_sql = """
                INSERT OR IGNORE INTO episodes_catalog (
                    episode_imdb_id, show_imdb_id, season, episode, rating_score, rating_votes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """
            ep_batch = []
            ep_inserted = 0
            with gzip.open(ep_path, "rt", encoding="utf-8") as f:
                next(f, None)
                for line in f:
                    if STOP_REQUESTED:
                        break
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 4:
                        continue
                    ep_id, parent_id, s_num, e_num = parts[0], parts[1], parts[2], parts[3]
                    if ep_id in existing_ep_ids or parent_id not in valid_series_ids:
                        continue
                    r_info = rmap.get(ep_id)
                    ep_batch.append((
                        ep_id, parent_id, parse_int(s_num), parse_int(e_num),
                        r_info[0] if r_info else None, r_info[1] if r_info else 0
                    ))
                    if len(ep_batch) >= 20000:
                        with conn:
                            conn.executemany(ep_insert_sql, ep_batch)
                        ep_inserted += len(ep_batch)
                        ep_batch.clear()
                        print(f"\r      Novos episódios: {ep_inserted:,}...", end="", flush=True)
            if ep_batch:
                with conn:
                    conn.executemany(ep_insert_sql, ep_batch)
                ep_inserted += len(ep_batch)
            print(f"\n  [+] {ep_inserted:,} novos episódios vinculados.")
            if not STOP_REQUESTED:
                set_sync_state(conn, "last_episodes_import_sig", ep_sig)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not get_sync_state(conn, "last_tmdb_changes_date"):
        set_sync_state(conn, "last_tmdb_changes_date", today_str)


# =====================================================================
# 3. CLIENTE TMDB E PARSERS DE METADADOS
# =====================================================================
def get_tmdb_session(read_token: str | None, api_key: str | None) -> std_requests.Session:
    if not hasattr(THREAD_LOCAL, "tmdb_session"):
        sess = std_requests.Session()
        headers = {"Accept": "application/json", "User-Agent": "IMDbMetadataCatalog/4.1"}
        base_params = {}
        if read_token:
            headers["Authorization"] = f"Bearer {read_token.removeprefix('Bearer ').strip()}"
        elif api_key:
            base_params["api_key"] = api_key

        sess.headers.update(headers)
        THREAD_LOCAL.tmdb_base_params = base_params
        THREAD_LOCAL.tmdb_session = sess
    return THREAD_LOCAL.tmdb_session


def select_best_youtube_trailer(videos_node: dict | None) -> str | None:
    results = (videos_node or {}).get("results") or []
    yt_videos = [v for v in results if (v.get("site") or "").lower() == "youtube" and v.get("key")]
    if not yt_videos:
        return None

    def video_rank(v: dict) -> tuple[int, int, int]:
        v_type = (v.get("type") or "").lower()
        lang = (v.get("iso_639_1") or "").lower()
        country = (v.get("iso_3166_1") or "").upper()
        official = 1 if v.get("official") else 0
        type_score = 3 if v_type == "trailer" else (2 if v_type == "teaser" else 1)
        lang_score = 3 if (lang == "pt" and country == "BR") else (2 if lang == "pt" else (1 if lang == "en" else 0))
        return (type_score, lang_score, official)

    best = max(yt_videos, key=video_rank)
    return f"https://www.youtube.com/watch?v={best['key']}"


def extract_tmdb_certification(full_data: dict, media_type: str) -> str | None:
    if media_type == "movie":
        results = ((full_data.get("release_dates") or {}).get("results") or [])
        cert_map = {}
        for country_entry in results:
            iso = country_entry.get("iso_3166_1")
            for rel in (country_entry.get("release_dates") or []):
                c = (rel.get("certification") or "").strip()
                if c:
                    cert_map[iso] = c
                    break
        return cert_map.get("BR") or cert_map.get("US")
    else:
        results = ((full_data.get("content_ratings") or {}).get("results") or [])
        cert_map = {
            r.get("iso_3166_1"): (r.get("rating") or "").strip()
            for r in results
            if (r.get("rating") or "").strip()
        }
        return cert_map.get("BR") or cert_map.get("US")


def parse_tmdb_enriched_payload(full_data: dict, media_type: str) -> dict:
    loc_title = (full_data.get("title") or full_data.get("name") or "").strip() or None
    orig_title = (full_data.get("original_title") or full_data.get("original_name") or "").strip() or None
    title_ptbr = loc_title if (loc_title and loc_title != orig_title) else loc_title

    overview = (full_data.get("overview") or "").strip() or None
    tagline = (full_data.get("tagline") or "").strip() or None

    poster_path = full_data.get("poster_path")
    backdrop_path = full_data.get("backdrop_path")
    genres_list = [g.get("name") for g in (full_data.get("genres") or []) if g.get("name")]
    canonical_genres = merge_canonical_genres(", ".join(genres_list)) if genres_list else []
    genres_ptbr = ", ".join(canonical_genres) if canonical_genres else None

    credits_node = full_data.get("aggregate_credits") or full_data.get("credits") or {}
    cast_names = [c.get("name") for c in (credits_node.get("cast") or [])[:15] if c.get("name")]
    cast_members = ", ".join(cast_names) if cast_names else None

    crew_raw = credits_node.get("crew") or []
    directors_list = []
    for member in crew_raw:
        job = (member.get("job") or "").lower()
        jobs_nested = [j.get("job", "").lower() for j in (member.get("jobs") or [])]
        if job == "director" or "director" in jobs_nested:
            if member.get("name") and member["name"] not in directors_list:
                directors_list.append(member["name"])
    directors = ", ".join(directors_list[:8]) if directors_list else None

    creators_list = [c.get("name") for c in (full_data.get("created_by") or []) if c.get("name")]
    if not creators_list and media_type == "movie":
        for member in crew_raw:
            if (member.get("job") or "").lower() in ("screenplay", "writer", "story"):
                if member.get("name") and member["name"] not in creators_list:
                    creators_list.append(member["name"])
    creators = ", ".join(creators_list[:8]) if creators_list else None

    countries = ", ".join(
        c.get("name") or c.get("iso_3166_1")
        for c in (full_data.get("production_countries") or [])
        if c.get("name") or c.get("iso_3166_1")
    ) or None

    languages = ", ".join(
        l.get("name") or l.get("english_name")
        for l in (full_data.get("spoken_languages") or [])
        if l.get("name") or l.get("english_name")
    ) or None

    network = ", ".join(
        n.get("name") for n in (full_data.get("networks") or [])[:4] if n.get("name")
    ) or None

    release_date = full_data.get("release_date") or full_data.get("first_air_date") or None
    start_year = int(release_date[:4]) if (release_date and len(release_date) >= 4 and release_date[:4].isdigit()) else None
    total_seasons = full_data.get("number_of_seasons") if media_type == "tv" else None

    ext_ids = full_data.get("external_ids") or {}
    imdb_id = (ext_ids.get("imdb_id") or "").strip() or None

    return {
        "imdb_id": imdb_id,
        "tmdb_id": full_data.get("id"),
        "title_type": "movie" if media_type == "movie" else "tvSeries",
        "primary_title": orig_title or loc_title or "Unknown",
        "original_title": orig_title,
        "title_ptbr": title_ptbr,
        "synopsis_ptbr": overview,
        "tagline": tagline,
        "genres_ptbr": genres_ptbr,
        "poster_url": f"{TMDB_IMG_BASE}{poster_path}" if poster_path else None,
        "backdrop_url": f"{TMDB_IMG_BASE}{backdrop_path}" if backdrop_path else None,
        "trailer_url": select_best_youtube_trailer(full_data.get("videos")),
        "cast_members": cast_members,
        "directors": directors,
        "creators": creators,
        "content_rating": extract_tmdb_certification(full_data, media_type),
        "release_date": release_date,
        "start_year": start_year,
        "runtime_minutes": full_data.get("runtime") or (
            (full_data.get("episode_run_time") or [None])[0] if media_type == "tv" else None
        ),
        "rating_score": full_data.get("vote_average"),
        "rating_votes": full_data.get("vote_count") or 0,
        "countries": countries,
        "languages": languages,
        "network": network,
        "streaming_providers": ", ".join(extract_tmdb_watch_providers(full_data)) or None,
        "total_seasons": total_seasons,
        "sync_flag": 1 if overview else 2,
    }


# =====================================================================
# 4. CAMADA RESUMÍVEL DE HIDRATAÇÃO (FILA LOCAL -> TMDB)
# =====================================================================
def fetch_tmdb_by_imdb_task(
    imdb_id: str,
    primary_title: str,
    read_token: str | None,
    api_key: str | None,
    delay: float,
) -> dict:
    if STOP_REQUESTED:
        return {"status": "aborted", "imdb_id": imdb_id}

    session = get_tmdb_session(read_token, api_key)
    base_params = THREAD_LOCAL.tmdb_base_params

    for attempt in range(1, 4):
        if STOP_REQUESTED:
            return {"status": "aborted", "imdb_id": imdb_id}
        try:
            find_url = f"{TMDB_API_BASE}/find/{imdb_id}"
            resp = session.get(
                find_url,
                params={**base_params, "external_source": "imdb_id", "language": "pt-BR"},
                timeout=20,
            )
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", 3)))
                continue
            if resp.status_code == 401:
                return {"status": "auth_error", "imdb_id": imdb_id, "error": "HTTP 401 Unauthorized no TMDB"}
            resp.raise_for_status()

            find_data = resp.json()
            if find_data.get("movie_results"):
                media_type = "movie"
                tmdb_id = find_data["movie_results"][0]["id"]
                append_fields = "credits,videos,release_dates,watch/providers"
            elif find_data.get("tv_results"):
                media_type = "tv"
                tmdb_id = find_data["tv_results"][0]["id"]
                append_fields = "aggregate_credits,videos,content_ratings,watch/providers"
            else:
                return {"status": "not_found", "imdb_id": imdb_id, "title": primary_title}

            detail_url = f"{TMDB_API_BASE}/{media_type}/{tmdb_id}"
            det_resp = session.get(
                detail_url,
                params={
                    **base_params,
                    "language": "pt-BR",
                    "append_to_response": append_fields,
                    "include_video_language": "pt-BR,pt,en,null",
                },
                timeout=20,
            )
            if det_resp.status_code == 429:
                time.sleep(int(det_resp.headers.get("Retry-After", 3)))
                continue
            det_resp.raise_for_status()

            enriched = parse_tmdb_enriched_payload(det_resp.json(), media_type)
            enriched["imdb_id"] = imdb_id

            if delay > 0 and not STOP_REQUESTED:
                time.sleep(delay)

            return {"status": "ok", "imdb_id": imdb_id, "title": primary_title, **enriched}
        except Exception as e:
            if attempt == 3:
                return {"status": "error", "imdb_id": imdb_id, "title": primary_title, "error": str(e)}
            time.sleep(attempt * 1.5)

    return {"status": "error", "imdb_id": imdb_id, "title": primary_title, "error": "Max retries"}


def commit_tmdb_result(conn: sqlite3.Connection, res: dict):
    imdb_id = res["imdb_id"]
    status = res["status"]

    with conn:
        if status == "not_found":
            conn.execute(
                "UPDATE shows SET tmdb_synced = -1, updated_at = CURRENT_TIMESTAMP WHERE imdb_id = ?;",
                (imdb_id,),
            )
            return
        if status != "ok":
            return

        conn.execute(
            """
            UPDATE shows SET
                tmdb_id = COALESCE(:tmdb_id, tmdb_id),
                title_ptbr = COALESCE(title_ptbr, :title_ptbr),
                synopsis_ptbr = COALESCE(:synopsis_ptbr, synopsis_ptbr),
                synopsis = COALESCE(:synopsis_ptbr, synopsis),
                tagline = COALESCE(:tagline, tagline),
                genres_ptbr = COALESCE(:genres_ptbr, genres_ptbr),
                poster_url = COALESCE(poster_url, :poster_url),
                backdrop_url = COALESCE(:backdrop_url, backdrop_url),
                trailer_url = COALESCE(:trailer_url, trailer_url),
                cast_members = COALESCE(cast_members, :cast_members),
                directors = COALESCE(directors, :directors),
                creators = COALESCE(creators, :creators),
                content_rating = COALESCE(content_rating, :content_rating),
                release_date = COALESCE(release_date, :release_date),
                countries = COALESCE(countries, :countries),
                languages = COALESCE(languages, :languages),
                network = COALESCE(:network, network),
                streaming_providers = COALESCE(:streaming_providers, streaming_providers),
                total_seasons = COALESCE(total_seasons, :total_seasons),
                details_fetched = 1,
                tmdb_synced = :sync_flag,
                updated_at = CURRENT_TIMESTAMP
            WHERE imdb_id = :imdb_id;
            """,
            res,
        )


def run_resumable_tmdb_queue(
    conn: sqlite3.Connection,
    read_token: str | None,
    api_key: str | None,
    workers: int = 10,
    order: str = "newest",
    category: str = "all",
    limit: int | None = None,
    min_votes: int = 50,
    since_year: int = 0,
    delay: float = 0.15,
):
    if order == "newest":
        order_clause = "COALESCE(start_year, 0) DESC, imdb_num DESC"
    elif order == "oldest":
        order_clause = "COALESCE(start_year, 9999) ASC, imdb_num ASC"
    else:
        order_clause = "rating_votes DESC, rating_score DESC"

    where_parts = ["COALESCE(tmdb_synced, 0) = 0"]
    params = []

    if category == "movies":
        where_parts.append("title_type IN ('movie', 'tvMovie')")
    elif category == "series":
        where_parts.append("title_type IN ('tvSeries', 'tvMiniSeries')")

    if min_votes > 0:
        where_parts.append("rating_votes >= ?")
        params.append(min_votes)

    if since_year > 0:
        where_parts.append("start_year >= ?")
        params.append(since_year)

    where_sql = " AND ".join(where_parts)

    total_scope, done_scope, pending_scope = conn.execute(
        f"""
        SELECT
            COUNT(*),
            SUM(CASE WHEN tmdb_synced != 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN COALESCE(tmdb_synced, 0) = 0 THEN 1 ELSE 0 END)
        FROM shows
        WHERE {" AND ".join(where_parts[1:]) if len(where_parts) > 1 else "1=1"}
        """,
        params,
    ).fetchone()

    query = f"SELECT imdb_id, primary_title FROM shows WHERE {where_sql} ORDER BY {order_clause}"
    if limit and limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    targets = conn.execute(query, params).fetchall()
    total_batch = len(targets)

    if total_batch == 0:
        print("[*] Fila de hidratação 100% concluída! Nenhum título pendente para os filtros informados.")
        return

    pct_before = ((done_scope or 0) / total_scope * 100) if total_scope else 0.0
    print(
        f"\n[*] [Hidratação Resumível] Progresso Global: {done_scope or 0:,}/{total_scope:,} ({pct_before:.1f}%) | "
        f"Pendentes totais: {pending_scope or 0:,} | Lote atual: {total_batch:,} | "
        f"Workers: {workers} | Ordem: {order.upper()}"
    )
    print("    (Pressione Ctrl+C a qualquer momento para pausar; rode com --resume para continuar de onde parou)\n")

    start_time = time.time()
    completed = 0
    recovered_ptbr = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        target_iter = iter(targets)
        active = {}

        for _ in range(min(total_batch, workers * 2)):
            item = next(target_iter, None)
            if item:
                fut = executor.submit(fetch_tmdb_by_imdb_task, item[0], item[1], read_token, api_key, delay)
                active[fut] = item

        while active:
            for fut in as_completed(list(active.keys())):
                active.pop(fut)
                res = fut.result()

                if res["status"] == "aborted":
                    continue
                if res["status"] == "auth_error":
                    print(f"\n[!] {res['error']}. Verifique o .env.", file=sys.stderr)
                    return

                commit_tmdb_result(conn, res)
                completed += 1
                if res.get("sync_flag") == 1:
                    recovered_ptbr += 1

                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                rem = total_batch - completed
                eta = str(timedelta(seconds=int(rem / rate))) if rate > 0 else "--:--:--"

                global_done_now = (done_scope or 0) + completed
                global_pct = (global_done_now / total_scope * 100) if total_scope else 100.0

                if res["status"] == "ok":
                    badge = "PT-BR" if res["sync_flag"] == 1 else "Sem Plot BR"
                    yt_badge = "Trailer" if res.get("trailer_url") else "Sem YT"
                    print(
                        f"  [{completed}/{total_batch} | Global: {global_pct:.1f}% | {rate:.1f} t/s | ETA: {eta}] "
                        f"{res['imdb_id']} '{res['title']}' -> TMDB={res['tmdb_id']} [{badge} | {yt_badge}]"
                    )
                elif res["status"] == "not_found":
                    print(f"  [{completed}/{total_batch} | Global: {global_pct:.1f}%] {res['imdb_id']} '{res['title']}' -> [Sem registro no TMDB]")
                else:
                    print(f"  [{completed}/{total_batch}] {res['imdb_id']} '{res['title']}' -> [Erro: {res.get('error')}]")

                if not STOP_REQUESTED:
                    nxt = next(target_iter, None)
                    if nxt:
                        nfut = executor.submit(fetch_tmdb_by_imdb_task, nxt[0], nxt[1], read_token, api_key, delay)
                        active[nfut] = nxt
                break

    set_sync_state(conn, "last_resume_checkpoint", datetime.now(timezone.utc).isoformat())
    print(
        f"\n[+] Checkpoint salvo! Lote processado: {completed:,} ({recovered_ptbr:,} com sinopse PT-BR). "
        f"Restantes na fila global: {max((pending_scope or 0) - completed, 0):,}."
    )


# =====================================================================
# 5. DELTA UPDATE REAL VIA API /CHANGES DO TMDB (ZERO DOWNLOAD DE .GZ)
# =====================================================================
def fetch_tmdb_changed_ids(
    session: std_requests.Session,
    base_params: dict,
    media_type: str,
    start_date: str,
    end_date: str,
) -> list[int]:
    changed_ids = []
    page = 1

    while not STOP_REQUESTED:
        url = f"{TMDB_API_BASE}/{media_type}/changes"
        params = {
            **base_params,
            "start_date": start_date,
            "end_date": end_date,
            "page": page,
        }
        resp = session.get(url, params=params, timeout=20)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 3)))
            continue
        resp.raise_for_status()

        payload = resp.json()
        for item in payload.get("results") or []:
            if not item.get("adult") and item.get("id"):
                changed_ids.append(int(item["id"]))

        total_pages = payload.get("total_pages") or 1
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.1)

    return list(dict.fromkeys(changed_ids))


def fetch_tmdb_by_native_id_task(
    tmdb_id: int,
    media_type: str,
    min_votes: int,
    since_year: int,
    read_token: str | None,
    api_key: str | None,
) -> dict:
    if STOP_REQUESTED:
        return {"status": "aborted"}

    session = get_tmdb_session(read_token, api_key)
    base_params = THREAD_LOCAL.tmdb_base_params
    append_fields = (
        "external_ids,credits,videos,release_dates,watch/providers"
        if media_type == "movie"
        else "external_ids,aggregate_credits,videos,content_ratings,watch/providers"
    )

    for attempt in range(1, 4):
        try:
            url = f"{TMDB_API_BASE}/{media_type}/{tmdb_id}"
            resp = session.get(
                url,
                params={
                    **base_params,
                    "language": "pt-BR",
                    "append_to_response": append_fields,
                    "include_video_language": "pt-BR,pt,en,null",
                },
                timeout=20,
            )
            if resp.status_code == 404:
                return {"status": "skip"}
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", 3)))
                continue
            resp.raise_for_status()

            data = resp.json()
            parsed = parse_tmdb_enriched_payload(data, media_type)

            imdb_id = parsed.get("imdb_id")
            if not imdb_id or not imdb_id.startswith("tt"):
                return {"status": "skip"}
            if min_votes > 0 and (parsed.get("rating_votes") or 0) < min_votes:
                return {"status": "skip"}
            if since_year > 0 and (not parsed.get("start_year") or parsed["start_year"] < since_year):
                return {"status": "skip"}

            parsed["imdb_num"] = int(imdb_id[2:]) if imdb_id[2:].isdigit() else None
            return {"status": "ok", **parsed}
        except Exception:
            if attempt == 3:
                return {"status": "skip"}
            time.sleep(attempt)

    return {"status": "skip"}


def run_lightweight_delta_update(
    conn: sqlite3.Connection,
    read_token: str | None,
    api_key: str | None,
    workers: int = 10,
    min_votes: int = 50,
    since_year: int = 0,
    days_back: int = 3,
):
    session = get_tmdb_session(read_token, api_key)
    base_params = THREAD_LOCAL.tmdb_base_params

    today_utc = datetime.now(timezone.utc)
    end_date = today_utc.strftime("%Y-%m-%d")

    last_date = get_sync_state(conn, "last_tmdb_changes_date")
    if not last_date:
        last_date = (today_utc - timedelta(days=days_back)).strftime("%Y-%m-%d")

    start_dt = datetime.strptime(last_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if (today_utc - start_dt).days > 14:
        start_dt = today_utc - timedelta(days=14)
    start_date = start_dt.strftime("%Y-%m-%d")

    print(f"[*] [Delta Update Leve] Buscando novidades e alterações no TMDB de {start_date} até {end_date} (sem baixar .gz)...")

    movie_ids = fetch_tmdb_changed_ids(session, base_params, "movie", start_date, end_date)
    tv_ids = fetch_tmdb_changed_ids(session, base_params, "tv", start_date, end_date)

    tasks = [("movie", mid) for mid in movie_ids] + [("tv", tid) for tid in tv_ids]
    print(f"    -> {len(movie_ids):,} filmes e {len(tv_ids):,} séries modificados/adicionados no período ({len(tasks):,} alvos).")

    if not tasks:
        set_sync_state(conn, "last_tmdb_changes_date", end_date)
        print("[+] Catálogo já está 100% atualizado.")
        return

    existing_imdb_ids = {row[0] for row in conn.execute("SELECT imdb_id FROM shows;").fetchall()}
    inserted_new = 0
    updated_existing = 0
    processed = 0

    upsert_sql = """
        INSERT INTO shows (
            imdb_id, imdb_num, tmdb_id, title_type, primary_title, original_title,
            title_ptbr, tagline, start_year, runtime_minutes, genres_ptbr,
            rating_score, rating_votes, poster_url, backdrop_url, trailer_url,
            synopsis, synopsis_ptbr, content_rating, release_date,
            countries, languages, network, streaming_providers, directors, creators, cast_members,
            total_seasons, details_fetched, tmdb_synced, updated_at
        ) VALUES (
            :imdb_id, :imdb_num, :tmdb_id, :title_type, :primary_title, :original_title,
            :title_ptbr, :tagline, :start_year, :runtime_minutes, :genres_ptbr,
            :rating_score, :rating_votes, :poster_url, :backdrop_url, :trailer_url,
            :synopsis_ptbr, :synopsis_ptbr, :content_rating, :release_date,
            :countries, :languages, :network, :streaming_providers, :directors, :creators, :cast_members,
            :total_seasons, 1, :sync_flag, CURRENT_TIMESTAMP
        )
        ON CONFLICT(imdb_id) DO UPDATE SET
            tmdb_id = COALESCE(excluded.tmdb_id, shows.tmdb_id),
            title_ptbr = COALESCE(excluded.title_ptbr, shows.title_ptbr),
            tagline = COALESCE(excluded.tagline, shows.tagline),
            genres_ptbr = COALESCE(excluded.genres_ptbr, shows.genres_ptbr),
            rating_score = COALESCE(excluded.rating_score, shows.rating_score),
            rating_votes = MAX(COALESCE(shows.rating_votes, 0), COALESCE(excluded.rating_votes, 0)),
            poster_url = COALESCE(excluded.poster_url, shows.poster_url),
            backdrop_url = COALESCE(excluded.backdrop_url, shows.backdrop_url),
            trailer_url = COALESCE(excluded.trailer_url, shows.trailer_url),
            synopsis_ptbr = COALESCE(excluded.synopsis_ptbr, shows.synopsis_ptbr),
            synopsis = COALESCE(excluded.synopsis_ptbr, shows.synopsis),
            content_rating = COALESCE(excluded.content_rating, shows.content_rating),
            network = COALESCE(excluded.network, shows.network),
            streaming_providers = COALESCE(excluded.streaming_providers, shows.streaming_providers),
            directors = COALESCE(excluded.directors, shows.directors),
            creators = COALESCE(excluded.creators, shows.creators),
            cast_members = COALESCE(excluded.cast_members, shows.cast_members),
            total_seasons = COALESCE(excluded.total_seasons, shows.total_seasons),
            details_fetched = 1,
            tmdb_synced = CASE WHEN excluded.tmdb_synced = 1 THEN 1 ELSE shows.tmdb_synced END,
            updated_at = CURRENT_TIMESTAMP;
    """

    with ThreadPoolExecutor(max_workers=workers) as executor:
        task_iter = iter(tasks)
        active = {}

        for _ in range(min(len(tasks), workers * 2)):
            m_type, tid = next(task_iter)
            fut = executor.submit(
                fetch_tmdb_by_native_id_task, tid, m_type, min_votes, since_year, read_token, api_key
            )
            active[fut] = (m_type, tid)

        while active:
            for fut in as_completed(list(active.keys())):
                active.pop(fut)
                res = fut.result()
                processed += 1

                if res["status"] == "ok":
                    imdb_id = res["imdb_id"]
                    is_new = imdb_id not in existing_imdb_ids
                    with conn:
                        conn.execute(upsert_sql, res)
                    if is_new:
                        existing_imdb_ids.add(imdb_id)
                        inserted_new += 1
                        print(
                            f"  [+NOVO] {imdb_id} | {res['title_ptbr'] or res['primary_title']} "
                            f"({res['start_year'] or 'N/A'}) - {res['rating_votes']} votos"
                        )
                    else:
                        updated_existing += 1

                if processed % 250 == 0:
                    print(
                        f"\r    Avaliados: {processed:,}/{len(tasks):,} | "
                        f"Novos inseridos: +{inserted_new:,} | Atualizados: {updated_existing:,}...",
                        end="",
                        flush=True,
                    )

                if not STOP_REQUESTED:
                    nxt = next(task_iter, None)
                    if nxt:
                        nfut = executor.submit(
                            fetch_tmdb_by_native_id_task, nxt[1], nxt[0], min_votes, since_year, read_token, api_key
                        )
                        active[nfut] = nxt
                break

    if not STOP_REQUESTED:
        set_sync_state(conn, "last_tmdb_changes_date", end_date)

    print(
        f"\n[+] Delta Update concluído! Novos títulos adicionados: +{inserted_new:,} | "
        f"Existentes atualizados: {updated_existing:,} | Cursor salvo em: {end_date}"
    )


# =====================================================================
# 6. DIAGNÓSTICO DO BANCO (--stats)
# =====================================================================
def print_stats(conn: sqlite3.Connection):
    ov = conn.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN title_type IN ('movie', 'tvMovie') THEN 1 ELSE 0 END),
            SUM(CASE WHEN title_type IN ('tvSeries', 'tvMiniSeries') THEN 1 ELSE 0 END),
            SUM(CASE WHEN title_ptbr IS NOT NULL AND title_ptbr != '' THEN 1 ELSE 0 END),
            SUM(CASE WHEN tmdb_synced != 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN COALESCE(tmdb_synced, 0) = 0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN synopsis_ptbr IS NOT NULL AND synopsis_ptbr != '' THEN 1 ELSE 0 END),
            SUM(CASE WHEN trailer_url IS NOT NULL AND trailer_url != '' THEN 1 ELSE 0 END),
            SUM(CASE WHEN backdrop_url IS NOT NULL AND backdrop_url != '' THEN 1 ELSE 0 END)
        FROM shows;
        """
    ).fetchone()
    ep_count = conn.execute("SELECT COUNT(*) FROM episodes_catalog;").fetchone()[0]
    last_delta = get_sync_state(conn, "last_tmdb_changes_date", "Nunca executado")

    total = ov[0] or 0
    done_l2 = ov[4] or 0
    pending_l2 = ov[5] or 0
    pct_done = (done_l2 / total * 100) if total else 0.0

    read_token, api_key = resolve_tmdb_credentials()
    cred_status = (
        "Bearer Token + API Key (.env)" if (read_token and api_key)
        else ("Bearer Token (.env)" if read_token else ("API Key (.env)" if api_key else "NÃO ENCONTRADAS"))
    )

    print("\n" + "=" * 78)
    print(" DIAGNÓSTICO DO CATÁLOGO IMDb + TMDB (SQLITE INCREMENTAL)")
    print("=" * 78)
    print(f" Credenciais (.env)                  : {cred_status}")
    print(f" Último Delta Update (--update)      : {last_delta}")
    print(f" Total de Títulos no Banco (1º Nível): {total:,}")
    print(f"   ├─ Filmes (movie / tvMovie)       : {ov[1] or 0:,}")
    print(f"   └─ Séries (tvSeries / Mini)       : {ov[2] or 0:,}")
    print(f" Hidratação Completa (2º/3º Nível)   : {done_l2:,} ({pct_done:.1f}%)")
    print(f"   └─ Fila Pendente (--resume)       : {pending_l2:,} títulos aguardando")
    print(f" Cobertura em Português & Mídia:")
    print(f"   ├─ Títulos Nacionais (title_ptbr) : {ov[3] or 0:,}")
    print(f"   ├─ Sinopses PT-BR (synopsis_ptbr) : {ov[6] or 0:,}")
    print(f"   ├─ Backdrops 16:9 (backdrop_url)  : {ov[8] or 0:,}")
    print(f"   └─ Trailers YouTube (trailer_url) : {ov[7] or 0:,}")
    print(f" Total de Episódios Vinculados       : {ep_count or 0:,}")
    print("=" * 78 + "\n")


# =====================================================================
# 7. CLI PRINCIPAL
# =====================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Catálogo Incremental e Resumível IMDb + TMDB em SQLite"
    )
    parser.add_argument("--db", default=DB_FILE, help="Arquivo SQLite (padrão: imdb_catalog.db)")
    parser.add_argument("--stats", action="store_true", help="Exibe progresso da fila, cobertura e estado do banco")

    # 1. Atualização Diária/Semanal Ultra-Leve (SEM baixar .tsv.gz de 600MB)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Atualização incremental leve via API /changes do TMDB (zero download de .gz; traz apenas novidades recentes)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=3,
        help="Janela de dias caso seja o primeiro --update sem cursor salvo (padrão: 3 dias, máx: 14)",
    )

    # 2. Hidratação Resumível da Fila Local (para continuar os 250k+ títulos em lotes)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retoma a hidratação completa (TMDB) exatamente de onde parou na fila pendente (tmdb_synced = 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limita o lote do --resume a N títulos por execução (ex: --resume --limit 5000)",
    )

    # 3. Bootstrap / Manutenção dos Dumps Oficiais (.tsv.gz) com validação HTTP HEAD ETag
    parser.add_argument(
        "--bootstrap",
        "--sync-datasets",
        dest="bootstrap",
        action="store_true",
        help="Sincroniza os dumps .tsv.gz do IMDb (valida ETag via HTTP HEAD; só baixa e re-importa se houver revisão nova)",
    )
    parser.add_argument("--include-episodes", action="store_true", help="Importa episódios inéditos no --bootstrap")
    parser.add_argument("--force-download", action="store_true", help="Ignora o cache ETag e força novo download e re-leitura dos .tsv.gz")

    # Filtros Gerais
    parser.add_argument("--min-votes", type=int, default=50, help="Filtro mínimo de votos (padrão: 50; 0 = tudo)")
    parser.add_argument("--since-year", type=int, default=0, help="Filtra apenas títulos com start_year >= ANO")
    parser.add_argument("--category", choices=["all", "movies", "series"], default="all", help="Filtra filmes ou séries")
    parser.add_argument("--order", choices=["newest", "oldest", "votes"], default="newest", help="Ordem da fila (padrão: newest)")
    parser.add_argument("--workers", type=int, default=10, help="Workers paralelos (padrão: 10)")
    parser.add_argument("--delay", type=float, default=0.15, help="Intervalo por worker em segundos (padrão: 0.15s)")

    args = parser.parse_args()
    conn = init_db(args.db)

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    # Fluxo 1: Bootstrap / Manutenção (.tsv.gz com validação ETag HTTP HEAD)
    if args.bootstrap:
        sync_level1_datasets(
            conn,
            min_votes=args.min_votes,
            since_year=args.since_year,
            include_episodes=args.include_episodes,
            force_download=args.force_download,
        )

    # Fluxo 2: Atualização Incremental Leve (--update) — zero download de .gz
    if args.update:
        read_token, api_key = resolve_tmdb_credentials()
        if not (read_token or api_key):
            print("[!] Credenciais TMDB não encontradas no .env.", file=sys.stderr)
            sys.exit(1)
        run_lightweight_delta_update(
            conn,
            read_token=read_token,
            api_key=api_key,
            workers=args.workers,
            min_votes=args.min_votes,
            since_year=args.since_year,
            days_back=args.days_back,
        )

    # Fluxo 3: Retomada Resumível da Fila de Hidratação (--resume)
    if args.resume:
        read_token, api_key = resolve_tmdb_credentials()
        if not (read_token or api_key):
            print("[!] Credenciais TMDB não encontradas no .env.", file=sys.stderr)
            sys.exit(1)
        run_resumable_tmdb_queue(
            conn,
            read_token=read_token,
            api_key=api_key,
            workers=args.workers,
            order=args.order,
            category=args.category,
            limit=args.limit if args.limit > 0 else None,
            min_votes=args.min_votes,
            since_year=args.since_year,
            delay=args.delay,
        )

    if not (args.bootstrap or args.update or args.resume):
        print_stats(conn)
        print("Comandos principais:")
        print(f"  1. Retomar hidratação em lotes : python3 {sys.argv[0]} --resume --limit 10000")
        print(f"  2. Atualização diária leve     : python3 {sys.argv[0]} --update")
        print(f"  3. Checar/importar dumps (.gz) : python3 {sys.argv[0]} --bootstrap --include-episodes")

    conn.close()


if __name__ == "__main__":
    main()