"""FastAPI router for release notifications and scheduler telemetry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from src.backend.core.database import get_session
from src.backend.models.db import ReleaseNotificationRecord
from src.backend.repositories.notification import NotificationRepository
from src.backend.services.scheduler import scheduler

router = APIRouter(prefix="/notifications", tags=["Release Notifications"])


class UnreadCountResponse(BaseModel):
    unread_count: int


class DismissResponse(BaseModel):
    status: str
    dismissed_count: int


@router.get("", response_model=list[ReleaseNotificationRecord])
def list_notifications(
    unread_only: bool = Query(False, description="Filtrar apenas alertas não lidos"),
    include_dismissed: bool = Query(False, description="Incluir alertas já dispensados"),
    limit: int = Query(50, ge=1, le=200, description="Quantidade de registros"),
    offset: int = Query(0, ge=0, description="Deslocamento para paginação"),
    session: Session = Depends(get_session),
):
    """List release notification events for shows in user's library."""
    return NotificationRepository.list_notifications(
        session=session,
        unread_only=unread_only,
        include_dismissed=include_dismissed,
        limit=limit,
        offset=offset,
    )


@router.get("/count", response_model=UnreadCountResponse)
def get_unread_count(session: Session = Depends(get_session)):
    """Get active count of unread notifications for badge rendering."""
    count = NotificationRepository.get_unread_count(session=session)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=ReleaseNotificationRecord)
def mark_notification_as_read(
    notification_id: int,
    session: Session = Depends(get_session),
):
    """Mark a specific notification as read."""
    record = NotificationRepository.mark_as_read(session=session, notification_id=notification_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Notificação {notification_id} não encontrada."
        )
    return record


@router.post("/dismiss-all", response_model=DismissResponse)
def dismiss_all_notifications(session: Session = Depends(get_session)):
    """Dismiss all active notifications."""
    dismissed = NotificationRepository.dismiss_all(session=session)
    return DismissResponse(status="success", dismissed_count=dismissed)


@router.get("/scheduler-status")
def get_scheduler_status():
    """Get operational status and telemetry of the background auto-sync worker."""
    return scheduler.get_telemetry()


@router.post("/trigger-sync")
async def trigger_manual_scheduler_cycle():
    """Trigger an immediate background synchronization and notification cycle."""
    telemetry = await scheduler.execute_cycle()
    return {"status": "success", "telemetry": telemetry}
