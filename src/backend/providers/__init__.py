"""Metadata and distribution providers for TV Pirata."""

from src.backend.providers.base import BaseMetadataProvider
from src.backend.providers.discovery_service import ResilientDiscoveryService
from src.backend.providers.eztv import EZTVProvider
from src.backend.providers.tmdb import TMDBProvider
from src.backend.providers.tvmaze import TVMazeProvider

__all__ = [
    "BaseMetadataProvider",
    "EZTVProvider",
    "ResilientDiscoveryService",
    "TMDBProvider",
    "TVMazeProvider",
]

