"""Unit tests for BackgroundSyncService and cooperative cancellation."""

from unittest.mock import AsyncMock, patch

import pytest

from src.backend.services.scheduler import BackgroundSyncService


@pytest.mark.asyncio
async def test_scheduler_disabled_flag():
    service = BackgroundSyncService(enabled=False)
    assert not service.enabled
    task = service.start()
    assert task is None
    assert service.status == "DISABLED"


@pytest.mark.asyncio
async def test_scheduler_start_and_stop_cleanly():
    service = BackgroundSyncService(interval_seconds=10.0, enabled=True)
    task = service.start()
    assert task is not None
    assert service.is_running
    assert not task.done()

    # Gracefully stop within 1 second
    await service.stop(timeout=1.0)
    assert not service.is_running
    assert task.done()
    assert service.status == "DISABLED"


@pytest.mark.asyncio
async def test_scheduler_execute_cycle_mocked():
    service = BackgroundSyncService(interval_seconds=60.0, enabled=True)

    fake_telemetry = {
        "releases_inspected": 100,
        "notifications_created": 3,
        "torrents_indexed": 15,
    }

    with patch.object(
        service._indexer, "sync_and_reconcile_recent", new=AsyncMock(return_value=fake_telemetry)
    ):
        result = await service.execute_cycle()
        assert result["releases_inspected"] == 100
        assert result["notifications_created"] == 3
        assert service.last_releases_found == 100
        assert service.last_notifications_created == 3
        assert service.last_run_at is not None
        assert service.status == "IDLE"

        telemetry = service.get_telemetry()
        assert telemetry["status"] == "IDLE"
        assert telemetry["last_releases_found"] == 100
        assert telemetry["last_notifications_created"] == 3
