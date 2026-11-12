"""Unit tests for TMDBProvider using deterministic respx fixtures."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from src.backend.providers.tmdb import TMDBProvider


@pytest.fixture
def tmdb_fixture() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "tmdb_show.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_tmdb_get_show_details_success(tmdb_fixture):
    provider = TMDBProvider(api_key="test_key_123")

    with respx.mock(base_url="https://api.themoviedb.org/3") as respx_mock:
        respx_mock.get("/tv/1399").respond(200, json=tmdb_fixture)

        show = await provider.get_show_details(1399)

        assert show.id == 1399
        assert show.tmdb_id == 1399
        assert show.imdb_id == "tt0944947"
        assert show.title == "Game of Thrones"
        assert show.rating == 8.442
        assert "Sci-Fi & Fantasy" in show.genres
        assert len(show.seasons) == 1
        assert show.seasons[0].season_number == 1
        assert "https://image.tmdb.org/t/p/w500" in (show.poster_url or "")


@pytest.mark.asyncio
async def test_tmdb_search_shows_success(tmdb_fixture):
    provider = TMDBProvider(api_key="test_key_123")

    with respx.mock(base_url="https://api.themoviedb.org/3") as respx_mock:
        respx_mock.get("/search/tv").respond(200, json={"results": [tmdb_fixture]})

        results = await provider.search_shows("Game of Thrones")

        assert len(results) == 1
        assert results[0].title == "Game of Thrones"


@pytest.mark.asyncio
async def test_tmdb_http_error():
    provider = TMDBProvider(api_key="test_key_123")

    with respx.mock(base_url="https://api.themoviedb.org/3") as respx_mock:
        respx_mock.get("/tv/9999").respond(404, json={"status_message": "Not Found"})

        with pytest.raises(httpx.HTTPStatusError):
            await provider.get_show_details(9999)

