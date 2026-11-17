"""API endpoints for torrent discovery and magnet links via EZTV."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from src.backend.core.database import get_eztv_session, get_session
from src.backend.models.unified import TorrentRelease
from src.backend.providers.eztv import EZTVProvider
from src.backend.repositories.catalog import CatalogRepository

router = APIRouter(prefix="/torrents", tags=["Torrent Distribution"])


@router.get("/shows/{imdb_id}", response_model=list[TorrentRelease])
async def get_show_torrents(
    imdb_id: str,
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    sources_session: Session = Depends(get_eztv_session),
    session: Session = Depends(get_session),
) -> list[TorrentRelease]:
    """Fetch available torrent releases from EZTV using IMDB ID with local DB fallback."""
    provider = EZTVProvider()
    releases = await provider.get_torrents_by_imdb(imdb_id=imdb_id, limit=limit, page=page)
    if releases:
        return releases

    # Fallback to local catalog releases (preferring sources.db, with legacy fallback)
    db_releases = []
    try:
        db_releases = CatalogRepository.get_show_releases(sources_session, imdb_id)
    except Exception:
        db_releases = []
    if not db_releases:
        db_releases = CatalogRepository.get_show_releases(session, imdb_id)
    if db_releases:
        return [
            TorrentRelease(
                id=r.eztv_id,
                hash=r.hash,
                filename=r.filename,
                title=r.title,
                season=r.season,
                episode=r.episode,
                magnet_url=r.magnet_url,
                torrent_url=r.torrent_url,
                seeds=r.seeds,
                peers=r.peers,
                size_bytes=r.size_bytes,
                quality=r.quality,
            )
            for r in db_releases[:limit]
        ]

    return []
