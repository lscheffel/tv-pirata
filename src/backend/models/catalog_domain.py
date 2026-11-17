"""Canonical domain entities for Layer 1 — Audiovisual Discovery Core (ADR-008)."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import MetaData, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

imdb_metadata = MetaData()


class IMDbBase(SQLModel):
    """Isolated metadata so IMDb catalog tables only auto-create on explicit init_db()."""

    metadata = imdb_metadata


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class WorkGenreLink(SQLModel, table=True):
    """Many-to-many association between MediaWork and GenreRecord."""

    work_id: Optional[int] = Field(
        default=None, foreign_key="mediawork.id", primary_key=True, index=True
    )
    genre_id: Optional[int] = Field(
        default=None, foreign_key="genrerecord.id", primary_key=True, index=True
    )


class GenreRecord(SQLModel, table=True):
    """Normalized audiovisual genre taxonomy."""

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str = Field(index=True)

    works: List["MediaWork"] = Relationship(
        back_populates="genre_records", link_model=WorkGenreLink
    )


class MediaWork(SQLModel, table=True):
    """Canonical representation of an audiovisual work across all formats and sources.

    Supports movies, TV series, mini-series, specials, documentaries, and animations
    independently of local files or P2P torrent availability.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    work_type: str = Field(default="movie", index=True)
    title: str = Field(index=True)
    original_title: Optional[str] = Field(default=None, index=True)
    overview: str = Field(default="")
    tagline: Optional[str] = Field(default=None)

    release_date: Optional[str] = Field(default=None, index=True)
    end_date: Optional[str] = Field(default=None)
    release_year: Optional[int] = Field(default=None, index=True)
    runtime_minutes: Optional[int] = Field(default=None, index=True)

    status: str = Field(default="Released", index=True)
    origin_country: str = Field(default="US", index=True)
    original_language: str = Field(default="en", index=True)

    poster_url: Optional[str] = Field(default=None)
    backdrop_url: Optional[str] = Field(default=None)

    canonical_rating: float = Field(default=0.0, index=True)
    rating_source: str = Field(default="consolidated")
    ratings_breakdown: str = Field(default="{}")  # JSON mapping provider -> {rating, votes}
    popularity_score: float = Field(default=0.0, index=True)
    vote_count: int = Field(default=0)

    seasons_count: int = Field(default=0, index=True)
    episodes_count: int = Field(default=0)
    network_or_studio: Optional[str] = Field(default=None, index=True)
    collection_name: Optional[str] = Field(default=None, index=True)
    genres_csv: str = Field(default="")  # Denormalized CSV for fast display alongside M2M

    # Direct fast-lookup external keys (canonical cross-reference)
    imdb_id: Optional[str] = Field(default=None, index=True)
    tmdb_id: Optional[int] = Field(default=None, index=True)
    tvmaze_id: Optional[int] = Field(default=None, index=True)
    wikidata_id: Optional[str] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    genre_records: List[GenreRecord] = Relationship(
        back_populates="works", link_model=WorkGenreLink
    )
    external_ids: List["ExternalIdentifier"] = Relationship(
        back_populates="work",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    provenance_records: List["DataProvenance"] = Relationship(
        back_populates="work",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    credits: List["WorkCredit"] = Relationship(
        back_populates="work",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    availabilities: List["StreamingAvailability"] = Relationship(
        back_populates="work",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    calendar_events: List["ReleaseCalendarEvent"] = Relationship(
        back_populates="work",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ExternalIdentifier(SQLModel, table=True):
    """Cross-referenced external identifier linked to a canonical MediaWork."""

    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_external_provider_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    work_id: int = Field(foreign_key="mediawork.id", index=True)
    provider: str = Field(index=True)  # imdb, tmdb_movie, tmdb_tv, tvmaze, wikidata
    external_id: str = Field(index=True)
    confidence: str = Field(default="deterministic")  # deterministic, high, probabilistic
    created_at: datetime = Field(default_factory=utc_now)

    work: Optional[MediaWork] = Relationship(back_populates="external_ids")


class DataProvenance(SQLModel, table=True):
    """Field-level provenance log preserving origin, value, and selection rationale."""

    id: Optional[int] = Field(default=None, primary_key=True)
    work_id: int = Field(foreign_key="mediawork.id", index=True)
    source_provider: str = Field(index=True)
    external_id: str = Field(default="")
    field_name: str = Field(index=True)
    field_value: str = Field(default="")
    selection_reason: str = Field(default="corroborated_source")
    fetched_at: datetime = Field(default_factory=utc_now)

    work: Optional[MediaWork] = Relationship(back_populates="provenance_records")


class PersonRecord(SQLModel, table=True):
    """Canonical representation of an actor, director, writer, creator, or producer."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    imdb_id: Optional[str] = Field(default=None, index=True)
    tmdb_id: Optional[int] = Field(default=None, index=True)
    tvmaze_id: Optional[int] = Field(default=None, index=True)
    known_for_department: str = Field(default="Acting", index=True)
    profile_url: Optional[str] = Field(default=None)
    biography: str = Field(default="")
    birth_year: Optional[int] = Field(default=None)
    country: Optional[str] = Field(default=None)

    credits: List["WorkCredit"] = Relationship(
        back_populates="person",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class WorkCredit(SQLModel, table=True):
    """Explicit credit linking a PersonRecord to a MediaWork with role and character."""

    id: Optional[int] = Field(default=None, primary_key=True)
    work_id: int = Field(foreign_key="mediawork.id", index=True)
    person_id: int = Field(foreign_key="personrecord.id", index=True)
    role_type: str = Field(
        default="actor", index=True
    )  # director, actor, writer, creator, producer
    character_name: Optional[str] = Field(default=None)
    billing_order: int = Field(default=0)

    work: Optional[MediaWork] = Relationship(back_populates="credits")
    person: Optional[PersonRecord] = Relationship(back_populates="credits")


class StreamingAvailability(SQLModel, table=True):
    """Platform distribution and territorial availability for a MediaWork."""

    id: Optional[int] = Field(default=None, primary_key=True)
    work_id: int = Field(foreign_key="mediawork.id", index=True)
    provider_name: str = Field(
        index=True
    )  # Netflix, Prime Video, Max, Apple TV+, Disney+, MUBI, Globoplay
    territory: str = Field(default="BR", index=True)
    monetization_type: str = Field(default="flatrate", index=True)  # flatrate, rent, buy
    link_url: Optional[str] = Field(default=None)
    source_provider: str = Field(default="justwatch-federated")
    updated_at: datetime = Field(default_factory=utc_now)

    work: Optional[MediaWork] = Relationship(back_populates="availabilities")


class WorkRelation(SQLModel, table=True):
    """Explicit relationship between two MediaWork entities (sequel, prequel, remake)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source_work_id: int = Field(foreign_key="mediawork.id", index=True)
    target_work_id: int = Field(foreign_key="mediawork.id", index=True)
    relation_type: str = Field(
        index=True
    )  # sequel, prequel, spinoff, remake, reboot, collection, related
    notes: Optional[str] = Field(default=None)


class ReleaseCalendarEvent(SQLModel, table=True):
    """Unified audiovisual release calendar event with explicit confidence level."""

    id: Optional[int] = Field(default=None, primary_key=True)
    work_id: int = Field(foreign_key="mediawork.id", index=True)
    event_type: str = Field(
        index=True
    )  # theatrical_premiere, streaming_premiere, new_season, new_episode, announced_production
    event_date: str = Field(index=True)  # YYYY-MM-DD
    confidence_level: str = Field(
        default="confirmed", index=True
    )  # confirmed, estimated, announced
    territory: str = Field(default="GLOBAL", index=True)
    platform_or_network: Optional[str] = Field(default=None, index=True)
    season_number: Optional[int] = Field(default=None)
    episode_number: Optional[int] = Field(default=None)
    event_title: str = Field(default="")
    source_provider: str = Field(default="tmdb")

    work: Optional[MediaWork] = Relationship(back_populates="calendar_events")


class IMDbCatalogShow(IMDbBase, table=True):
    """Canonical universal title in data/mainstream.db (IMDb backbone + TMDB/TVMaze merge)."""

    __tablename__ = "shows"

    imdb_id: str = Field(primary_key=True)
    imdb_num: Optional[int] = Field(default=None, index=True)
    tmdb_id: Optional[int] = Field(default=None, index=True)
    title_type: str = Field(default="movie", index=True)
    primary_title: str = Field(index=True)
    original_title: Optional[str] = Field(default=None)
    title_ptbr: Optional[str] = Field(default=None, index=True)
    tagline: Optional[str] = Field(default=None)
    is_adult: int = Field(default=0)
    start_year: Optional[int] = Field(default=None, index=True)
    end_year: Optional[int] = Field(default=None)
    runtime_minutes: Optional[int] = Field(default=None)
    genres: Optional[str] = Field(default=None)
    genres_ptbr: Optional[str] = Field(default=None)
    rating_score: Optional[float] = Field(default=None)
    rating_votes: int = Field(default=0, index=True)
    poster_url: Optional[str] = Field(default=None)
    backdrop_url: Optional[str] = Field(default=None)
    trailer_url: Optional[str] = Field(default=None)
    synopsis: Optional[str] = Field(default=None)
    synopsis_ptbr: Optional[str] = Field(default=None)
    content_rating: Optional[str] = Field(default=None)
    release_date: Optional[str] = Field(default=None)
    countries: Optional[str] = Field(default=None)
    languages: Optional[str] = Field(default=None)
    network: Optional[str] = Field(default=None)
    directors: Optional[str] = Field(default=None)
    creators: Optional[str] = Field(default=None)
    cast_members: Optional[str] = Field(default=None)
    keywords: Optional[str] = Field(default=None)
    total_seasons: Optional[int] = Field(default=None)
    details_fetched: int = Field(default=0)
    tmdb_synced: int = Field(default=0, index=True)
    tvmaze_id: Optional[int] = Field(default=None)
    status: Optional[str] = Field(default=None)
    air_day_time: Optional[str] = Field(default=None)
    streaming_providers: Optional[str] = Field(default=None)
    has_eztv: int = Field(default=0, index=True)
    eztv_id: Optional[int] = Field(default=None, index=True)
    eztv_slug: Optional[str] = Field(default=None)
    eztv_match_type: Optional[str] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)


class IMDbEpisodeCatalog(IMDbBase, table=True):
    """Canonical IMDb episode tree stored in data/mainstream.db (table: episodes_catalog)."""

    __tablename__ = "episodes_catalog"

    episode_imdb_id: str = Field(primary_key=True)
    show_imdb_id: str = Field(foreign_key="shows.imdb_id", index=True)
    season: Optional[int] = Field(default=None)
    episode: Optional[int] = Field(default=None)
    title: Optional[str] = Field(default=None)
    start_year: Optional[int] = Field(default=None)
    runtime_minutes: Optional[int] = Field(default=None)
    rating_score: Optional[float] = Field(default=None)
    rating_votes: int = Field(default=0)
    updated_at: Optional[str] = Field(default=None)
