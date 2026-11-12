"""Unit tests for SQLModel database entities and LibraryRepository operations."""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.backend.models.db import EpisodeRecord, SeasonRecord
from src.backend.models.unified import UnifiedEpisode, UnifiedSeason, UnifiedShow
from src.backend.repositories.library import LibraryRepository


@pytest.fixture
def session():
    """In-memory isolated SQLite session for unit testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_upsert_from_unified_creates_full_hierarchy(session: Session):
    repo = LibraryRepository(session)

    unified = UnifiedShow(
        id=9999,
        title="Arcane",
        overview="Two sisters fight on opposite sides of a war.",
        genres=["Animation", "Sci-Fi", "Action"],
        rating=9.0,
        seasons=[
            UnifiedSeason(
                id=10,
                season_number=1,
                name="Season 1",
                episode_count=3,
                episodes=[
                    UnifiedEpisode(
                        id=101, episode_number=1, season_number=1, title="Welcome to the Playground"
                    ),
                    UnifiedEpisode(
                        id=102, episode_number=2, season_number=1, title="Some Mysteries"
                    ),
                    UnifiedEpisode(
                        id=103, episode_number=3, season_number=1, title="The Base Violence"
                    ),
                ],
            )
        ],
    )

    show = repo.upsert_from_unified(unified, user_status="watching")
    assert show.id is not None
    assert show.tmdb_id == 9999
    assert show.user_status == "watching"
    assert "Animation" in show.genres

    # Verify seasons & episodes
    seasons = session.exec(select(SeasonRecord).where(SeasonRecord.show_id == show.id)).all()
    assert len(seasons) == 1
    assert seasons[0].season_number == 1

    episodes = session.exec(
        select(EpisodeRecord).where(EpisodeRecord.season_id == seasons[0].id)
    ).all()
    assert len(episodes) == 3


def test_toggle_watch_and_calculate_progress(session: Session):
    repo = LibraryRepository(session)

    unified = UnifiedShow(
        id=5555,
        title="Chernobyl",
        overview="The true story of the 1986 nuclear disaster.",
        rating=9.4,
        seasons=[
            UnifiedSeason(
                season_number=1,
                name="Miniseries",
                episode_count=2,
                episodes=[
                    UnifiedEpisode(id=1, episode_number=1, season_number=1, title="1:23:45"),
                    UnifiedEpisode(
                        id=2, episode_number=2, season_number=1, title="Please Remain Calm"
                    ),
                ],
            )
        ],
    )

    show = repo.upsert_from_unified(unified)
    episodes = session.exec(select(EpisodeRecord)).all()
    ep1 = episodes[0]

    # Initial progress: 0%
    prog = repo.get_show_progress(show.id)
    assert prog["watched_episodes"] == 0
    assert prog["progress_pct"] == 0.0
    assert not prog["is_completed"]

    # Watch episode 1
    watch1 = repo.toggle_episode_watch(ep1.id)
    assert watch1.is_watched
    assert watch1.watched_at is not None

    prog = repo.get_show_progress(show.id)
    assert prog["watched_episodes"] == 1
    assert prog["progress_pct"] == 50.0

    # Watch episode 2 via watch_all_in_season
    repo.watch_all_in_season(ep1.season_id, is_watched=True)
    prog = repo.get_show_progress(show.id)
    assert prog["watched_episodes"] == 2
    assert prog["progress_pct"] == 100.0
    assert prog["is_completed"]


def test_local_media_tracking(session: Session):
    repo = LibraryRepository(session)

    unified = UnifiedShow(
        id=123,
        title="Dark",
        seasons=[
            UnifiedSeason(
                season_number=1,
                episode_count=1,
                episodes=[
                    UnifiedEpisode(id=1, episode_number=1, season_number=1, title="Secrets")
                ],
            )
        ],
    )
    repo.upsert_from_unified(unified)
    ep = session.exec(select(EpisodeRecord)).first()

    media = repo.set_local_media(ep.id, relative_path="Dark/Season 1/S01E01.mkv", is_available=True)
    assert media.is_available
    assert media.relative_path == "Dark/Season 1/S01E01.mkv"

    # Mark as unavailable (e.g. disk unmounted)
    media_updated = repo.set_local_media(
        ep.id, relative_path="Dark/Season 1/S01E01.mkv", is_available=False
    )
    assert not media_updated.is_available


def test_tags_and_smart_collections(session: Session):
    repo = LibraryRepository(session)

    # Create shows
    repo.upsert_from_unified(
        UnifiedShow(id=1, title="Severance", genres=["Sci-Fi", "Thriller"], rating=8.7),
        user_status="watching",
    )
    repo.upsert_from_unified(
        UnifiedShow(id=2, title="Ted Lasso", genres=["Comedy"], rating=8.8),
        user_status="completed",
    )

    # Tags
    repo.create_tag("Favoritos", color="#00ff00")
    tags = repo.list_tags()
    assert len(tags) == 1
    assert tags[0].name == "Favoritos"

    # Smart collection: Sci-Fi watching
    collection = repo.create_collection(
        name="Sci-Fi em Andamento",
        description="Minhas séries de ficção científica",
        filter_criteria={"user_status": "watching", "genre": "Sci-Fi"},
    )
    assert collection.id is not None

    items = repo.query_smart_collection(collection.id)
    assert len(items) == 1
    assert items[0].title == "Severance"
