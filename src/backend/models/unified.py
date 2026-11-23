"""Canonical unified domain models for media discovery and management.

This module provides normalized Pydantic schemas that decouple the internal
business logic and API contracts from external provider payloads (TMDB, TVMaze).
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field


class TorrentRelease(BaseModel):
    """Represents a torrent release candidate from distribution networks."""

    id: int
    hash: str
    filename: str
    title: str
    season: int = 0
    episode: int = 0
    magnet_url: str
    torrent_url: Optional[str] = None
    seeds: int = 0
    peers: int = 0
    size_bytes: int = 0
    quality: str = "Unknown"

    @classmethod
    def from_eztv(cls, item: dict) -> TorrentRelease:
        """Parse an EZTV API response item into a standardized TorrentRelease."""
        title = item.get("title", "")
        filename = item.get("filename", "")
        raw_season = item.get("season", "0")
        raw_episode = item.get("episode", "0")

        # Normalize quality from filename or title
        quality = "Unknown"
        normalized_str = f"{title} {filename}".lower()
        if "2160p" in normalized_str or "4k" in normalized_str:
            quality = "4K / 2160p"
        elif "1080p" in normalized_str:
            quality = "1080p"
        elif "720p" in normalized_str:
            quality = "720p"
        elif "480p" in normalized_str or "hdtv" in normalized_str:
            quality = "SD"

        # Safely parse numeric season / episode
        try:
            season_num = int(raw_season)
        except (ValueError, TypeError):
            season_num = 0

        try:
            episode_num = int(raw_episode)
        except (ValueError, TypeError):
            episode_num = 0

        try:
            size_int = int(item.get("size_bytes", 0))
        except (ValueError, TypeError):
            size_int = 0

        return cls(
            id=int(item.get("id", 0)),
            hash=item.get("hash", ""),
            filename=filename,
            title=title,
            season=season_num,
            episode=episode_num,
            magnet_url=item.get("magnet_url", ""),
            torrent_url=item.get("torrent_url"),
            seeds=int(item.get("seeds", 0)),
            peers=int(item.get("peers", 0)),
            size_bytes=size_int,
            quality=quality,
        )


class UnifiedEpisode(BaseModel):
    """Normalized episode metadata."""

    id: Optional[int] = None
    episode_number: int
    season_number: int
    title: str
    overview: str = ""
    air_date: Optional[str] = None
    rating: Optional[float] = None
    is_watched: bool = False


class UnifiedSeason(BaseModel):
    """Normalized season metadata."""

    id: Optional[int] = None
    season_number: int
    name: str = ""
    overview: str = ""
    poster_url: Optional[str] = None
    episode_count: int = 0
    episodes: list[UnifiedEpisode] = Field(default_factory=list)


class UnifiedShow(BaseModel):
    """Canonical representation of a TV Show across all providers."""

    id: int
    tmdb_id: Optional[int] = None
    tvmaze_id: Optional[int] = None
    imdb_id: Optional[str] = None
    title: str
    original_title: Optional[str] = None
    overview: str = ""
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    rating: float = 0.0
    genres: list[str] = Field(default_factory=list)
    first_air_date: Optional[str] = None
    status: Optional[str] = None
    network: Optional[str] = None
    streaming_providers: list[str] = Field(default_factory=list)
    eztv_available: bool = False
    has_media: bool = False
    media_sources: list[str] = Field(default_factory=list)
    sources_count: int = 0
    source_provider: str = "tmdb"
    seasons: list[UnifiedSeason] = Field(default_factory=list)

    @staticmethod
    def clean_html(text: str) -> str:
        """Strip HTML tags from text payloads (e.g., TVMaze summaries)."""
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", "", text)
        return clean.strip()
