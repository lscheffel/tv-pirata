"""Additive SQLModel definitions for multi-provider external sources in data/sources.db."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import MetaData, UniqueConstraint
from sqlmodel import Field, SQLModel

sources_metadata = MetaData()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourcesBase(SQLModel):
    """Isolated SQLModel base targeting data/sources.db without polluting mainstream.db."""

    metadata = sources_metadata


class ExternalSourceRecord(SourcesBase, table=True):
    """Registry entry, dynamic instance configuration, and sync telemetry for a media source."""

    __tablename__ = "external_sources"

    source_key: str = Field(primary_key=True)
    display_name: str
    adapter_key: str = Field(default="eztv", index=True)
    source_kind: str = Field(default="torrent_mirrorable", index=True)
    kind: str = Field(default="torrent_api")
    media_types: str = Field(default="tvSeries")
    base_url: Optional[str] = None
    config_json: str = Field(default="{}")
    priority: int = Field(default=100, index=True)
    enabled: bool = Field(default=True, index=True)
    status: str = Field(default="ready", index=True)
    cooldown_until: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    total_titles: int = Field(default=0)
    total_releases: int = Field(default=0)


class ExternalRelease(SourcesBase, table=True):
    """Provider-agnostic external release/link indexed in data/sources.db."""

    __tablename__ = "external_releases"
    __table_args__ = (
        UniqueConstraint("source_key", "external_id", name="uq_external_source_release"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    source_key: str = Field(index=True)
    external_id: str = Field(index=True)
    imdb_id: Optional[str] = Field(default=None, index=True)
    title: str = Field(index=True)
    work_type: str = Field(default="movie", index=True)
    season: int = Field(default=0, index=True)
    episode: int = Field(default=0, index=True)
    quality: str = Field(default="Unknown", index=True)
    seeds: int = Field(default=0, index=True)
    peers: int = Field(default=0)
    size_bytes: int = Field(default=0)
    release_type: str = Field(default="magnet")
    magnet_url: Optional[str] = None
    torrent_url: Optional[str] = None
    external_url: Optional[str] = None
    info_hash: Optional[str] = Field(default=None, index=True)
    poster_url: Optional[str] = None
    genres: Optional[str] = None
    year: Optional[int] = None
    rating: float = Field(default=0.0)
    matched_by: str = Field(default="exact_imdb")
    match_confidence: float = Field(default=1.0)
    last_checked_at: Optional[datetime] = Field(default_factory=_utc_now)
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utc_now)
