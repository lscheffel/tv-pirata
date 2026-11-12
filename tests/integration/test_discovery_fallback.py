"""Integration tests for ResilientDiscoveryService verifying TMDB -> TVMaze fallback."""

import asyncio
import json
from pathlib import Path

import pytest
import respx

from src.backend.providers.discovery_service import ResilientDiscoveryService
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider


@pytest.fixture
def fixtures() -> tuple[dict, dict]:
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    tmdb = json.loads((fixtures_dir / "tmdb_show.json").read_text(encoding="utf-8"))
    tvmaze = json.loads((fixtures_dir / "tvmaze_show.json").read_text(encoding="utf-8"))
    return tmdb, tvmaze


@pytest.mark.asyncio
async def test_fallback_when_tmdb_times_out(fixtures):
    _, tvmaze_data = fixtures

    tmdb = TMDBProvider(api_key="mock_key")
    tvmaze = TVMazeProvider()
    service = ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=0.1)

    async def slow_tmdb_response(request):
        await asyncio.sleep(0.3)
        return respx.MockResponse(200, json={"results": []})

    with respx.mock(assert_all_called=False) as respx_mock:
        # TMDB times out
        respx_mock.get("https://api.themoviedb.org/3/search/tv").mock(side_effect=slow_tmdb_response)
        # TVMaze responds successfully
        respx_mock.get("https://api.tvmaze.com/search/shows").respond(
            200, json=[{"score": 10.0, "show": tvmaze_data}]
        )

        results = await service.search_shows("Game of Thrones")

        assert len(results) == 1
        assert results[0].source_provider == "tvmaze"
        assert results[0].title == "Game of Thrones"


@pytest.mark.asyncio
async def test_fallback_when_tmdb_returns_http_500(fixtures):
    _, tvmaze_data = fixtures

    tmdb = TMDBProvider(api_key="mock_key")
    tvmaze = TVMazeProvider()
    service = ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=2.0)

    with respx.mock(assert_all_called=False) as respx_mock:
        # TMDB returns 500 Internal Server Error
        respx_mock.get("https://api.themoviedb.org/3/search/tv").respond(500)
        # TVMaze succeeds
        respx_mock.get("https://api.tvmaze.com/search/shows").respond(
            200, json=[{"score": 10.0, "show": tvmaze_data}]
        )

        results = await service.search_shows("Game of Thrones")

        assert len(results) == 1
        assert results[0].source_provider == "tvmaze"
        assert results[0].title == "Game of Thrones"


@pytest.mark.asyncio
async def test_primary_tmdb_success_avoids_fallback(fixtures):
    tmdb_data, _ = fixtures

    tmdb = TMDBProvider(api_key="mock_key")
    tvmaze = TVMazeProvider()
    service = ResilientDiscoveryService(primary=tmdb, fallback=tvmaze, timeout_seconds=2.0)

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://api.themoviedb.org/3/search/tv").respond(
            200, json={"results": [tmdb_data]}
        )
        tvmaze_route = respx_mock.get("https://api.tvmaze.com/search/shows").respond(200, json=[])

        results = await service.search_shows("Game of Thrones")

        assert len(results) == 1
        assert results[0].source_provider == "tmdb"
        assert results[0].title == "Game of Thrones"
        # Ensure fallback route was NOT called
        assert not tvmaze_route.called

