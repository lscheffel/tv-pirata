"""Integration tests for /api/catalog REST endpoints."""

from datetime import datetime, timezone

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, delete

from src.backend.core.database import get_session
from src.backend.main import app
from src.backend.models.db import CatalogRelease, CatalogShow

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)


def override_get_session():
    with Session(test_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def seed_catalog():
    app.dependency_overrides[get_session] = override_get_session
    with Session(test_engine) as session:
        # Clear existing
        session.exec(delete(CatalogRelease))
        session.exec(delete(CatalogShow))
        session.commit()

        show1 = CatalogShow(
            imdb_id="tt0944947",
            title="Game of Thrones",
            overview="Epic fantasy saga.",
            rating=9.3,
            genres="Drama, Action",
            total_torrents=2,
            max_seeds=350,
            latest_season=8,
            latest_episode=6,
            latest_release_date=datetime.now(timezone.utc),
        )
        show2 = CatalogShow(
            imdb_id="tt0903747",
            title="Breaking Bad",
            overview="Chemistry teacher turns meth kingpin.",
            rating=9.5,
            genres="Crime, Drama",
            total_torrents=1,
            max_seeds=180,
            latest_season=5,
            latest_episode=16,
            latest_release_date=datetime.now(timezone.utc),
        )
        session.add(show1)
        session.add(show2)

        rel1 = CatalogRelease(
            eztv_id=701,
            hash="got_hash",
            imdb_id="tt0944947",
            title="Game.of.Thrones.S08E06.1080p.mkv",
            season=8,
            episode=6,
            quality="1080p",
            seeds=350,
            peers=50,
            size_bytes=2500000000,
            magnet_url="magnet:?xt=urn:btih:got_hash",
        )
        session.add(rel1)
        session.commit()


def test_list_catalog_shows():
    res = client.get("/api/catalog/shows")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # Ordered by seeds descending by default
    assert data["items"][0]["title"] == "Game of Thrones"
    assert data["items"][0]["max_seeds"] == 350


def test_filter_catalog_shows():
    # Filter by min_seeds
    res_seeds = client.get("/api/catalog/shows?min_seeds=200")
    assert res_seeds.status_code == 200
    assert res_seeds.json()["total"] == 1
    assert res_seeds.json()["items"][0]["imdb_id"] == "tt0944947"

    # Search filter
    res_search = client.get("/api/catalog/shows?search=Breaking")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1
    assert res_search.json()["items"][0]["title"] == "Breaking Bad"


def test_get_catalog_show_detail():
    res = client.get("/api/catalog/shows/tt0944947")
    assert res.status_code == 200
    data = res.json()
    assert data["show"]["title"] == "Game of Thrones"
    assert len(data["releases"]) == 1
    assert data["releases"][0]["quality"] == "1080p"

    # 404 for missing
    res_404 = client.get("/api/catalog/shows/tt9999999")
    assert res_404.status_code == 404


def test_get_catalog_stats():
    res = client.get("/api/catalog/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_shows"] == 2
    assert data["total_releases"] == 1
    assert data["max_seeds_in_catalog"] == 350


def test_sync_catalog_endpoint():
    fake_eztv = {
        "torrents": [
            {
                "id": 801,
                "hash": "new_hash",
                "filename": "Fargo.S05E01.720p.mkv",
                "title": "Fargo S05E01 720p EZTV",
                "imdb_id": "2802850",
                "season": "5",
                "episode": "1",
                "seeds": 120,
                "peers": 15,
                "size_bytes": 1000000000,
                "date_released_unix": 1700000000,
                "magnet_url": "magnet:?xt=urn:btih:new_hash",
            }
        ]
    }

    with respx.mock(base_url="https://eztvx.to/api") as eztv_mock:
        eztv_mock.get("/get-torrents").respond(json=fake_eztv)
        res = client.post("/api/catalog/sync?start_page=1&pages=1&enrich=false")
        assert res.status_code == 200
        telemetry = res.json()["telemetry"]
        assert telemetry["shows_created"] == 1
        assert telemetry["torrents_indexed"] == 1


def test_discovery_trending_fallback_to_catalog():
    # Both TMDB and TVMaze fail
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://api.themoviedb.org/3/trending/tv/day").respond(500)
        respx_mock.get("https://api.tvmaze.com/shows").respond(500)

        res = client.get("/api/discovery/trending")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 2
        assert data[0]["source_provider"] == "eztv-catalog"
        assert data[0]["title"] == "Game of Thrones"


def test_torrents_shows_fallback_to_catalog():
    # External EZTV returns 500 error
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://eztvx.to/api/get-torrents").respond(500)

        res = client.get("/api/torrents/shows/tt0944947")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["hash"] == "got_hash"
        assert data[0]["quality"] == "1080p"


def test_discovery_show_details_catalog_fallback():
    # Fetch show by numeric ID or IMDB ID when online providers fail
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://api.tvmaze.com/lookup/shows").respond(404)
        respx_mock.get("https://api.themoviedb.org/3/tv/944947").respond(404)

        res = client.get("/api/discovery/shows/944947?provider=eztv-catalog")
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Game of Thrones"
        assert data["imdb_id"] == "tt0944947"
        assert data["source_provider"] == "eztv-catalog"


def test_get_catalog_genres():
    res = client.get("/api/catalog/genres")
    assert res.status_code == 200
    genres = res.json()
    assert len(genres) >= 2
    names = [g["genre"] for g in genres]
    assert "Drama" in names


def test_get_curated_sections():
    res = client.get("/api/catalog/sections")
    assert res.status_code == 200
    sections = res.json()
    assert len(sections) >= 1
    sec_ids = [s["id"] for s in sections]
    assert "top_p2p" in sec_ids
