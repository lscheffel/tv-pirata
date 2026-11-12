"""Unit tests for EZTVIndexerService title parsing and synchronization."""

import pytest
import respx
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.backend.models.db import CatalogRelease, CatalogShow
from src.backend.services.catalog_indexer import EZTVIndexerService


def test_normalize_imdb_id():
    assert EZTVIndexerService.normalize_imdb_id("0944947") == "tt0944947"
    assert EZTVIndexerService.normalize_imdb_id("tt0944947") == "tt0944947"
    assert EZTVIndexerService.normalize_imdb_id(944947) == "tt0944947"
    assert EZTVIndexerService.normalize_imdb_id("31842126") == "tt31842126"
    assert EZTVIndexerService.normalize_imdb_id("0") is None
    assert EZTVIndexerService.normalize_imdb_id("") is None
    assert EZTVIndexerService.normalize_imdb_id(None) is None


def test_extract_clean_show_title():
    t1 = "Location Location Location S46E08 720p WEB H264-JFF EZTV"
    assert EZTVIndexerService.extract_clean_show_title(t1) == "Location Location Location"

    t2 = "The.Good.Daughter.2026.S01E01.1080p.AMZN.WEB-DL.DDP2.0.H.264[EZTVx.to].mkv"
    assert EZTVIndexerService.extract_clean_show_title(t2) == "The Good Daughter 2026"

    t3 = "Game of Thrones S01E01 1080p HDTV x264-EZTV"
    assert EZTVIndexerService.extract_clean_show_title(t3) == "Game of Thrones"


@pytest.mark.asyncio
async def test_sync_pages_with_mocks():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    fake_eztv_payload = {
        "torrents_count": 2,
        "torrents": [
            {
                "id": 5001,
                "hash": "hash111",
                "filename": "Severance.S02E01.1080p.WEB.mkv",
                "title": "Severance S02E01 1080p WEB EZTV",
                "imdb_id": "11280740",
                "season": "2",
                "episode": "1",
                "seeds": 200,
                "peers": 40,
                "size_bytes": "2000000000",
                "date_released_unix": 1700000000,
                "magnet_url": "magnet:?xt=urn:btih:hash111",
            },
            {
                "id": 5002,
                "hash": "hash222",
                "filename": "Severance.S02E01.720p.WEB.mkv",
                "title": "Severance S02E01 720p WEB EZTV",
                "imdb_id": "11280740",
                "season": "2",
                "episode": "1",
                "seeds": 90,
                "peers": 10,
                "size_bytes": "1000000000",
                "date_released_unix": 1700000000,
                "magnet_url": "magnet:?xt=urn:btih:hash222",
            },
        ],
    }

    fake_tvmaze_payload = {
        "id": 444,
        "name": "Severance",
        "summary": (
            "<p>Mark leads a team of office workers whose memories have been "
            "surgically divided.</p>"
        ),
        "rating": {"average": 8.7},
        "genres": ["Drama", "Sci-Fi", "Thriller"],
        "premiered": "2022-02-18",
        "status": "Running",
        "image": {"original": "https://images.tvmaze.com/severance.jpg"},
    }

    with (
        respx.mock(base_url="https://eztvx.to/api") as eztv_mock,
        respx.mock(base_url="https://api.tvmaze.com") as tvmaze_mock,
    ):
        eztv_mock.get("/get-torrents").respond(json=fake_eztv_payload)
        tvmaze_mock.get("/lookup/shows").respond(json=fake_tvmaze_payload)

        indexer = EZTVIndexerService()
        with Session(engine) as session:
            telemetry = await indexer.sync_pages(
                session=session,
                start_page=1,
                max_pages=1,
                enrich_metadata=True,
            )

            assert telemetry["pages_processed"] == 1
            assert telemetry["torrents_indexed"] == 2
            assert telemetry["shows_created"] == 1
            assert telemetry["shows_enriched"] == 1

            show = session.get(CatalogShow, "tt11280740")
            assert show is not None
            assert show.title == "Severance"
            assert show.rating == 8.7
            assert show.max_seeds == 200
            assert show.total_torrents == 2
            assert show.poster_url == "https://images.tvmaze.com/severance.jpg"
            assert show.is_enriched is True

            releases = session.exec(select(CatalogRelease)).all()
            assert len(releases) == 2
