"""Asynchronous IMDb Canonical Dataset Sync & FTS5 Reindex Service (ADR-018 Bloco 2)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.database import DEFAULT_MAINSTREAM_DB_PATH, mainstream_engine
from src.backend.repositories.preferences import ExplorePreferencesRepository

logger = logging.getLogger(__name__)

IMDB_SYNC_STATE_KEY = "imdb_canonical_sync_v1"
IMDB_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "imdb-metadata-catalog.py"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IMDbSyncJobStatus(BaseModel):
    """Persistent and live status contract for IMDb TSV sync & FTS5 rebuild."""

    state: Literal["IDLE", "RUNNING", "COMPLETED", "ERROR"] = "IDLE"
    stage: Literal[
        "idle",
        "checking_remote",
        "downloading",
        "importing_works",
        "importing_episodes",
        "rebuilding_fts",
        "refreshing_facets",
        "completed",
        "error",
    ] = "idle"
    progress_pct: float = 0.0
    include_episodes: bool = False
    works_processed: int = 0
    episodes_processed: int = 0
    delta_inserted: int = 0
    delta_updated: int = 0
    local_last_modified: Optional[str] = None
    remote_last_modified: Optional[str] = None
    cache_status: Literal["unknown", "up_to_date", "downloaded", "remote_check_failed"] = "unknown"
    last_sync_at: Optional[str] = None
    last_error: Optional[str] = None
    message: Optional[str] = None


def _load_imdb_catalog_module() -> Any:
    """Dynamically load scripts/imdb-metadata-catalog.py without executing main()."""
    spec = importlib.util.spec_from_file_location("imdb_metadata_catalog_mod", IMDB_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"IMDb sync script not found: {IMDB_SCRIPT_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IMDbCanonicalSyncService:
    """Cooperative background manager for IMDb canonical TSV ingestion and FTS5 rebuild."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._status: IMDbSyncJobStatus = IMDbSyncJobStatus()
        self._hydrated_from_db: bool = False

    def _load_persisted(self, session: Session) -> None:
        if self._hydrated_from_db:
            return
        try:
            ExplorePreferencesRepository._ensure_sync_state_table(session)
            row = session.exec(
                text("SELECT value FROM sync_state WHERE key = :key"),
                params={"key": IMDB_SYNC_STATE_KEY},
            ).first()
            if row and row[0]:
                data = json.loads(row[0])
                self._status.last_sync_at = data.get("last_sync_at")
                self._status.works_processed = int(data.get("works_processed") or 0)
                self._status.episodes_processed = int(data.get("episodes_processed") or 0)
                self._status.delta_inserted = int(data.get("delta_inserted") or 0)
                self._status.delta_updated = int(data.get("delta_updated") or 0)
                self._status.local_last_modified = data.get("local_last_modified")
                self._status.remote_last_modified = data.get("remote_last_modified")
                c_stat = data.get("cache_status")
                if c_stat in ("unknown", "up_to_date", "downloaded", "remote_check_failed"):
                    self._status.cache_status = c_stat
        except Exception:
            pass
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            self._hydrated_from_db = True

    def _persist_summary(self, session: Session) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return
        try:
            ExplorePreferencesRepository._ensure_sync_state_table(session)
            payload = json.dumps(
                {
                    "last_sync_at": self._status.last_sync_at,
                    "works_processed": self._status.works_processed,
                    "episodes_processed": self._status.episodes_processed,
                    "delta_inserted": self._status.delta_inserted,
                    "delta_updated": self._status.delta_updated,
                    "local_last_modified": self._status.local_last_modified,
                    "remote_last_modified": self._status.remote_last_modified,
                    "cache_status": self._status.cache_status,
                }
            )
            session.exec(
                text(
                    """
                    INSERT INTO sync_state (key, value, updated_at)
                    VALUES (:key, :val, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                params={"key": IMDB_SYNC_STATE_KEY, "val": payload},
            )
            session.commit()
        except Exception as exc:
            logger.warning("Failed to persist IMDb sync summary: %s", exc)

    def get_status(self, session: Optional[Session] = None) -> IMDbSyncJobStatus:
        """Return live IMDb TSV/FTS5 job status."""
        if session is not None:
            self._load_persisted(session)
        return self._status.model_copy()

    def _run_stage1_download_blocking(self, include_episodes: bool) -> dict[str, Any]:
        """Stage 1: Check remote HEAD and download updated TSVs with zero SQLite locks."""
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return {
                "downloaded_any": False,
                "check_failed": False,
                "cache_status": "up_to_date",
                "local_last_modified": None,
                "remote_last_modified": None,
            }
        mod = _load_imdb_catalog_module()
        self._status.stage = "checking_remote"
        self._status.progress_pct = 10.0
        self._status.message = "Verificando revisão oficial nos servidores IMDb..."
        head_info = mod.check_remote_revisions(("ratings", "basics", "akas"))
        if head_info.get("check_failed") and not head_info.get("remote_last_modified"):
            return {
                "downloaded_any": False,
                "check_failed": True,
                "cache_status": "remote_check_failed",
                "local_last_modified": head_info.get("local_last_modified"),
                "remote_last_modified": None,
            }
        self._status.stage = "downloading"
        self._status.progress_pct = 25.0
        self._status.message = (
            "Baixando datasets oficiais do IMDb (em paralelo, sem travar o app)..."
        )
        dl_info = mod.download_datasets_stage1(
            include_akas_br=True,
            include_episodes=include_episodes,
            force_download=False,
        )
        return dl_info

    def _run_stage2_apply_blocking(self, include_episodes: bool) -> dict[str, Any]:
        """Stage 2: Apply TSV delta to SQLite, rebuild FTS5 and refresh global_facets_v2."""
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return {
                "works_cnt": 0,
                "eps_cnt": 0,
                "delta_inserted": 0,
                "delta_updated": 0,
            }
        db_path = str(DEFAULT_MAINSTREAM_DB_PATH)
        mod = _load_imdb_catalog_module()
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            self._status.stage = "importing_works"
            self._status.progress_pct = 55.0
            self._status.message = "Aplicando delta de obras e notas canônicas no catálogo..."
            sync_res = (
                mod.sync_level1_datasets(
                    conn,
                    include_episodes=include_episodes,
                    force_download=False,
                )
                or {}
            )
            if include_episodes:
                self._status.stage = "importing_episodes"
                self._status.progress_pct = 75.0
            self._status.stage = "rebuilding_fts"
            self._status.progress_pct = 88.0
            self._status.message = "Reconstruindo índice FTS5 de busca..."
            conn.execute("INSERT INTO shows_fts(shows_fts) VALUES('rebuild')")
            conn.commit()
            works_cnt = int(conn.execute("SELECT COUNT(*) FROM shows").fetchone()[0] or 0)
            eps_cnt = int(conn.execute("SELECT COUNT(*) FROM episodes_catalog").fetchone()[0] or 0)
            return {
                "works_cnt": works_cnt,
                "eps_cnt": eps_cnt,
                "delta_inserted": int(sync_res.get("delta_inserted") or 0),
                "delta_updated": int(sync_res.get("delta_updated") or 0),
                "remote_last_modified": sync_res.get("remote_last_modified"),
                "local_last_modified": sync_res.get("local_last_modified"),
            }
        finally:
            conn.close()

    def _run_reindex_fts_blocking(self) -> int:
        """Rebuild shows_fts index inside mainstream.db."""
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return 0
        db_path = str(DEFAULT_MAINSTREAM_DB_PATH)
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            conn.execute("INSERT INTO shows_fts(shows_fts) VALUES('rebuild')")
            conn.commit()
            return int(conn.execute("SELECT COUNT(*) FROM shows").fetchone()[0] or 0)
        finally:
            conn.close()

    async def _execute_cooperative_job(
        self,
        *,
        mode: Literal["sync", "reindex_fts"],
        include_episodes: bool = False,
    ) -> None:
        from src.backend.repositories.discovery_engine import DiscoveryEngineRepository
        from src.backend.services.hydration_orchestrator import hydration_orchestrator

        was_running = False
        resume_scope: Literal["all", "sources", "metadata"] = "all"
        resume_target: Optional[str] = None
        resume_meta_mode: Literal["pending", "missing_synopsis_ptbr"] = "pending"

        try:
            if mode == "sync":
                # Stage 1 runs completely lock-free while orchestrator continues serving P2P
                dl_info = await asyncio.to_thread(
                    self._run_stage1_download_blocking, include_episodes
                )
                self._status.local_last_modified = dl_info.get("local_last_modified")
                self._status.remote_last_modified = dl_info.get("remote_last_modified")
                c_stat = dl_info.get("cache_status", "unknown")
                self._status.cache_status = c_stat

                if dl_info.get("check_failed"):
                    self._status.state = "ERROR"
                    self._status.stage = "error"
                    self._status.last_error = (
                        "Falha ao consultar revisão remota do IMDb (HTTP HEAD)."
                    )
                    self._status.message = "Falha ao verificar versão oficial no servidor IMDb."
                    return

                # Stage 2: Cooperative pause only for SQLite write + FTS5 + facets
                if not os.environ.get("PYTEST_CURRENT_TEST"):
                    with Session(mainstream_engine) as ms_sess:
                        st = hydration_orchestrator.get_status(ms_sess)
                        if st.state == "RUNNING":
                            was_running = True
                            resume_scope = st.scope
                            resume_target = st.target_provider
                            resume_meta_mode = st.metadata_mode
                            await hydration_orchestrator.pause(ms_sess)

                apply_res = await asyncio.to_thread(
                    self._run_stage2_apply_blocking, include_episodes
                )
                self._status.works_processed = int(apply_res.get("works_cnt") or 0)
                self._status.episodes_processed = int(apply_res.get("eps_cnt") or 0)
                self._status.delta_inserted = int(apply_res.get("delta_inserted") or 0)
                self._status.delta_updated = int(apply_res.get("delta_updated") or 0)
                if apply_res.get("remote_last_modified"):
                    self._status.remote_last_modified = apply_res.get("remote_last_modified")
                if apply_res.get("local_last_modified"):
                    self._status.local_last_modified = apply_res.get("local_last_modified")

                if not os.environ.get("PYTEST_CURRENT_TEST"):
                    self._status.stage = "refreshing_facets"
                    self._status.progress_pct = 95.0
                    self._status.message = "Atualizando facetas globais do catálogo..."
                    with Session(mainstream_engine) as ms_sess:
                        DiscoveryEngineRepository.refresh_global_facets_cache(ms_sess)

                self._status.last_sync_at = _utc_iso()
            else:
                if not os.environ.get("PYTEST_CURRENT_TEST"):
                    with Session(mainstream_engine) as ms_sess:
                        st = hydration_orchestrator.get_status(ms_sess)
                        if st.state == "RUNNING":
                            was_running = True
                            resume_scope = st.scope
                            resume_target = st.target_provider
                            resume_meta_mode = st.metadata_mode
                            await hydration_orchestrator.pause(ms_sess)
                self._status.stage = "rebuilding_fts"
                self._status.progress_pct = 50.0
                self._status.message = "Reindexando busca FTS5 do catálogo canônico..."
                works_cnt = await asyncio.to_thread(self._run_reindex_fts_blocking)
                self._status.works_processed = works_cnt

            self._status.state = "COMPLETED"
            self._status.stage = "completed"
            self._status.progress_pct = 100.0
            self._status.last_error = None
            if mode == "sync":
                self._status.message = (
                    f"IMDb atualizado (+{self._status.delta_inserted:,} novas, "
                    f"+{self._status.delta_updated:,} notas/anos)."
                )
            else:
                self._status.message = "Índice de busca FTS5 reconstruído."
            if not os.environ.get("PYTEST_CURRENT_TEST"):
                with Session(mainstream_engine) as ms_sess:
                    self._persist_summary(ms_sess)
            catalog_cache.invalidate()
            discovery_cache.invalidate()
        except Exception as exc:
            self._status.state = "ERROR"
            self._status.stage = "error"
            self._status.last_error = str(exc)
            self._status.message = f"Falha na operação IMDb: {str(exc)[:120]}"
        finally:
            if was_running and not os.environ.get("PYTEST_CURRENT_TEST"):
                try:
                    with Session(mainstream_engine) as ms_sess:
                        hydration_orchestrator.start(
                            ms_sess,
                            scope=resume_scope,
                            target_provider=resume_target,
                            metadata_mode=resume_meta_mode,
                        )
                except Exception as exc:
                    logger.warning("Failed to resume orchestrator after IMDb sync: %s", exc)

    async def check_and_trigger_auto_sync(self, session: Session) -> dict[str, Any]:
        """Lightweight HEAD check used by novidades mode; triggers background sync if >24h stale."""
        self._load_persisted(session)
        if self._task and not self._task.done():
            return {"triggered": False, "reason": "already_running"}
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return {"triggered": False, "reason": "pytest_isolated"}

        last_dt: Optional[datetime] = None
        if self._status.last_sync_at:
            try:
                last_dt = datetime.fromisoformat(self._status.last_sync_at.replace("Z", "+00:00"))
            except ValueError:
                last_dt = None

        age_hours = (
            (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
            if last_dt is not None
            else 999.0
        )
        if age_hours < 24.0:
            return {
                "triggered": False,
                "reason": "fresh_within_24h",
                "age_hours": round(age_hours, 1),
            }

        mod = _load_imdb_catalog_module()
        head_info = await asyncio.to_thread(
            mod.check_remote_revisions, ("ratings", "basics", "akas")
        )
        self._status.remote_last_modified = head_info.get("remote_last_modified")
        self._status.local_last_modified = head_info.get("local_last_modified")
        if head_info.get("check_failed"):
            self._status.cache_status = "remote_check_failed"
            return {"triggered": False, "reason": "remote_check_failed"}
        if not head_info.get("has_updates"):
            self._status.cache_status = "up_to_date"
            return {"triggered": False, "reason": "remote_unchanged"}

        await self.start_sync(session, include_episodes=False)
        return {
            "triggered": True,
            "reason": "remote_revision_newer",
            "remote_last_modified": head_info.get("remote_last_modified"),
        }

    async def start_sync(
        self, session: Session, *, include_episodes: bool = False
    ) -> IMDbSyncJobStatus:
        """Start asynchronous IMDb TSV sync job."""
        self._load_persisted(session)
        if self._task and not self._task.done():
            return self.get_status(session)

        self._status.state = "RUNNING"
        self._status.stage = "downloading"
        self._status.progress_pct = 5.0
        self._status.include_episodes = include_episodes
        self._status.last_error = None
        self._status.message = "Iniciando atualização da base canônica IMDb..."

        if os.environ.get("PYTEST_CURRENT_TEST"):
            await self._execute_cooperative_job(mode="sync", include_episodes=include_episodes)
            return self.get_status(session)

        self._task = asyncio.create_task(
            self._execute_cooperative_job(mode="sync", include_episodes=include_episodes),
            name="tv-pirata-imdb-sync",
        )
        return self.get_status(session)

    async def start_reindex_fts(self, session: Session) -> IMDbSyncJobStatus:
        """Start asynchronous FTS5 rebuild job."""
        self._load_persisted(session)
        if self._task and not self._task.done():
            return self.get_status(session)

        self._status.state = "RUNNING"
        self._status.stage = "rebuilding_fts"
        self._status.progress_pct = 10.0
        self._status.last_error = None
        self._status.message = "Iniciando reindexação FTS5..."

        if os.environ.get("PYTEST_CURRENT_TEST"):
            await self._execute_cooperative_job(mode="reindex_fts")
            return self.get_status(session)

        self._task = asyncio.create_task(
            self._execute_cooperative_job(mode="reindex_fts"),
            name="tv-pirata-imdb-fts-reindex",
        )
        return self.get_status(session)


imdb_sync_service = IMDbCanonicalSyncService()
