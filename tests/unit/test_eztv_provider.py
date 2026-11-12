"""Unit tests for EZTVProvider using deterministic respx fixtures."""

import json
from pathlib import Path

import pytest
import respx

from src.backend.providers.eztv import EZTVProvider


@pytest.fixture
def eztv_fixture() -> dict:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "eztv_torrents.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_eztv_get_torrents_by_imdb_success(eztv_fixture):
    provider = EZTVProvider()

    with respx.mock(base_url="https://eztvx.to/api") as respx_mock:
        respx_mock.get("/get-torrents").respond(200, json=eztv_fixture)

        # Calling with 'tt0944947' should sanitize to '0944947'
        torrents = await provider.get_torrents_by_imdb("tt0944947")

        assert len(torrents) == 2
        # Torrents ordered by seeds descending: 150 > 85
        assert torrents[0].seeds == 150
        assert torrents[0].quality == "1080p"
        assert "magnet:?xt=urn:btih:abcdef" in torrents[0].magnet_url
        assert torrents[1].seeds == 85
        assert torrents[1].quality == "720p"


@pytest.mark.asyncio
async def test_eztv_handles_network_failure():
    provider = EZTVProvider()

    with respx.mock(base_url="https://eztvx.to/api") as respx_mock:
        respx_mock.get("/get-torrents").respond(500)

        torrents = await provider.get_torrents_by_imdb("tt9999999")
        # Should gracefully return empty list on failure
        assert torrents == []
