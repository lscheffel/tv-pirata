"""Relational SQLModel database entities for TV Pirata."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class ShowTagLink(SQLModel, table=True):
    """Many-to-many link between ShowRecord and TagRecord."""

    show_id: Optional[int] = Field(default=None, foreign_key="showrecord.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tagrecord.id", primary_key=True)


class TagRecord(SQLModel, table=True):
    """User-defined tags for classification."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: str = Field(default="#e50914")

    shows: List["ShowRecord"] = Relationship(back_populates="tags", link_model=ShowTagLink)


class CollectionRecord(SQLModel, table=True):
    """Smart collections defined by JSON filter criteria."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = ""
    filter_criteria: str = Field(default="{}")  # Stored as JSON string
    created_at: datetime = Field(default_factory=utc_now)


class ShowRecord(SQLModel, table=True):
    """Primary relational representation of a show in the user's personal library."""

    id: Optional[int] = Field(default=None, primary_key=True)
    tmdb_id: int = Field(unique=True, index=True)
    tvmaze_id: Optional[int] = Field(default=None, index=True)
    imdb_id: Optional[str] = Field(default=None, index=True)
    title: str = Field(index=True)
    original_title: Optional[str] = None
    overview: str = ""
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    rating: float = 0.0
    genres: str = ""  # Comma-separated genre list
    first_air_date: Optional[str] = None
    status: Optional[str] = None
    user_status: str = Field(default="plan_to_watch", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    seasons: List["SeasonRecord"] = Relationship(
        back_populates="show",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    tags: List[TagRecord] = Relationship(back_populates="shows", link_model=ShowTagLink)


class SeasonRecord(SQLModel, table=True):
    """Relational representation of a show's season."""

    id: Optional[int] = Field(default=None, primary_key=True)
    show_id: int = Field(foreign_key="showrecord.id", index=True)
    season_number: int = Field(index=True)
    name: str = ""
    overview: str = ""
    poster_url: Optional[str] = None
    episode_count: int = 0

    show: Optional[ShowRecord] = Relationship(back_populates="seasons")
    episodes: List["EpisodeRecord"] = Relationship(
        back_populates="season",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class EpisodeRecord(SQLModel, table=True):
    """Relational representation of an individual episode."""

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="seasonrecord.id", index=True)
    episode_number: int = Field(index=True)
    title: str = ""
    overview: str = ""
    air_date: Optional[str] = None
    rating: Optional[float] = None

    season: Optional[SeasonRecord] = Relationship(back_populates="episodes")
    watch: Optional["EpisodeWatchRecord"] = Relationship(
        back_populates="episode",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False},
    )
    media: Optional["LocalMediaRecord"] = Relationship(
        back_populates="episode",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "uselist": False},
    )


class EpisodeWatchRecord(SQLModel, table=True):
    """Granular tracking of episode watch state and timestamp."""

    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episoderecord.id", unique=True, index=True)
    is_watched: bool = Field(default=False, index=True)
    watched_at: Optional[datetime] = None

    episode: Optional[EpisodeRecord] = Relationship(back_populates="watch")


class LocalMediaRecord(SQLModel, table=True):
    """Tracking of local/SMB file availability for an episode."""

    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episoderecord.id", unique=True, index=True)
    relative_path: str = ""
    is_available: bool = Field(default=True, index=True)
    last_seen_at: datetime = Field(default_factory=utc_now)

    episode: Optional[EpisodeRecord] = Relationship(back_populates="media")


class CatalogShow(SQLModel, table=True):
    """TV Show catalog entry aggregated from EZTV releases."""

    imdb_id: str = Field(primary_key=True, index=True)  # Format: tt1234567
    title: str = Field(index=True)
    original_title: Optional[str] = None
    overview: str = ""
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    rating: float = 0.0
    genres: str = ""  # CSV format
    first_air_date: Optional[str] = None
    status: Optional[str] = None
    total_torrents: int = Field(default=0, index=True)
    max_seeds: int = Field(default=0, index=True)
    latest_season: int = Field(default=0, index=True)
    latest_episode: int = Field(default=0, index=True)
    latest_release_date: Optional[datetime] = None
    is_enriched: bool = Field(default=False, index=True)
    last_synced_at: datetime = Field(default_factory=utc_now)

    releases: List["CatalogRelease"] = Relationship(
        back_populates="show",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class CatalogRelease(SQLModel, table=True):
    """Torrent release item indexed from EZTV."""

    id: Optional[int] = Field(default=None, primary_key=True)
    eztv_id: int = Field(unique=True, index=True)
    hash: str = Field(index=True)
    imdb_id: str = Field(foreign_key="catalogshow.imdb_id", index=True)
    title: str = ""
    filename: str = ""
    season: int = Field(default=0, index=True)
    episode: int = Field(default=0, index=True)
    quality: str = Field(default="Unknown", index=True)
    seeds: int = Field(default=0, index=True)
    peers: int = 0
    size_bytes: int = 0
    magnet_url: str
    torrent_url: Optional[str] = None
    date_released_unix: int = 0
    created_at: datetime = Field(default_factory=utc_now)

    show: Optional[CatalogShow] = Relationship(back_populates="releases")


class ReleaseNotificationRecord(SQLModel, table=True):
    """Eventos de notificação para episódios recém-disponibilizados de séries salvas."""

    __table_args__ = (
        UniqueConstraint("show_id", "season", "episode", name="uq_notification_episode"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    show_id: int = Field(foreign_key="showrecord.id", index=True)
    imdb_id: str = Field(index=True)
    show_title: str = Field(default="")
    season: int = Field(default=0, index=True)
    episode: int = Field(default=0, index=True)
    release_title: str = Field(default="")
    quality: str = Field(default="Unknown")
    seeds: int = Field(default=0)
    magnet_url: str = Field(default="")
    is_read: bool = Field(default=False, index=True)
    is_dismissed: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

    show: Optional[ShowRecord] = Relationship()
