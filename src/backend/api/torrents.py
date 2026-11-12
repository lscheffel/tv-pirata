"""API endpoints for torrent discovery and magnet links via EZTV."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.backend.models.unified import TorrentRelease
from src.backend.providers.eztv import EZTVProvider

router = APIRouter(prefix="/torrents", tags=["Torrent Distribution"])


@router.get("/shows/{imdb_id}", response_model=list[TorrentRelease])
async def get_show_torrents(
    imdb_id: str,
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
) -> list[TorrentRelease]:
    """Fetch available torrent releases from EZTV using IMDB ID."""
    provider = EZTVProvider()
    return await provider.get_torrents_by_imdb(imdb_id=imdb_id, limit=limit, page=page)
