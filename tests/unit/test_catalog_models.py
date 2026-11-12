"""Unit tests for CatalogShow and CatalogRelease database entities."""

from datetime import datetime, timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.backend.models.db import CatalogRelease, CatalogShow


def test_catalog_show_and_release_lifecycle():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        show = CatalogShow(
            imdb_id="tt0944947",
            title="Game of Thrones",
            overview="Epic fantasy drama series.",
            rating=9.2,
            genres="Drama, Action, Fantasy",
            total_torrents=2,
            max_seeds=150,
            latest_season=8,
            latest_episode=6,
            latest_release_date=datetime.now(timezone.utc),
        )
        session.add(show)

        rel1 = CatalogRelease(
            eztv_id=1001,
            hash="abc123hash",
            imdb_id="tt0944947",
            title="Game of Thrones S01E01 1080p",
            season=1,
            episode=1,
            quality="1080p",
            seeds=150,
            peers=20,
            size_bytes=1500000000,
            magnet_url="magnet:?xt=urn:btih:abc123hash",
        )
        rel2 = CatalogRelease(
            eztv_id=1002,
            hash="def456hash",
            imdb_id="tt0944947",
            title="Game of Thrones S01E01 720p",
            season=1,
            episode=1,
            quality="720p",
            seeds=50,
            peers=5,
            size_bytes=800000000,
            magnet_url="magnet:?xt=urn:btih:def456hash",
        )
        session.add(rel1)
        session.add(rel2)
        session.commit()

        # Query and assert relationships
        queried = session.get(CatalogShow, "tt0944947")
        assert queried is not None
        assert queried.title == "Game of Thrones"
        assert queried.max_seeds == 150
        assert len(queried.releases) == 2
        assert queried.releases[0].quality in ["1080p", "720p"]
