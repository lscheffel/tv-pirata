"""Unit tests for TVMazeProvider using deterministic respx fixtures."""

import json
from pathlib import Path

import pytest
import respx

from src.backend.providers.tvmaze import TVMazeProvider


@pytest.fixture
def tvmaze_fixture() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "tvmaze_show.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_tvmaze_get_show_details_success(tvmaze_fixture):
    provider = TVMazeProvider()

    with respx.mock(base_url="https://api.tvmaze.com") as respx_mock:
        respx_mock.get("/shows/82").respond(200, json=tvmaze_fixture)

        show = await provider.get_show_details(82)

        assert show.id == 82
        assert show.tvmaze_id == 82
        assert show.imdb_id == "tt0944947"
        assert show.title == "Game of Thrones"
        assert show.rating == 8.9
        assert show.source_provider == "tvmaze"
        # Verify HTML cleaning in overview
        assert "<p>" not in show.overview
        assert "Based on the bestselling book series" in show.overview
        assert len(show.seasons) == 1
        assert show.seasons[0].season_number == 1


@pytest.mark.asyncio
async def test_tvmaze_search_shows_success(tvmaze_fixture):
    provider = TVMazeProvider()

    with respx.mock(base_url="https://api.tvmaze.com") as respx_mock:
        respx_mock.get("/search/shows").respond(200, json=[{"score": 9.5, "show": tvmaze_fixture}])

        results = await provider.search_shows("Game of Thrones")

        assert len(results) == 1
        assert results[0].title == "Game of Thrones"

