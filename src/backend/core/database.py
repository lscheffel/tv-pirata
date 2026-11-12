"""Database configuration and session management for TV Pirata."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine

import src.backend.models  # noqa: F401

# Default SQLite database path
DEFAULT_DB_PATH = Path("data/tv_pirata.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Ensure parent directory exists for SQLite
if DATABASE_URL.startswith("sqlite:///") and not DATABASE_URL.startswith("sqlite:///:memory:"):
    db_file_path = Path(DATABASE_URL.replace("sqlite:///", ""))
    db_file_path.parent.mkdir(parents=True, exist_ok=True)

# Connect args needed for SQLite concurrency
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)


def get_engine(custom_url: Optional[str] = None):
    """Retrieve or create a database engine (supports in-memory test databases)."""
    if custom_url:
        args = {"check_same_thread": False} if "sqlite" in custom_url else {}
        return create_engine(custom_url, echo=False, connect_args=args)
    return engine


def init_db(target_engine=None) -> None:
    """Initialize database tables deterministically."""
    active_engine = target_engine or engine
    SQLModel.metadata.create_all(active_engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database sessions with automatic commit/rollback."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
