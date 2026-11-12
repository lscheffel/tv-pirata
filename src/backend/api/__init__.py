"""API routers for TV Pirata."""

from src.backend.api.catalog import router as catalog_router
from src.backend.api.collections import router as collections_router
from src.backend.api.discovery import router as discovery_router
from src.backend.api.library import router as library_router
from src.backend.api.notifications import router as notifications_router
from src.backend.api.torrents import router as torrents_router
from src.backend.api.watches import router as watches_router

__all__ = [
    "catalog_router",
    "collections_router",
    "discovery_router",
    "library_router",
    "notifications_router",
    "torrents_router",
    "watches_router",
]
