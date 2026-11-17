#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

IMDB_DB_DEFAULT = "data/mainstream.db"
EZTV_DB_DEFAULT = "data/sources.db"

SERIES_TYPES = ("tvSeries", "tvMiniSeries")


# =====================================================================
# 1. FUNÇÕES AUXILIARES DE NORMALIZAÇÃO (UDF PARA SQLITE)
# =====================================================================
def normalize_title_for_match(raw: str | None) -> str:
    """
    Normaliza títulos para comparação segura:
    - Remove sufixos de ano entre parênteses no final, ex: 'The Flash (2014)' -> 'the flash'
    - Remove acentos/diacríticos (NFKD)
    - Converte '&' em 'and'
    - Remove pontuação e espaços duplicados
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    # Remove ano no fim: "Show Name (2023)" ou "Show Name 2023"
    text = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_year_from_text(raw: str | None) -> int | None:
    """Extrai o primeiro ano válido (1950-2035) de strings como '2024-05-12' ou 'May 12, 2024'."""
    if not raw:
        return None
    m = re.search(r"\b(19[5-9]\d|20[0-3]\d)\b", str(raw))
    return int(m.group(1)) if m else None


# =====================================================================
# 2. PREPARAÇÃO DE SCHEMA E ÍNDICES NO IMDB_CATALOG.DB
# =====================================================================
def ensure_imdb_badge_columns(conn: sqlite3.Connection):
    existing_cols = {row[1] for row in conn.execute("PRAGMA main.table_info(shows);").fetchall()}
    migrations = {
        "has_eztv": "INTEGER DEFAULT 0",
        "eztv_id": "INTEGER",
        "eztv_slug": "TEXT",
        "eztv_match_type": "TEXT",  # 'exact_imdb' | 'title_year_fallback'
        "tvmaze_id": "INTEGER",
        "status": "TEXT",
        "air_day_time": "TEXT",
        "streaming_providers": "TEXT",
    }
    with conn:
        for col, col_type in migrations.items():
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE main.shows ADD COLUMN {col} {col_type};")

        conn.execute("CREATE INDEX IF NOT EXISTS main.idx_shows_has_eztv ON shows(has_eztv);")
        conn.execute("CREATE INDEX IF NOT EXISTS main.idx_shows_eztv_id ON shows(eztv_id);")


# =====================================================================
# 3. MOTOR DE CRUZAMENTO VIA ATTACH DATABASE
# =====================================================================
def run_eztv_cross_reference(
    imdb_db_path: str,
    eztv_db_path: str,
    reset_badges: bool = False,
    enable_fallback: bool = True,
):
    imdb_path = Path(imdb_db_path)
    eztv_path = Path(eztv_db_path)

    if not imdb_path.is_file():
        print(f"[!] Banco IMDb não encontrado: {imdb_path}", file=sys.stderr)
        sys.exit(1)
    if not eztv_path.is_file():
        print(f"[!] Banco EZTV não encontrado: {eztv_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(imdb_path), timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")

    # Registra funções Python dentro da conexão SQLite para o fallback
    conn.create_function("NORM_TITLE", 1, normalize_title_for_match)
    conn.create_function("EXTRACT_YEAR", 1, extract_year_from_text)

    ensure_imdb_badge_columns(conn)

    # Anexa o banco do EZTV como schema secundário 'eztv'
    conn.execute("ATTACH DATABASE ? AS eztv;", (str(eztv_path.resolve()),))

    if reset_badges:
        with conn:
            conn.execute(
                """
                UPDATE main.shows
                SET has_eztv = 0, eztv_id = NULL, eztv_slug = NULL, eztv_match_type = NULL
                WHERE has_eztv != 0;
                """
            )
        print("[*] Selos EZTV anteriores zerados (--reset).")

    # Diagnóstico inicial do banco EZTV anexado
    eztv_total, eztv_with_imdb = conn.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN imdb_id IS NOT NULL AND TRIM(imdb_id) != '' THEN 1 ELSE 0 END)
        FROM eztv.shows;
        """
    ).fetchone()
    print(f"[*] Banco EZTV anexado: {eztv_total:,} séries totais ({eztv_with_imdb or 0:,} com imdb_id).")

    # -----------------------------------------------------------------
    # CAMADA 1: MATCH EXATO POR IMDb ID (ttXXXXXXX)
    # -----------------------------------------------------------------
    print("[*] [Camada 1] Cruzando por IMDb ID exato (ATTACH DATABASE)...")
    with conn:
        # Tabela temporária indexada com a melhor ocorrência de cada imdb_id no EZTV
        conn.executescript(
            """
            DROP TABLE IF EXISTS temp.eztv_best_imdb;
            CREATE TEMP TABLE temp.eztv_best_imdb AS
            SELECT
                LOWER(TRIM(imdb_id)) AS norm_imdb_id,
                id AS eztv_id,
                slug AS eztv_slug,
                tvmaze_id,
                status,
                air_day_time,
                streaming_providers,
                network,
                poster_url
            FROM (
                SELECT
                    imdb_id,
                    id,
                    slug,
                    tvmaze_id,
                    status,
                    air_day_time,
                    streaming_providers,
                    network,
                    poster_url,
                    ROW_NUMBER() OVER (
                        PARTITION BY LOWER(TRIM(imdb_id))
                        ORDER BY COALESCE(rating_votes, 0) DESC, id DESC
                    ) AS rn
                FROM eztv.shows
                WHERE imdb_id IS NOT NULL AND TRIM(imdb_id) != ''
            )
            WHERE rn = 1;

            CREATE UNIQUE INDEX temp.idx_tmp_eztv_imdb ON eztv_best_imdb(norm_imdb_id);
            """
        )

        cur_exact = conn.execute(
            """
            UPDATE main.shows
            SET
                has_eztv = 1,
                eztv_id = (SELECT e.eztv_id FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id)),
                eztv_slug = (SELECT e.eztv_slug FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id)),
                eztv_match_type = 'exact_imdb',
                tvmaze_id = COALESCE(main.shows.tvmaze_id, (SELECT e.tvmaze_id FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id))),
                status = COALESCE(NULLIF(TRIM(main.shows.status), ''), (SELECT e.status FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id))),
                air_day_time = COALESCE(NULLIF(TRIM(main.shows.air_day_time), ''), (SELECT e.air_day_time FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id))),
                streaming_providers = COALESCE(NULLIF(TRIM(main.shows.streaming_providers), ''), (SELECT COALESCE(NULLIF(TRIM(e.streaming_providers), ''), e.network) FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id))),
                network = COALESCE(NULLIF(TRIM(main.shows.network), ''), (SELECT e.network FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id))),
                poster_url = COALESCE(NULLIF(TRIM(main.shows.poster_url), ''), (SELECT e.poster_url FROM temp.eztv_best_imdb e WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id))),
                updated_at = CURRENT_TIMESTAMP
            WHERE EXISTS (
                SELECT 1
                FROM temp.eztv_best_imdb e
                WHERE e.norm_imdb_id = LOWER(main.shows.imdb_id)
            );
            """
        )
        exact_updated = cur_exact.rowcount

    print(f"  [+] [Camada 1] {exact_updated:,} títulos tageados/atualizados via IMDb ID exato.")

    # -----------------------------------------------------------------
    # CAMADA 2: FALLBACK POR TÍTULO NORMALIZADO + ANO (SÉRIES SEM IMDB_ID)
    # -----------------------------------------------------------------
    fallback_updated = 0
    if enable_fallback:
        print("[*] [Camada 2] Executando fallback por Título Normalizado + Ano (apenas correspondências únicas)...")
        with conn:
            conn.executescript(
                """
                DROP TABLE IF EXISTS temp.eztv_unmatched;
                CREATE TEMP TABLE temp.eztv_unmatched AS
                SELECT
                    id AS eztv_id,
                    slug AS eztv_slug,
                    NORM_TITLE(name) AS norm_name,
                    EXTRACT_YEAR(premiered) AS ez_year
                FROM eztv.shows
                WHERE (imdb_id IS NULL OR TRIM(imdb_id) = '')
                  AND NORM_TITLE(name) != '';

                CREATE INDEX temp.idx_tmp_ez_unmatched ON eztv_unmatched(norm_name);

                -- Indexa apenas séries do IMDb ainda não tageadas para busca rápida
                DROP TABLE IF EXISTS temp.imdb_series_pool;
                CREATE TEMP TABLE temp.imdb_series_pool AS
                SELECT
                    imdb_id,
                    NORM_TITLE(primary_title) AS norm_primary,
                    NORM_TITLE(original_title) AS norm_original,
                    start_year
                FROM main.shows
                WHERE title_type IN ('tvSeries', 'tvMiniSeries')
                  AND COALESCE(has_eztv, 0) = 0;

                CREATE INDEX temp.idx_tmp_imdb_norm_p ON imdb_series_pool(norm_primary);
                CREATE INDEX temp.idx_tmp_imdb_norm_o ON imdb_series_pool(norm_original);

                -- Candidatos válidos: exige ano compatível (±1 ano) e que o match seja 1-para-1 (sem ambiguidade)
                DROP TABLE IF EXISTS temp.fallback_matches;
                CREATE TEMP TABLE temp.fallback_matches AS
                SELECT
                    i.imdb_id,
                    MIN(e.eztv_id) AS eztv_id,
                    MIN(e.eztv_slug) AS eztv_slug
                FROM temp.eztv_unmatched e
                JOIN temp.imdb_series_pool i
                  ON (i.norm_primary = e.norm_name OR i.norm_original = e.norm_name)
                WHERE e.ez_year IS NOT NULL
                  AND i.start_year IS NOT NULL
                  AND ABS(i.start_year - e.ez_year) <= 1
                GROUP BY i.imdb_id
                HAVING COUNT(DISTINCT e.eztv_id) = 1
                   AND (
                       SELECT COUNT(*)
                       FROM temp.imdb_series_pool i2
                       WHERE (i2.norm_primary = e.norm_name OR i2.norm_original = e.norm_name)
                         AND i2.start_year IS NOT NULL
                         AND ABS(i2.start_year - e.ez_year) <= 1
                   ) = 1;

                CREATE UNIQUE INDEX temp.idx_tmp_fb_imdb ON fallback_matches(imdb_id);
                """
            )

            cur_fb = conn.execute(
                """
                UPDATE main.shows
                SET
                    has_eztv = 1,
                    eztv_id = (SELECT f.eztv_id FROM temp.fallback_matches f WHERE f.imdb_id = main.shows.imdb_id),
                    eztv_slug = (SELECT f.eztv_slug FROM temp.fallback_matches f WHERE f.imdb_id = main.shows.imdb_id),
                    eztv_match_type = 'title_year_fallback',
                    updated_at = CURRENT_TIMESTAMP
                WHERE imdb_id IN (SELECT imdb_id FROM temp.fallback_matches);
                """
            )
            fallback_updated = cur_fb.rowcount

        print(f"  [+] [Camada 2] {fallback_updated:,} séries adicionais tageadas via Fallback (Título + Ano).")

    # -----------------------------------------------------------------
    # DIAGNÓSTICO FINAL DO CRUZAMENTO
    # -----------------------------------------------------------------
    stats = conn.execute(
        """
        SELECT
            SUM(CASE WHEN has_eztv = 1 THEN 1 ELSE 0 END) AS total_badged,
            SUM(CASE WHEN eztv_match_type = 'exact_imdb' THEN 1 ELSE 0 END) AS by_imdb,
            SUM(CASE WHEN eztv_match_type = 'title_year_fallback' THEN 1 ELSE 0 END) AS by_fallback,
            SUM(CASE WHEN title_type IN ('tvSeries', 'tvMiniSeries') THEN 1 ELSE 0 END) AS total_imdb_series
        FROM main.shows;
        """
    ).fetchone()

    total_badged = stats[0] or 0
    by_imdb = stats[1] or 0
    by_fb = stats[2] or 0
    total_series = stats[3] or 0
    cov_pct = (total_badged / total_series * 100) if total_series else 0.0

    print("\n" + "=" * 74)
    print(" RELATÓRIO DO SELO EZTV NO CATÁLOGO PRINCIPAL (data/mainstream.db)")
    print("=" * 74)
    print(f" Total de Títulos com Selo (has_eztv = 1) : {total_badged:,} ({cov_pct:.1f}% das séries do IMDb)")
    print(f"   ├─ Via IMDb ID Exato ('exact_imdb')    : {by_imdb:,}")
    print(f"   └─ Via Fallback ('title_year_fallback'): {by_fb:,}")
    print("-" * 74)
    print(" [Amostra: Top 10 Séries Mais Votadas com Selo EZTV Ativo]")

    sample_rows = conn.execute(
        """
        SELECT imdb_id, primary_title, title_ptbr, start_year, eztv_id, eztv_match_type, rating_votes
        FROM main.shows
        WHERE has_eztv = 1
        ORDER BY rating_votes DESC
        LIMIT 10;
        """
    ).fetchall()

    for tid, title, ptbr, yr, ez_id, m_type, votes in sample_rows:
        br = f" [BR: {ptbr}]" if ptbr and ptbr != title else ""
        print(f"   • {tid} -> EZTV#{ez_id:<6} | {title}{br} ({yr or 'N/A'}) [{m_type}]")

    print("=" * 74 + "\n")

    conn.execute("DETACH DATABASE eztv;")
    conn.close()


# =====================================================================
# 4. CLI
# =====================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Cruza imdb_catalog.db e eztv_metadata.db via ATTACH DATABASE para aplicar o selo has_eztv = 1"
    )
    parser.add_argument("--imdb-db", default=IMDB_DB_DEFAULT, help="Caminho do banco IMDb (padrão: imdb_catalog.db)")
    parser.add_argument("--eztv-db", default=EZTV_DB_DEFAULT, help="Caminho do banco EZTV (padrão: eztv_metadata.db)")
    parser.add_argument("--no-fallback", action="store_true", help="Desativa o fallback por Título + Ano e cruza apenas por imdb_id exato")
    parser.add_argument("--reset", action="store_true", help="Limpa os selos has_eztv antes de reexecutar o cruzamento")
    args = parser.parse_args()

    run_eztv_cross_reference(
        imdb_db_path=args.imdb_db,
        eztv_db_path=args.eztv_db,
        reset_badges=args.reset,
        enable_fallback=not args.no_fallback,
    )


if __name__ == "__main__":
    main()