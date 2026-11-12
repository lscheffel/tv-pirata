"""API endpoints for tags and smart collections."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from src.backend.core.database import get_session
from src.backend.models.db import CollectionRecord, ShowRecord, TagRecord
from src.backend.repositories.library import LibraryRepository

router = APIRouter(prefix="/collections", tags=["Collections & Tags"])


class CreateTagRequest(BaseModel):
    name: str
    color: str = "#e50914"


class CreateCollectionRequest(BaseModel):
    name: str
    description: str = ""
    filter_criteria: Optional[dict] = None


@router.get("/tags", response_model=list[TagRecord])
def list_tags(session: Session = Depends(get_session)) -> list[TagRecord]:
    """List all user-defined classification tags."""
    repo = LibraryRepository(session)
    return repo.list_tags()


@router.post("/tags", response_model=TagRecord)
def create_tag(
    payload: CreateTagRequest,
    session: Session = Depends(get_session),
) -> TagRecord:
    """Create a new tag."""
    repo = LibraryRepository(session)
    return repo.create_tag(name=payload.name, color=payload.color)


@router.get("/smart", response_model=list[CollectionRecord])
def list_smart_collections(session: Session = Depends(get_session)) -> list[CollectionRecord]:
    """List all saved smart collections."""
    repo = LibraryRepository(session)
    return repo.list_collections()


@router.post("/smart", response_model=CollectionRecord)
def create_smart_collection(
    payload: CreateCollectionRequest,
    session: Session = Depends(get_session),
) -> CollectionRecord:
    """Create a new smart collection with JSON criteria."""
    repo = LibraryRepository(session)
    return repo.create_collection(
        name=payload.name,
        description=payload.description,
        filter_criteria=payload.filter_criteria,
    )


@router.get("/smart/{collection_id}/items", response_model=list[ShowRecord])
def query_smart_collection_items(
    collection_id: int,
    session: Session = Depends(get_session),
) -> list[ShowRecord]:
    """Execute dynamic query for a smart collection and return matching shows."""
    repo = LibraryRepository(session)
    shows = repo.query_smart_collection(collection_id)
    if shows is None:
        raise HTTPException(status_code=404, detail="Collection not found.")
    return shows
