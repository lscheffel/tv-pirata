"""TVMaze open metadata provider implementation."""

from __future__ import annotations

from typing import Optional

import httpx

from src.backend.models.unified import UnifiedSeason, UnifiedShow
from src.backend.providers.base import BaseMetadataProvider


class TVMazeProvider(BaseMetadataProvider):
    """Client for the public TVMaze REST API."""

    def __init__(
        self,
        base_url: str = "https://api.tvmaze.com",
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    @property
    def provider_name(self) -> str:
        return "tvmaze"

    def _map_show(self, data: dict) -> UnifiedShow:
        externals = data.get("externals") or {}
        imdb_id = externals.get("imdb")

        # Ratings in TVMaze come as {"average": 8.9}
        rating_obj = data.get("rating") or {}
        rating = float(rating_obj.get("average") or 0.0)

        images = data.get("image") or {}
        poster_url = images.get("original") or images.get("medium")

        # Embedded seasons
        seasons = []
        embedded = data.get("_embedded") or {}
        for s in embedded.get("seasons", []):
            seasons.append(
                UnifiedSeason(
                    id=s.get("id"),
                    season_number=s.get("number", 0),
                    name=s.get("name") or f"Temporada {s.get('number', 0)}",
                    overview=UnifiedShow.clean_html(s.get("summary", "")),
                    episode_count=s.get("episodeOrder") or 0,
                )
            )

        return UnifiedShow(
            id=data["id"],
            tvmaze_id=data["id"],
            imdb_id=imdb_id,
            title=data.get("name") or "Sem Título",
            overview=UnifiedShow.clean_html(data.get("summary", "")),
            poster_url=poster_url,
            rating=rating,
            genres=data.get("genres", []),
            first_air_date=data.get("premiered"),
            status=data.get("status"),
            source_provider="tvmaze",
            seasons=seasons,
        )

    async def search_shows(self, query: str) -> list[UnifiedShow]:
        url = f"{self.base_url}/search/shows"
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params={"q": query})
            response.raise_for_status()
            payload = response.json()
            return [self._map_show(item["show"]) for item in payload if "show" in item]
        finally:
            if should_close:
                await client.aclose()

    async def get_show_details(self, show_id: int) -> UnifiedShow:
        url = f"{self.base_url}/shows/{show_id}"
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params={"embed": "seasons"})
            response.raise_for_status()
            return self._map_show(response.json())
        finally:
            if should_close:
                await client.aclose()

    async def get_trending(self) -> list[UnifiedShow]:
        url = f"{self.base_url}/shows"
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params={"page": 0})
            response.raise_for_status()
            payload = response.json()
            # Return top 20 shows
            return [self._map_show(item) for item in payload[:20]]
        finally:
            if should_close:
                await client.aclose()

    async def lookup_by_imdb(self, imdb_id: str) -> Optional[UnifiedShow]:
        """Lookup show details using canonical IMDB ID (e.g. tt0944947)."""
        clean_id = imdb_id.strip().lower()
        if not clean_id.startswith("tt"):
            clean_id = f"tt{clean_id}"

        url = f"{self.base_url}/lookup/shows"
        client = self._client or httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        should_close = self._client is None
        try:
            response = await client.get(url, params={"imdb": clean_id})
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._map_show(response.json())
        except Exception:
            return None
        finally:
            if should_close:
                await client.aclose()
