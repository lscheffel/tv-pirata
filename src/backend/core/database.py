"""Database configuration and session management for TV Pirata."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

import src.backend.models  # noqa: F401
from src.backend.models.catalog_domain import imdb_metadata
from src.backend.models.eztv_db import eztv_metadata


@event.listens_for(Engine, "connect")
def _configure_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
    """Apply high-performance SQLite PRAGMAs on every connection (ADR-010 DEC-001)."""
    cursor_fn = getattr(dbapi_connection, "cursor", None)
    if not callable(cursor_fn):
        return
    cur = cursor_fn()
    try:
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.execute("PRAGMA cache_size=-64000")
        cur.execute("PRAGMA mmap_size=268435456")
        cur.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    finally:
        cur.close()

# Default SQLite Dual-SSOT database paths (ADR-011)
DEFAULT_MAINSTREAM_DB_PATH = Path("data/mainstream.db")
DEFAULT_DB_PATH = DEFAULT_MAINSTREAM_DB_PATH
MAINSTREAM_DATABASE_URL = os.getenv(
    "MAINSTREAM_DATABASE_URL",
    os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_MAINSTREAM_DB_PATH}"),
)
DATABASE_URL = MAINSTREAM_DATABASE_URL

DEFAULT_SOURCES_DB_PATH = Path("data/sources.db")
DEFAULT_EZTV_DB_PATH = DEFAULT_SOURCES_DB_PATH
SOURCES_DATABASE_URL = os.getenv(
    "SOURCES_DATABASE_URL",
    os.getenv("EZTV_DATABASE_URL", f"sqlite:///{DEFAULT_SOURCES_DB_PATH}"),
)
EZTV_DATABASE_URL = SOURCES_DATABASE_URL

# Ensure parent directories exist for SQLite files
for _url in (MAINSTREAM_DATABASE_URL, SOURCES_DATABASE_URL):
    if _url.startswith("sqlite:///") and not _url.startswith("sqlite:///:memory:"):
        _db_file_path = Path(_url.replace("sqlite:///", ""))
        _db_file_path.parent.mkdir(parents=True, exist_ok=True)

# Connect args needed for SQLite concurrency
connect_args = {"check_same_thread": False} if "sqlite" in MAINSTREAM_DATABASE_URL else {}
eztv_connect_args = {"check_same_thread": False} if "sqlite" in SOURCES_DATABASE_URL else {}

mainstream_engine = create_engine(
    MAINSTREAM_DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)
engine = mainstream_engine

sources_engine = create_engine(
    SOURCES_DATABASE_URL,
    echo=False,
    connect_args=eztv_connect_args,
)
eztv_engine = sources_engine


def get_engine(custom_url: Optional[str] = None):
    """Retrieve or create a mainstream database engine (supports in-memory test databases)."""
    if custom_url:
        args = {"check_same_thread": False} if "sqlite" in custom_url else {}
        return create_engine(custom_url, echo=False, connect_args=args)
    return mainstream_engine


def get_mainstream_engine(custom_url: Optional[str] = None):
    """Canonical alias for get_engine pointing to data/mainstream.db."""
    return get_engine(custom_url)


def get_eztv_engine(custom_url: Optional[str] = None):
    """Retrieve or create the dedicated external sources database engine (data/sources.db)."""
    if custom_url:
        args = {"check_same_thread": False} if "sqlite" in custom_url else {}
        return create_engine(custom_url, echo=False, connect_args=args)
    return sources_engine


def get_sources_engine(custom_url: Optional[str] = None):
    """Canonical alias for get_eztv_engine pointing to data/sources.db."""
    return get_eztv_engine(custom_url)


def init_db(target_engine=None) -> None:
    """Initialize mainstream.db tables, IMDb show merge/badge columns, and composite indexes."""
    active_engine = target_engine or mainstream_engine
    SQLModel.metadata.create_all(active_engine)
    imdb_metadata.create_all(active_engine)
    inspector = inspect(active_engine)
    if "shows" in set(inspector.get_table_names()):
        cols = {c["name"] for c in inspector.get_columns("shows")}
        additive = [
            ("tvmaze_id", "INTEGER"),
            ("status", "TEXT"),
            ("air_day_time", "TEXT"),
            ("streaming_providers", "TEXT"),
            ("has_eztv", "INTEGER DEFAULT 0"),
            ("eztv_id", "INTEGER"),
            ("eztv_slug", "TEXT"),
            ("eztv_match_type", "TEXT"),
        ]
        with active_engine.begin() as conn:
            for col_name, col_type in additive:
                if col_name not in cols:
                    conn.execute(text(f"ALTER TABLE shows ADD COLUMN {col_name} {col_type}"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_votes_rating "
                    "ON shows(rating_votes DESC, rating_score DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_year_votes "
                    "ON shows(start_year DESC, rating_votes DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_type_votes "
                    "ON shows(title_type, rating_votes DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_has_eztv "
                    "ON shows(has_eztv, rating_votes DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_filter_cover "
                    "ON shows(title_type, start_year DESC, rating_score DESC, rating_votes DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_score_cover "
                    "ON shows(rating_score DESC, rating_votes DESC, start_year DESC, title_type)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_shows_facets_cover "
                    "ON shows(title_type, has_eztv, start_year, rating_score, "
                    "genres_ptbr, streaming_providers, status)"
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS sync_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS shows_fts USING fts5(
                        imdb_id,
                        primary_title,
                        original_title,
                        title_ptbr,
                        directors,
                        creators,
                        cast_members,
                        content='shows',
                        content_rowid='rowid',
                        tokenize='unicode61 remove_diacritics 2'
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TRIGGER IF NOT EXISTS mainstream_shows_fts_ai AFTER INSERT ON shows BEGIN
                        INSERT INTO shows_fts(
                            rowid, imdb_id, primary_title, original_title,
                            title_ptbr, directors, creators, cast_members
                        )
                        VALUES (
                            new.rowid, new.imdb_id, new.primary_title, new.original_title,
                            new.title_ptbr, new.directors, new.creators, new.cast_members
                        );
                    END
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TRIGGER IF NOT EXISTS mainstream_shows_fts_ad AFTER DELETE ON shows BEGIN
                        INSERT INTO shows_fts(
                            shows_fts, rowid, imdb_id, primary_title, original_title,
                            title_ptbr, directors, creators, cast_members
                        )
                        VALUES (
                            'delete', old.rowid, old.imdb_id, old.primary_title, old.original_title,
                            old.title_ptbr, old.directors, old.creators, old.cast_members
                        );
                    END
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TRIGGER IF NOT EXISTS mainstream_shows_fts_au AFTER UPDATE ON shows BEGIN
                        INSERT INTO shows_fts(
                            shows_fts, rowid, imdb_id, primary_title, original_title,
                            title_ptbr, directors, creators, cast_members
                        )
                        VALUES (
                            'delete', old.rowid, old.imdb_id, old.primary_title, old.original_title,
                            old.title_ptbr, old.directors, old.creators, old.cast_members
                        );
                        INSERT INTO shows_fts(
                            rowid, imdb_id, primary_title, original_title,
                            title_ptbr, directors, creators, cast_members
                        )
                        VALUES (
                            new.rowid, new.imdb_id, new.primary_title, new.original_title,
                            new.title_ptbr, new.directors, new.creators, new.cast_members
                        );
                    END
                    """
                )
            )
            fts_data_cnt = conn.execute(text("SELECT COUNT(*) FROM shows_fts_data")).scalar() or 0
            shows_cnt = conn.execute(text("SELECT COUNT(*) FROM shows")).scalar() or 0
            if fts_data_cnt <= 2 and shows_cnt > 0:
                conn.execute(text("INSERT INTO shows_fts(shows_fts) VALUES('rebuild')"))


def init_mainstream_db(target_engine=None) -> None:
    """Canonical alias for init_db (data/mainstream.db)."""
    init_db(target_engine)


def init_eztv_db(target_engine=None) -> None:
    """Initialize sources.db tables (EZTV + multi-source + P2P), stats, indexes, and FTS5."""
    from src.backend.models.sources_db import sources_metadata

    active_engine = target_engine or sources_engine
    eztv_metadata.create_all(active_engine)
    sources_metadata.create_all(active_engine)
    from src.backend.models.db import CatalogRelease, CatalogShow

    SQLModel.metadata.create_all(
        active_engine,
        tables=[CatalogShow.__table__, CatalogRelease.__table__],
    )
    inspector = inspect(active_engine)
    table_names = set(inspector.get_table_names())
    if "shows" not in table_names:
        return

    cols = {c["name"] for c in inspector.get_columns("shows")}
    additive_columns = [
        ("streaming_providers", "TEXT"),
        ("episodes_count", "INTEGER DEFAULT 0"),
        ("max_season", "INTEGER"),
        ("max_episode", "INTEGER"),
    ]
    with active_engine.begin() as conn:
        for col_name, col_type in additive_columns:
            if col_name not in cols:
                conn.execute(text(f"ALTER TABLE shows ADD COLUMN {col_name} {col_type}"))

        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_episodes_show_season_ep "
                "ON episodes_catalog(show_id, season, episode)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_shows_rating_id "
                "ON shows(rating_score DESC, id DESC)"
            )
        )

        # Backfill materialized episode stats for shows where episodes_count is 0/NULL
        conn.execute(
            text(
                """
                UPDATE shows
                SET
                    episodes_count = COALESCE((
                        SELECT COUNT(e.id) FROM episodes_catalog e WHERE e.show_id = shows.id
                    ), 0),
                    max_season = (
                        SELECT MAX(e.season) FROM episodes_catalog e WHERE e.show_id = shows.id
                    ),
                    max_episode = (
                        SELECT MAX(e.episode)
                        FROM episodes_catalog e
                        WHERE e.show_id = shows.id
                          AND e.season = (
                              SELECT MAX(e2.season)
                              FROM episodes_catalog e2
                              WHERE e2.show_id = shows.id
                          )
                    )
                WHERE (episodes_count IS NULL OR episodes_count = 0)
                  AND EXISTS (SELECT 1 FROM episodes_catalog e WHERE e.show_id = shows.id)
                """
            )
        )

        # Setup FTS5 virtual table and sync triggers (ADR-010 DEC-006)
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS shows_fts USING fts5(
                    name,
                    slug,
                    imdb_id,
                    genres,
                    network,
                    streaming_providers,
                    content='shows',
                    content_rowid='id'
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS shows_fts_ai AFTER INSERT ON shows BEGIN
                    INSERT INTO shows_fts(
                        rowid, name, slug, imdb_id, genres, network, streaming_providers
                    )
                    VALUES (
                        new.id, new.name, new.slug, new.imdb_id,
                        new.genres, new.network, new.streaming_providers
                    );
                END
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS shows_fts_ad AFTER DELETE ON shows BEGIN
                    INSERT INTO shows_fts(
                        shows_fts, rowid, name, slug, imdb_id,
                        genres, network, streaming_providers
                    )
                    VALUES (
                        'delete', old.id, old.name, old.slug, old.imdb_id,
                        old.genres, old.network, old.streaming_providers
                    );
                END
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS shows_fts_au AFTER UPDATE ON shows BEGIN
                    INSERT INTO shows_fts(
                        shows_fts, rowid, name, slug, imdb_id,
                        genres, network, streaming_providers
                    )
                    VALUES (
                        'delete', old.id, old.name, old.slug, old.imdb_id,
                        old.genres, old.network, old.streaming_providers
                    );
                    INSERT INTO shows_fts(
                        rowid, name, slug, imdb_id, genres, network, streaming_providers
                    )
                    VALUES (
                        new.id, new.name, new.slug, new.imdb_id,
                        new.genres, new.network, new.streaming_providers
                    );
                END
                """
            )
        )
        fts_data_count = conn.execute(text("SELECT COUNT(*) FROM shows_fts_data")).scalar() or 0
        shows_count = conn.execute(text("SELECT COUNT(*) FROM shows")).scalar() or 0
        if fts_data_count <= 2 and shows_count > 0:
            conn.execute(text("INSERT INTO shows_fts(shows_fts) VALUES('rebuild')"))


def init_sources_db(target_engine=None) -> None:
    """Canonical alias for init_eztv_db (data/sources.db)."""
    init_eztv_db(target_engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding main data/mainstream.db sessions with commit/rollback."""
    with Session(mainstream_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_mainstream_session() -> Generator[Session, None, None]:
    """Canonical alias for get_session yielding data/mainstream.db sessions."""
    yield from get_session()


def get_eztv_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding dedicated data/sources.db sessions."""
    with Session(sources_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_sources_session() -> Generator[Session, None, None]:
    """Canonical alias for get_eztv_session yielding data/sources.db sessions."""
    yield from get_eztv_session()
