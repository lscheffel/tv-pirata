"""EZTV public torrent distribution provider implementation (sources-apis.md spec)."""

from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from src.backend.models.unified import TorrentRelease

logger = logging.getLogger(__name__)


class EZTVProvider:
    """Client for EZTV public torrent metadata API (https://eztvx.to/api/get-torrents)."""

    def __init__(
        self,
        base_url: str = "https://eztvx.to/api",
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        cleaned = base_url.rstrip("/")
        if cleaned.endswith("/api/get-torrents"):
            cleaned = cleaned[: -len("/get-torrents")]
        elif not cleaned.endswith("/api"):
            cleaned = f"{cleaned}/api"
        self.base_url = cleaned
        self._client = client

    def _sanitize_imdb_id(self, imdb_id: str) -> str:
        """Strip 'tt' prefix and non-digits since EZTV expects numeric IMDB ID (e.g. 6048596)."""
        return re.sub(r"\D", "", (imdb_id or "").strip())

    async def get_torrents_by_imdb(
        self, imdb_id: str, limit: int = 100, page: int = 1
    ) -> list[TorrentRelease]:
        """Fetch available torrent releases for a given IMDB ID (limit 1..100, page 1..100)."""
        clean_id = self._sanitize_imdb_id(imdb_id)
        if not clean_id:
            return []

        safe_limit = max(1, min(int(limit or 100), 100))
        safe_page = max(1, min(int(page or 1), 100))
        url = f"{self.base_url}/get-torrents"
        params = {"imdb_id": clean_id, "limit": safe_limit, "page": safe_page}
        client = self._client or httpx.AsyncClient(timeout=10.0)

        should_close = self._client is None
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            raw_torrents = data.get("torrents", []) or []
            releases = [TorrentRelease.from_eztv(t) for t in raw_torrents]
            releases.sort(key=lambda r: r.seeds, reverse=True)
            return releases
        except Exception as exc:
            logger.warning("Failed to fetch torrents from EZTV for imdb_id=%s: %s", imdb_id, exc)
            return []
        finally:
            if should_close:
                await client.aclose()
