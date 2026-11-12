"""Integration tests for /api/notifications REST endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, delete

from src.backend.core.database import get_session
from src.backend.main import app
from src.backend.models.db import ReleaseNotificationRecord, ShowRecord
from src.backend.repositories.notification import NotificationRepository

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)


def override_get_session():
    with Session(test_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_data():
    app.dependency_overrides[get_session] = override_get_session
    with Session(test_engine) as session:
        session.exec(delete(ReleaseNotificationRecord))
        session.exec(delete(ShowRecord))
        session.commit()

        show = ShowRecord(
            id=1,
            tmdb_id=1399,
            imdb_id="tt0944947",
            title="Game of Thrones",
        )
        session.add(show)
        session.commit()

        # Seed initial notification
        notif = ReleaseNotificationRecord(
            show_id=1,
            imdb_id="tt0944947",
            show_title="Game of Thrones",
            season=8,
            episode=6,
            release_title="Game.of.Thrones.S08E06.1080p.mkv",
            quality="1080p",
            seeds=250,
            magnet_url="magnet:?xt=urn:btih:fake",
            is_read=False,
            is_dismissed=False,
        )
        session.add(notif)
        session.commit()


def test_list_notifications():
    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["show_title"] == "Game of Thrones"
    assert data[0]["season"] == 8
    assert data[0]["episode"] == 6
    assert data[0]["is_read"] is False


def test_get_unread_count():
    res = client.get("/api/notifications/count")
    assert res.status_code == 200
    data = res.json()
    assert data["unread_count"] == 1


def test_mark_notification_as_read():
    res_list = client.get("/api/notifications")
    notif_id = res_list.json()[0]["id"]

    res_patch = client.patch(f"/api/notifications/{notif_id}/read")
    assert res_patch.status_code == 200
    assert res_patch.json()["is_read"] is True

    # Count should now be 0
    res_count = client.get("/api/notifications/count")
    assert res_count.json()["unread_count"] == 0


def test_dismiss_all_notifications():
    res = client.post("/api/notifications/dismiss-all")
    assert res.status_code == 200
    assert res.json()["dismissed_count"] == 1

    # Should not appear in active list by default
    res_list = client.get("/api/notifications")
    assert len(res_list.json()) == 0


def test_scheduler_status():
    res = client.get("/api/notifications/scheduler-status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "is_running" in data


def test_notification_repository_idempotency():
    with Session(test_engine) as session:
        # Attempt duplicate insertion for same (show_id, season, episode)
        dup = NotificationRepository.create_notification(
            session=session,
            show_id=1,
            imdb_id="tt0944947",
            show_title="Game of Thrones",
            season=8,
            episode=6,
            release_title="Another.Release.S08E06.mkv",
        )
        # Must return None due to duplicate prevention
        assert dup is None
