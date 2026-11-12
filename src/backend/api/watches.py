"""API endpoints for tracking watched episodes and calculation of progress."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from src.backend.core.database import get_session
from src.backend.models.db import EpisodeWatchRecord
from src.backend.repositories.library import LibraryRepository

router = APIRouter(prefix="/watches", tags=["Watch History"])


class ToggleWatchRequest(BaseModel):
    is_watched: Optional[bool] = None


class WatchSeasonRequest(BaseModel):
    is_watched: bool = True


@router.post("/episodes/{episode_id}/toggle", response_model=EpisodeWatchRecord)
def toggle_episode(
    episode_id: int,
    payload: Optional[ToggleWatchRequest] = None,
    session: Session = Depends(get_session),
) -> EpisodeWatchRecord:
    """Toggle or explicitly set an episode's watched status."""
    repo = LibraryRepository(session)
    force_state = payload.is_watched if payload else None
    return repo.toggle_episode_watch(episode_id, force_state=force_state)


@router.post("/seasons/{season_id}/watch-all")
def watch_entire_season(
    season_id: int,
    payload: Optional[WatchSeasonRequest] = None,
    session: Session = Depends(get_session),
) -> dict:
    """Mark all episodes in a season as watched or unwatched."""
    repo = LibraryRepository(session)
    is_watched = payload.is_watched if payload else True
    count = repo.watch_all_in_season(season_id, is_watched=is_watched)
    return {
        "season_id": season_id,
        "is_watched": is_watched,
        "updated_episodes": count,
    }


@router.get("/shows/{show_id}/progress")
def get_progress(
    show_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """Calculate aggregated progress percentage and watched counts for a show."""
    repo = LibraryRepository(session)
    return repo.get_show_progress(show_id)
