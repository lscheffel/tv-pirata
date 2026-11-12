"""Repository managing release notification events."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from src.backend.models.db import ReleaseNotificationRecord


class NotificationRepository:
    """Data access layer for release notifications."""

    @staticmethod
    def list_notifications(
        session: Session,
        unread_only: bool = False,
        include_dismissed: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReleaseNotificationRecord]:
        """List notification events ordered by creation date descending."""
        query = select(ReleaseNotificationRecord)

        if not include_dismissed:
            query = query.where(ReleaseNotificationRecord.is_dismissed.is_(False))

        if unread_only:
            query = query.where(ReleaseNotificationRecord.is_read.is_(False))

        query = (
            query.order_by(col(ReleaseNotificationRecord.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        return list(session.exec(query).all())

    @staticmethod
    def get_unread_count(session: Session) -> int:
        """Count active unread and non-dismissed notifications."""
        query = select(func.count(ReleaseNotificationRecord.id)).where(
            ReleaseNotificationRecord.is_read.is_(False),
            ReleaseNotificationRecord.is_dismissed.is_(False),
        )
        return session.exec(query).one()

    @staticmethod
    def mark_as_read(session: Session, notification_id: int) -> Optional[ReleaseNotificationRecord]:
        """Mark a specific notification as read."""
        record = session.get(ReleaseNotificationRecord, notification_id)
        if not record:
            return None
        record.is_read = True
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def dismiss_all(session: Session) -> int:
        """Dismiss all notifications for the user."""
        query = select(ReleaseNotificationRecord).where(
            ReleaseNotificationRecord.is_dismissed.is_(False)
        )
        records = session.exec(query).all()
        count = len(records)
        for r in records:
            r.is_dismissed = True
            r.is_read = True
            session.add(r)
        session.commit()
        return count

    @staticmethod
    def create_notification(
        session: Session,
        show_id: int,
        imdb_id: str,
        show_title: str,
        season: int,
        episode: int,
        release_title: str,
        quality: str = "Unknown",
        seeds: int = 0,
        magnet_url: str = "",
    ) -> Optional[ReleaseNotificationRecord]:
        """Atomically create a notification ensuring idempotency."""
        # 1. Quick check for existing record
        existing = session.exec(
            select(ReleaseNotificationRecord).where(
                ReleaseNotificationRecord.show_id == show_id,
                ReleaseNotificationRecord.season == season,
                ReleaseNotificationRecord.episode == episode,
            )
        ).first()
        if existing:
            return None

        # 2. Insert with IntegrityError protection
        record = ReleaseNotificationRecord(
            show_id=show_id,
            imdb_id=imdb_id,
            show_title=show_title,
            season=season,
            episode=episode,
            release_title=release_title,
            quality=quality,
            seeds=seeds,
            magnet_url=magnet_url,
            is_read=False,
            is_dismissed=False,
        )
        try:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        except IntegrityError:
            session.rollback()
            return None
