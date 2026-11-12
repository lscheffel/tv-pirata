"""Domain and database models for TV Pirata."""

from src.backend.models.db import (
    CatalogRelease,
    CatalogShow,
    CollectionRecord,
    EpisodeRecord,
    EpisodeWatchRecord,
    LocalMediaRecord,
    ReleaseNotificationRecord,
    SeasonRecord,
    ShowRecord,
    ShowTagLink,
    TagRecord,
)
from src.backend.models.unified import (
    TorrentRelease,
    UnifiedEpisode,
    UnifiedSeason,
    UnifiedShow,
)

__all__ = [
    "CatalogRelease",
    "CatalogShow",
    "CollectionRecord",
    "EpisodeRecord",
    "EpisodeWatchRecord",
    "LocalMediaRecord",
    "ReleaseNotificationRecord",
    "SeasonRecord",
    "ShowRecord",
    "ShowTagLink",
    "TagRecord",
    "TorrentRelease",
    "UnifiedEpisode",
    "UnifiedSeason",
    "UnifiedShow",
]
