"""Background periodic sync and notification service."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from src.backend.core.database import engine, sources_engine
from src.backend.services.catalog_indexer import EZTVIndexerService

logger = logging.getLogger(__name__)


class BackgroundSyncService:
    """Manages cooperative in-process polling for library releases."""

    def __init__(
        self,
        interval_seconds: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        if interval_seconds is None:
            mins = float(os.getenv("AUTO_SYNC_INTERVAL_MINUTES", "60"))
            self.interval_seconds = mins * 60.0
        else:
            self.interval_seconds = interval_seconds

        if enabled is None:
            self.enabled = os.getenv("ENABLE_AUTO_SYNC", "true").lower() in ("true", "1", "yes")
        else:
            self.enabled = enabled

        self.is_running = False
        self.status = "IDLE" if self.enabled else "DISABLED"
        self.last_run_at: Optional[datetime] = None
        self.next_run_eta_seconds: Optional[int] = None
        self.last_releases_found: int = 0
        self.last_notifications_created: int = 0
        self.current_backoff_seconds = self.interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._indexer = EZTVIndexerService()

    def start(self) -> Optional[asyncio.Task]:
        """Start the background scheduler task if enabled."""
        if not self.enabled:
            logger.info("BackgroundSyncService is disabled via configuration.")
            self.status = "DISABLED"
            return None

        if self.is_running and self._task and not self._task.done():
            logger.warning("BackgroundSyncService is already running.")
            return self._task

        self.is_running = True
        self.status = "IDLE"
        self._task = asyncio.create_task(self._run_loop(), name="tv-pirata-scheduler")
        logger.info(
            "BackgroundSyncService started with interval=%.1fs (task=%s)",
            self.interval_seconds,
            self._task.get_name(),
        )
        return self._task

    async def stop(self, timeout: float = 3.0) -> None:
        """Cooperatively terminate background task ensuring zero orphaned tasks."""
        self.is_running = False
        self.status = "DISABLED"

        if self._task and not self._task.done():
            logger.info("Stopping BackgroundSyncService (task=%s)...", self._task.get_name())
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            finally:
                logger.info("BackgroundSyncService stopped cleanly.")

    async def execute_cycle(self) -> dict:
        """Execute a single atomic synchronization and reconciliation cycle."""
        self.status = "RUNNING"
        with Session(engine) as session, Session(sources_engine) as src_session:
            telemetry = await self._indexer.sync_and_reconcile_recent(
                session, sources_session=src_session
            )
            self.last_releases_found = telemetry.get("releases_inspected", 0)
            self.last_notifications_created = telemetry.get("notifications_created", 0)
            self.last_run_at = datetime.now(timezone.utc)
            self.status = "IDLE"
            self.current_backoff_seconds = self.interval_seconds
            return telemetry

    async def _run_loop(self) -> None:
        """Main loop with exponential backoff and jitter."""
        # Initial sleep before first run to allow server startup to stabilize
        try:
            await asyncio.sleep(min(10.0, self.interval_seconds))
        except asyncio.CancelledError:
            self.is_running = False
            return

        while self.is_running:
            try:
                logger.debug("Executing scheduled catalog auto-sync cycle...")
                await self.execute_cycle()
            except asyncio.CancelledError:
                self.is_running = False
                break
            except Exception as exc:
                self.status = "BACKOFF"
                self.current_backoff_seconds = min(self.current_backoff_seconds * 2, 7200.0)
                logger.warning(
                    "Scheduler cycle failed (%s). Backing off for %.0fs",
                    exc,
                    self.current_backoff_seconds,
                )

            # Apply +/- 10% jitter
            jitter = random.uniform(0.9, 1.1)
            wait_time = (
                self.current_backoff_seconds if self.status == "BACKOFF" else self.interval_seconds
            ) * jitter

            self.next_run_eta_seconds = int(wait_time)

            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                self.is_running = False
                break

    def get_telemetry(self) -> dict:
        """Return operational scheduler telemetry."""
        return {
            "status": self.status,
            "is_running": self.is_running,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_eta_seconds": self.next_run_eta_seconds,
            "last_releases_found": self.last_releases_found,
            "last_notifications_created": self.last_notifications_created,
        }


# Singleton instance shared across the application
scheduler = BackgroundSyncService()
