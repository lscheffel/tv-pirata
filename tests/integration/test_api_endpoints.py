"""Integration tests for FastAPI REST endpoints covering library, discovery and watches."""

import json
from pathlib import Path

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.backend.core.database import get_session
from src.backend.main import app

# Shared in-memory database across sessions using StaticPool
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
def setup_db():
    app.dependency_overrides[get_session] = override_get_session


@pytest.fixture
def fixtures():
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    tmdb = json.loads((fixtures_dir / "tmdb_show.json").read_text(encoding="utf-8"))
    tvmaze = json.loads((fixtures_dir / "tvmaze_show.json").read_text(encoding="utf-8"))
    eztv = json.loads((fixtures_dir / "eztv_torrents.json").read_text(encoding="utf-8"))
    return tmdb, tvmaze, eztv


def test_root_and_health_endpoints():
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["app"] == "TV Pirata 🏴‍☠️"

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"


def test_frontend_spa_serving():
    """Verify that browser requests receive compiled SPA index.html and assets."""
    res_html = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers.get("content-type", "")
    assert "TV Pirata" in res_html.text

    res_app = client.get("/app")
    assert res_app.status_code == 200
    assert "text/html" in res_app.headers.get("content-type", "")


def test_favicon_endpoints():
    res_ico = client.get("/favicon.ico")
    assert res_ico.status_code == 200
    assert len(res_ico.content) > 0

    res_svg = client.get("/favicon.svg")
    assert res_svg.status_code == 200
    assert "svg" in res_svg.headers.get("content-type", "")


def test_discovery_endpoints_with_mocked_network(fixtures):
    tmdb_data, _, _ = fixtures

    with respx.mock(base_url="https://api.themoviedb.org/3") as respx_mock:
        respx_mock.get("/trending/tv/week").respond(200, json={"results": [tmdb_data]})
        respx_mock.get("/search/tv").respond(200, json={"results": [tmdb_data]})

        # Trending
        res_trend = client.get("/api/discovery/trending")
        assert res_trend.status_code == 200
        assert len(res_trend.json()) == 1
        assert res_trend.json()[0]["title"] == "Game of Thrones"

        # Search
        res_search = client.get("/api/discovery/search?q=Thrones")
        assert res_search.status_code == 200
        assert res_search.json()[0]["title"] == "Game of Thrones"


def test_library_crud_and_watches_flow(fixtures):
    tmdb_data, _, _ = fixtures

    # 1. Import show into library
    import_payload = {
        "show": {
            "id": 1399,
            "title": "Game of Thrones",
            "overview": "Westeros epic fantasy",
            "rating": 8.4,
            "genres": ["Drama", "Fantasy"],
            "seasons": [
                {
                    "season_number": 1,
                    "name": "Season 1",
                    "episode_count": 2,
                    "episodes": [
                        {"episode_number": 1, "season_number": 1, "title": "Winter Is Coming"},
                        {"episode_number": 2, "season_number": 1, "title": "The Kingsroad"},
                    ],
                }
            ],
        },
        "user_status": "watching",
    }

    res_import = client.post("/api/library/shows", json=import_payload)
    assert res_import.status_code == 200
    show_id = res_import.json()["id"]
    assert show_id is not None

    # 2. List library shows
    res_list = client.get("/api/library/shows")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 3. Check progress (0% initially)
    res_prog = client.get(f"/api/watches/shows/{show_id}/progress")
    assert res_prog.status_code == 200
    assert res_prog.json()["progress_pct"] == 0.0

    # 4. Toggle episode 1
    res_toggle = client.post("/api/watches/episodes/1/toggle")
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_watched"] is True

    # 5. Check progress after 1 episode watched (50%)
    res_prog2 = client.get(f"/api/watches/shows/{show_id}/progress")
    assert res_prog2.json()["progress_pct"] == 50.0

    # 6. Update user status
    res_status = client.patch(
        f"/api/library/shows/{show_id}/status",
        json={"user_status": "completed"},
    )
    assert res_status.status_code == 200
    assert res_status.json()["user_status"] == "completed"


def test_torrents_endpoint(fixtures):
    _, _, eztv_data = fixtures

    with respx.mock(base_url="https://eztvx.to/api") as respx_mock:
        respx_mock.get("/get-torrents").respond(200, json=eztv_data)

        res_torrents = client.get("/api/torrents/shows/tt0944947")
        assert res_torrents.status_code == 200
        torrents = res_torrents.json()
        assert len(torrents) == 2
        assert torrents[0]["seeds"] == 150
        assert "magnet:" in torrents[0]["magnet_url"]


def test_collections_and_tags_endpoints():
    # Create tag
    res_tag = client.post("/api/collections/tags", json={"name": "Maratona", "color": "#ff0000"})
    assert res_tag.status_code == 200
    assert res_tag.json()["name"] == "Maratona"

    # List tags
    res_tags = client.get("/api/collections/tags")
    assert res_tags.status_code == 200
    assert any(t["name"] == "Maratona" for t in res_tags.json())

    # Create Smart Collection
    col_payload = {
        "name": "Completas",
        "description": "Séries finalizadas",
        "filter_criteria": {"user_status": "completed"},
    }
    res_col = client.post("/api/collections/smart", json=col_payload)
    assert res_col.status_code == 200
    col_id = res_col.json()["id"]

    # Query Smart Collection
    res_items = client.get(f"/api/collections/smart/{col_id}/items")
    assert res_items.status_code == 200
    assert len(res_items.json()) >= 1
    assert res_items.json()[0]["user_status"] == "completed"
