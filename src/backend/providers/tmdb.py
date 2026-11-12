"""The Movie Database (TMDB) metadata provider implementation."""

from __future__ import annotations

from typing import Optional

import httpx

from src.backend.models.unified import UnifiedSeason, UnifiedShow
from src.backend.providers.base import BaseMetadataProvider


class TMDBProvider(BaseMetadataProvider):
    """Client for The Movie Database API v3."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.themoviedb.org/3",
        language: str = "pt-BR",
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.language = language
        self._client = client
        self.image_base_url = "https://image.tmdb.org/t/p"

    @property
    def provider_name(self) -> str:
        return "tmdb"

    def _get_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if len(self.api_key) > 50:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_params(self, extra: Optional[dict] = None) -> dict:
        params = {"language": self.language}
        if len(self.api_key) <= 50 and self.api_key:
            params["api_key"] = self.api_key
        if extra:
            params.update(extra)
        return params

    def _format_image_url(self, path: Optional[str], size: str = "w500") -> Optional[str]:
        if not path:
            return None
        return f"{self.image_base_url}/{size}{path}"

    def _map_show(self, data: dict) -> UnifiedShow:
        external_ids = data.get("external_ids", {})
        imdb_id = external_ids.get("imdb_id") if isinstance(external_ids, dict) else None

        genres = []
        for g in data.get("genres", []):
            if isinstance(g, dict) and "name" in g:
                genres.append(g["name"])
            elif isinstance(g, str):
                genres.append(g)

        seasons = []
        for s in data.get("seasons", []):
            if isinstance(s, dict):
                seasons.append(
                    UnifiedSeason(
                        id=s.get("id"),
                        season_number=s.get("season_number", 0),
                        name=s.get("name", ""),
                        overview=s.get("overview", ""),
                        poster_url=self._format_image_url(s.get("poster_path")),
                        episode_count=s.get("episode_count", 0),
                    )
                )

        return UnifiedShow(
            id=data["id"],
            tmdb_id=data["id"],
            imdb_id=imdb_id,
            title=data.get("name") or data.get("title") or "Sem Título",
            original_title=data.get("original_name") or data.get("original_title"),
            overview=data.get("overview", ""),
            poster_url=self._format_image_url(data.get("poster_path")),
            backdrop_url=self._format_image_url(data.get("backdrop_path"), size="original"),
            rating=float(data.get("vote_average", 0.0)),
            genres=genres,
            first_air_date=data.get("first_air_date"),
            status=data.get("status"),
            source_provider="tmdb",
            seasons=seasons,
        )

    async def search_shows(self, query: str) -> list[UnifiedShow]:
        url = f"{self.base_url}/search/tv"
        params = self._get_params({"query": query})
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            payload = response.json()
            return [self._map_show(item) for item in payload.get("results", [])]
        finally:
            if should_close:
                await client.aclose()

    async def get_show_details(self, show_id: int) -> UnifiedShow:
        url = f"{self.base_url}/tv/{show_id}"
        params = self._get_params({"append_to_response": "external_ids"})
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            return self._map_show(response.json())
        finally:
            if should_close:
                await client.aclose()

    async def get_trending(self) -> list[UnifiedShow]:
        url = f"{self.base_url}/trending/tv/week"
        params = self._get_params()
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            payload = response.json()
            return [self._map_show(item) for item in payload.get("results", [])]
        finally:
            if should_close:
                await client.aclose()
