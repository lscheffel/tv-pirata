"""API endpoints for managing the user's personal media library."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from src.backend.core.database import get_session
from src.backend.models.db import ShowRecord
from src.backend.models.unified import UnifiedShow
from src.backend.repositories.library import LibraryRepository

router = APIRouter(prefix="/library", tags=["Personal Library"])


class ImportShowRequest(BaseModel):
    show: UnifiedShow
    user_status: str = "plan_to_watch"


class UpdateStatusRequest(BaseModel):
    user_status: str


@router.get("/shows", response_model=list[ShowRecord])
def list_library_shows(
    status: Optional[str] = Query(None, description="Filter by user status"),
    session: Session = Depends(get_session),
) -> list[ShowRecord]:
    """List shows currently saved in personal library."""
    repo = LibraryRepository(session)
    return repo.list_shows(user_status=status)


@router.post("/shows", response_model=ShowRecord)
def add_show_to_library(
    payload: ImportShowRequest,
    session: Session = Depends(get_session),
) -> ShowRecord:
    """Save a discovered show and its seasons/episodes into the personal database."""
    repo = LibraryRepository(session)
    return repo.upsert_from_unified(payload.show, user_status=payload.user_status)


@router.get("/shows/{show_id}", response_model=ShowRecord)
def get_library_show(
    show_id: int,
    session: Session = Depends(get_session),
) -> ShowRecord:
    """Retrieve show details from personal library."""
    repo = LibraryRepository(session)
    show = repo.get_show_by_id(show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found in library.")
    return show


@router.patch("/shows/{show_id}/status", response_model=ShowRecord)
def update_show_status(
    show_id: int,
    payload: UpdateStatusRequest,
    session: Session = Depends(get_session),
) -> ShowRecord:
    """Update viewing status (plan_to_watch, watching, completed, dropped, on_hold)."""
    repo = LibraryRepository(session)
    show = repo.update_show_status(show_id, payload.user_status)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found in library.")
    return show


@router.delete("/shows/{show_id}")
def delete_show(
    show_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """Remove a show and all associated records from personal library."""
    repo = LibraryRepository(session)
    success = repo.delete_show(show_id)
    if not success:
        raise HTTPException(status_code=404, detail="Show not found in library.")
    return {"message": "Show deleted successfully", "show_id": show_id}
