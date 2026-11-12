"""EZTV public torrent distribution provider implementation."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.backend.models.unified import TorrentRelease

logger = logging.getLogger(__name__)


class EZTVProvider:
    """Client for EZTV public torrent metadata API."""

    def __init__(
        self,
        base_url: str = "https://eztvx.to/api",
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    def _sanitize_imdb_id(self, imdb_id: str) -> str:
        """Strip 'tt' prefix if present since EZTV expects numeric IMDB ID."""
        return imdb_id.strip().lower().lstrip("tt")

    async def get_torrents_by_imdb(
        self, imdb_id: str, limit: int = 50, page: int = 1
    ) -> list[TorrentRelease]:
        """Fetch available torrent releases for a given IMDB ID."""
        clean_id = self._sanitize_imdb_id(imdb_id)
        if not clean_id:
            return []

        url = f"{self.base_url}/get-torrents"
        params = {"imdb_id": clean_id, "limit": limit, "page": page}
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            raw_torrents = data.get("torrents", [])
            releases = [TorrentRelease.from_eztv(t) for t in raw_torrents]
            # Order by seeds descending for highest quality/health
            releases.sort(key=lambda r: r.seeds, reverse=True)
            return releases
        except Exception as exc:
            logger.warning("Failed to fetch torrents from EZTV for imdb_id=%s: %s", imdb_id, exc)
            return []
        finally:
            if should_close:
                await client.aclose()
