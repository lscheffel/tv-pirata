"""Database configuration and session management for TV Pirata."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

import src.backend.models  # noqa: F401
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

# Default SQLite database paths
DEFAULT_DB_PATH = Path("data/tv_pirata.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

DEFAULT_EZTV_DB_PATH = Path("data/eztv_metadata.db")
EZTV_DATABASE_URL = os.getenv("EZTV_DATABASE_URL", f"sqlite:///{DEFAULT_EZTV_DB_PATH}")

# Ensure parent directories exist for SQLite files
for _url in (DATABASE_URL, EZTV_DATABASE_URL):
    if _url.startswith("sqlite:///") and not _url.startswith("sqlite:///:memory:"):
        _db_file_path = Path(_url.replace("sqlite:///", ""))
        _db_file_path.parent.mkdir(parents=True, exist_ok=True)

# Connect args needed for SQLite concurrency
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
eztv_connect_args = {"check_same_thread": False} if "sqlite" in EZTV_DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)

eztv_engine = create_engine(
    EZTV_DATABASE_URL,
    echo=False,
    connect_args=eztv_connect_args,
)


def get_engine(custom_url: Optional[str] = None):
    """Retrieve or create a database engine (supports in-memory test databases)."""
    if custom_url:
        args = {"check_same_thread": False} if "sqlite" in custom_url else {}
        return create_engine(custom_url, echo=False, connect_args=args)
    return engine


def get_eztv_engine(custom_url: Optional[str] = None):
    """Retrieve or create the dedicated EZTV metadata database engine."""
    if custom_url:
        args = {"check_same_thread": False} if "sqlite" in custom_url else {}
        return create_engine(custom_url, echo=False, connect_args=args)
    return eztv_engine


def init_db(target_engine=None) -> None:
    """Initialize main tv_pirata.db tables deterministically."""
    active_engine = target_engine or engine
    SQLModel.metadata.create_all(active_engine)


def init_eztv_db(target_engine=None) -> None:
    """Initialize eztv_metadata.db tables, materialized stats, indexes, and FTS5 idempotently."""
    active_engine = target_engine or eztv_engine
    eztv_metadata.create_all(active_engine)
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
        fts_count = conn.execute(text("SELECT COUNT(*) FROM shows_fts")).scalar() or 0
        shows_count = conn.execute(text("SELECT COUNT(*) FROM shows")).scalar() or 0
        if fts_count == 0 and shows_count > 0:
            conn.execute(text("INSERT INTO shows_fts(shows_fts) VALUES('rebuild')"))


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding main tv_pirata.db sessions with commit/rollback."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_eztv_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding dedicated eztv_metadata.db sessions."""
    with Session(eztv_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
