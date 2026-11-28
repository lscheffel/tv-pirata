"""SQLModel definitions for the dedicated EZTV metadata database (data/eztv_metadata.db)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import MetaData
from sqlmodel import Field, SQLModel

eztv_metadata = MetaData()


class EZTVBase(SQLModel):
    """Isolated SQLModel base so EZTV tables never pollute tv_pirata.db metadata."""

    metadata = eztv_metadata


class EZTVShow(EZTVBase, table=True):
    """Show record stored in data/eztv_metadata.db (table: shows)."""

    __tablename__ = "shows"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: Optional[str] = Field(default=None, index=True)
    name: str
    status: Optional[str] = Field(default=None, index=True)
    status_note: Optional[str] = None
    rating_score: Optional[float] = None
    rating_votes: int = Field(default=0)
    rating_raw: Optional[str] = None
    tooltip: Optional[str] = None
    url: Optional[str] = None
    imdb_id: Optional[str] = Field(default=None, index=True)
    tvmaze_id: Optional[int] = None
    poster_url: Optional[str] = None
    synopsis: Optional[str] = None
    network: Optional[str] = Field(default=None, index=True)
    air_day_time: Optional[str] = None
    premiered: Optional[str] = None
    genres: Optional[str] = None
    cast_members: Optional[str] = None
    streaming_providers: Optional[str] = None
    episodes_count: int = Field(default=0)
    max_season: Optional[int] = Field(default=None)
    max_episode: Optional[int] = Field(default=None)
    details_fetched: int = Field(default=0)
    guide_synced: int = Field(default=0)
    last_error: Optional[str] = None
    updated_at: Optional[str] = None


class EZTVEpisodeCatalog(EZTVBase, table=True):
    """Episode record stored in data/eztv_metadata.db (table: episodes_catalog)."""

    __tablename__ = "episodes_catalog"

    id: Optional[int] = Field(default=None, primary_key=True)
    show_id: int = Field(foreign_key="shows.id", index=True)
    season: int = Field(index=True)
    episode: int = Field(index=True)
    title: Optional[str] = None
    airdate: Optional[str] = None
    runtime: Optional[int] = None
    rating: Optional[float] = None
    summary: Optional[str] = None
    source: str = Field(default="page")
    updated_at: Optional[str] = None
