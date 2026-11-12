"""Domain and database models for TV Pirata."""

from src.backend.models.db import (
    CollectionRecord,
    EpisodeRecord,
    EpisodeWatchRecord,
    LocalMediaRecord,
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
    "CollectionRecord",
    "EpisodeRecord",
    "EpisodeWatchRecord",
    "LocalMediaRecord",
    "SeasonRecord",
    "ShowRecord",
    "ShowTagLink",
    "TagRecord",
    "TorrentRelease",
    "UnifiedEpisode",
    "UnifiedSeason",
    "UnifiedShow",
]
