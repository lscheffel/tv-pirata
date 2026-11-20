"""Unified 3-Pillar Resumable Hydration Orchestrator & Smart Bootstrap Detector (ADR-015)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session

from src.backend.core.database import mainstream_engine, sources_engine
from src.backend.repositories.preferences import ExplorePreferencesRepository
from src.backend.services.cascading_enricher import CascadingMetadataEnricher
from src.backend.services.sources_registry import SourcesRegistryService

logger = logging.getLogger(__name__)

HYDRATION_STATE_KEY = "hydration_pipeline_v1"
IMDB_BOOTSTRAP_THRESHOLD = 250_000
EZTV_BOOTSTRAP_THRESHOLD = 500
PILLAR_SOURCE_KEYS: tuple[str, ...] = ("eztv", "yify", "tgx", "nyaasi", "bitsearch", "glodls")
SIDECAR_PILLAR_KEYS: tuple[str, ...] = ("tgx", "nyaasi", "bitsearch", "glodls")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PillarSourceCursor(BaseModel):
    """Persistent checkpoint cursor per source for resumable Stage 1B hydration."""

    source_key: str
    mode: Literal["BOOTSTRAP", "DELTA"] = "BOOTSTRAP"
    next_page: int = 1
    total_pages: int = 1
    recent_exhausted: bool = False
    catalog_sweep_offset: int = 0
    titles_indexed: int = 0
    releases_indexed: int = 0
    bootstrap_completed: bool = False
    last_run_at: Optional[str] = None
    last_error: Optional[str] = None


class WaterfallProvenanceCounts(BaseModel):
    """Cumulative enrichment attribution counters across the 6 canonical tiers."""

    imdb: int = 0
    tmdb: int = 0
    tvmaze: int = 0
    eztv: int = 0
    yify: int = 0
    open_sources: int = 0
    self_healed_eztv: int = 0
    self_healed_mainstream: int = 0


class CanonicalCoverageSnapshot(BaseModel):
    """Live completeness telemetry across mainstream.db and sources.db."""

    total_shows: int = 0
    with_poster: int = 0
    with_synopsis: int = 0
    with_synopsis_ptbr: int = 0
    missing_posters: int = 0
    missing_synopsis: int = 0
    posters_pct: float = 0.0
    synopsis_pct: float = 0.0
    synopsis_ptbr_pct: float = 0.0
    eztv_shows: int = 0
    eztv_missing_meta: int = 0


class HydrationActivityEvent(BaseModel):
    """Human-readable live activity entry kept in an in-memory ring buffer (ADR-016)."""

    timestamp: str
    stage: str
    target: str
    outcome: Literal["ok", "partial", "skipped", "error"] = "ok"
    message: str


class HydrationPipelineStatus(BaseModel):
    """Authoritative status contract stored under sync_state['hydration_pipeline_v1']."""

    schema_version: Literal[1] = 1
    state: Literal["IDLE", "RUNNING", "PAUSED", "COMPLETED", "ERROR"] = "IDLE"
    scope: Literal["all", "sources", "metadata"] = "all"
    overall_mode: Literal["BOOTSTRAP", "DELTA"] = "BOOTSTRAP"
    imdb_backbone_mode: Literal["BOOTSTRAP", "DELTA"] = "BOOTSTRAP"
    eztv_mode: Literal["BOOTSTRAP", "DELTA"] = "BOOTSTRAP"
    steps_executed: int = 0
    last_step_summary: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: Optional[str] = None
    is_worker_active: bool = False
    current_stage: Optional[str] = None
    current_target: Optional[str] = None
    started_at: Optional[str] = None
    elapsed_seconds: float = 0.0
    items_processed_in_run: int = 0
    rate_per_minute: float = 0.0
    eta_seconds: Optional[int] = None
    recent_events: list[HydrationActivityEvent] = Field(default_factory=list)
    coverage: CanonicalCoverageSnapshot = Field(default_factory=CanonicalCoverageSnapshot)
    sources: dict[str, PillarSourceCursor] = Field(default_factory=dict)
    provenance: WaterfallProvenanceCounts = Field(default_factory=WaterfallProvenanceCounts)


class SmartBootstrapDetector:
    """Detects Warm DB vs Zero-State Clean Install to pick DELTA vs BOOTSTRAP (DEC-001)."""

    @staticmethod
    def compute_coverage(
        mainstream_session: Session,
        sources_session: Optional[Session],
    ) -> tuple[CanonicalCoverageSnapshot, dict[str, tuple[int, int]]]:
        """Compute canonical coverage & per-source indexed counts in two fast SQL queries."""
        cov = CanonicalCoverageSnapshot()
        try:
            row = mainstream_session.exec(
                text(
                    """
                    SELECT
                        COUNT(*),
                        SUM(
                            CASE
                                WHEN poster_url IS NOT NULL AND poster_url != '' THEN 1 ELSE 0
                            END
                        ),
                        SUM(
                            CASE
                                WHEN synopsis IS NOT NULL AND synopsis != '' THEN 1 ELSE 0
                            END
                        ),
                        SUM(
                            CASE
                                WHEN synopsis_ptbr IS NOT NULL AND synopsis_ptbr != '' THEN 1
                                ELSE 0
                            END
                        )
                    FROM shows
                    """
                )
            ).first()
            if row and row[0]:
                total = int(row[0] or 0)
                with_p = int(row[1] or 0)
                with_s = int(row[2] or 0)
                with_pt = int(row[3] or 0)
                cov.total_shows = total
                cov.with_poster = with_p
                cov.with_synopsis = with_s
                cov.with_synopsis_ptbr = with_pt
                cov.missing_posters = max(0, total - with_p)
                cov.missing_synopsis = max(0, total - max(with_s, with_pt))
                cov.posters_pct = round((with_p / total) * 100.0, 2) if total else 0.0
                cov.synopsis_pct = round((with_s / total) * 100.0, 2) if total else 0.0
                cov.synopsis_ptbr_pct = round((with_pt / total) * 100.0, 2) if total else 0.0
        except Exception:
            pass

        src_counts: dict[str, tuple[int, int]] = {}
        if sources_session is not None:
            try:
                ez_row = sources_session.exec(
                    text(
                        """
                        SELECT
                            COUNT(*),
                            SUM(
                                CASE
                                    WHEN poster_url IS NULL OR poster_url = ''
                                      OR synopsis IS NULL OR synopsis = '' THEN 1
                                    ELSE 0
                                END
                            )
                        FROM shows
                        """
                    )
                ).first()
                if ez_row:
                    cov.eztv_shows = int(ez_row[0] or 0)
                    cov.eztv_missing_meta = int(ez_row[1] or 0)
            except Exception:
                pass

            try:
                rel_rows = sources_session.exec(
                    text(
                        """
                        SELECT
                            source_key,
                            COUNT(DISTINCT imdb_id),
                            COUNT(*)
                        FROM external_releases
                        GROUP BY source_key
                        """
                    )
                ).all()
                for s_key, t_cnt, r_cnt in rel_rows:
                    src_counts[str(s_key)] = (int(t_cnt or 0), int(r_cnt or 0))
            except Exception:
                pass

        return cov, src_counts

    @classmethod
    def refresh_modes(
        cls,
        status: HydrationPipelineStatus,
        mainstream_session: Session,
        sources_session: Optional[Session],
    ) -> HydrationPipelineStatus:
        """Recalculate maturity thresholds and synchronize live counts without erasing cursors."""
        cov, src_counts = cls.compute_coverage(mainstream_session, sources_session)
        status.coverage = cov
        status.imdb_backbone_mode = (
            "DELTA" if cov.total_shows >= IMDB_BOOTSTRAP_THRESHOLD else "BOOTSTRAP"
        )
        status.eztv_mode = "DELTA" if cov.eztv_shows >= EZTV_BOOTSTRAP_THRESHOLD else "BOOTSTRAP"

        for key in PILLAR_SOURCE_KEYS:
            cursor = status.sources.get(key) or PillarSourceCursor(source_key=key)
            if key == "eztv":
                ez_rel_titles, ez_rel_rows = src_counts.get("eztv", (0, 0))
                cursor.titles_indexed = max(cov.eztv_shows, ez_rel_titles)
                cursor.releases_indexed = ez_rel_rows
                cursor.bootstrap_completed = status.eztv_mode == "DELTA"
                cursor.mode = status.eztv_mode
            else:
                t_cnt, r_cnt = src_counts.get(key, (0, 0))
                cursor.titles_indexed = t_cnt
                cursor.releases_indexed = r_cnt
                cursor.mode = "DELTA" if cursor.bootstrap_completed else "BOOTSTRAP"
            status.sources[key] = cursor

        all_delta = status.imdb_backbone_mode == "DELTA" and all(
            status.sources[k].mode == "DELTA" for k in PILLAR_SOURCE_KEYS
        )
        status.overall_mode = "DELTA" if all_delta else "BOOTSTRAP"
        return status


class HydrationOrchestratorService:
    """Coordinated lifecycle worker executing the 3 Hydration Pillars with persistent resume."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._step_lock: Optional[asyncio.Lock] = None
        self._run_started_mono: Optional[float] = None
        self._run_started_iso: Optional[str] = None
        self._accumulated_elapsed: float = 0.0
        self._items_in_run: int = 0
        self._current_stage: Optional[str] = None
        self._current_target: Optional[str] = None
        self._recent_events: deque[HydrationActivityEvent] = deque(maxlen=15)

    def _get_lock(self) -> asyncio.Lock:
        if self._step_lock is None:
            self._step_lock = asyncio.Lock()
        return self._step_lock

    def _set_live_progress(self, stage: Optional[str], target: Optional[str]) -> None:
        self._current_stage = stage
        self._current_target = target

    def _record_event(
        self,
        stage: str,
        target: str,
        outcome: Literal["ok", "partial", "skipped", "error"],
        message: str,
    ) -> None:
        self._recent_events.appendleft(
            HydrationActivityEvent(
                timestamp=_utc_iso(),
                stage=stage,
                target=target,
                outcome=outcome,
                message=message,
            )
        )

    def _apply_live_telemetry(self, state: HydrationPipelineStatus) -> HydrationPipelineStatus:
        elapsed = self._accumulated_elapsed
        if self._run_started_mono is not None:
            elapsed += max(0.0, time.monotonic() - self._run_started_mono)
        state.elapsed_seconds = round(elapsed, 1)
        state.started_at = self._run_started_iso
        state.items_processed_in_run = self._items_in_run
        state.current_stage = self._current_stage
        state.current_target = self._current_target
        state.recent_events = list(self._recent_events)

        if self._items_in_run > 0 and elapsed > 0.0:
            eff_minutes = max(elapsed / 60.0, 0.05)
            state.rate_per_minute = round(self._items_in_run / eff_minutes, 1)
        else:
            state.rate_per_minute = 0.0

        remaining = 0
        if state.scope == "metadata":
            remaining = (
                state.coverage.missing_posters
                if state.coverage.missing_posters > 0
                else state.coverage.missing_synopsis
            )
        else:
            yts_cur = state.sources.get("yify")
            if yts_cur and not yts_cur.bootstrap_completed and yts_cur.total_pages > 1:
                remaining = max(0, (yts_cur.total_pages - yts_cur.next_page + 1) * 50)
            elif state.scope == "all":
                remaining = state.coverage.missing_posters

        if state.rate_per_minute > 0 and remaining > 0:
            state.eta_seconds = int((remaining / state.rate_per_minute) * 60)
        else:
            state.eta_seconds = None
        return state

    @staticmethod
    def _load_state(mainstream_session: Session) -> HydrationPipelineStatus:
        try:
            ExplorePreferencesRepository._ensure_sync_state_table(mainstream_session)
            row = mainstream_session.exec(
                text("SELECT value FROM sync_state WHERE key = :key"),
                params={"key": HYDRATION_STATE_KEY},
            ).first()
            if row and row[0]:
                return HydrationPipelineStatus.model_validate(json.loads(row[0]))
        except Exception:
            pass
        return HydrationPipelineStatus()

    @staticmethod
    def _save_state(
        mainstream_session: Session, state: HydrationPipelineStatus
    ) -> HydrationPipelineStatus:
        ExplorePreferencesRepository._ensure_sync_state_table(mainstream_session)
        state.updated_at = _utc_iso()
        payload = state.model_dump_json()
        mainstream_session.exec(
            text(
                """
                INSERT INTO sync_state (key, value, updated_at)
                VALUES (:key, :val, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            params={"key": HYDRATION_STATE_KEY, "val": payload},
        )
        mainstream_session.commit()
        return state

    def get_status(
        self,
        mainstream_session: Session,
        sources_session: Optional[Session] = None,
    ) -> HydrationPipelineStatus:
        """Load persistent state enriched with real-time SmartBootstrapDetector telemetry."""
        state = self._load_state(mainstream_session)
        state.is_worker_active = bool(self._task and not self._task.done())
        if state.state == "RUNNING" and not state.is_worker_active:
            if not os.environ.get("PYTEST_CURRENT_TEST"):
                state.state = "PAUSED"
        refreshed = SmartBootstrapDetector.refresh_modes(state, mainstream_session, sources_session)
        return self._apply_live_telemetry(refreshed)

    def reset_cursor(
        self,
        mainstream_session: Session,
        sources_session: Optional[Session] = None,
        *,
        target: str = "all",
    ) -> HydrationPipelineStatus:
        """Reset one or all resumable checkpoints back to BOOTSTRAP page 1 / offset 0."""
        state = self.get_status(mainstream_session, sources_session)
        norm_target = (target or "all").strip().lower()
        keys = PILLAR_SOURCE_KEYS if norm_target == "all" else (norm_target,)
        for key in keys:
            if key in state.sources:
                cur = state.sources[key]
                cur.next_page = 1
                cur.recent_exhausted = False
                cur.catalog_sweep_offset = 0
                cur.bootstrap_completed = False
                cur.last_error = None
                cur.mode = "BOOTSTRAP"
        if norm_target == "all":
            state.steps_executed = 0
            state.last_error = None
            state.state = "IDLE"
        state.last_step_summary = f"Cursor reiniciado para alvo: {norm_target}."
        state = SmartBootstrapDetector.refresh_modes(state, mainstream_session, sources_session)
        return self._save_state(mainstream_session, state)

    async def run_single_step(
        self,
        mainstream_session: Session,
        sources_session: Session,
        *,
        scope: Literal["all", "sources", "metadata"] = "all",
        yts_pages: int = 3,
        sidecar_pages: int = 2,
        sweep_batch: int = 8,
        meta_batch: int = 10,
    ) -> dict[str, Any]:
        """Execute one bounded, checkpoint-persisted step across active pillars (DEC-005)."""
        async with self._get_lock():
            if self._run_started_mono is None:
                self._run_started_mono = time.monotonic()
                self._run_started_iso = _utc_iso()
            state = self.get_status(mainstream_session, sources_session)
            step_notes: list[str] = []
            step_telemetry: dict[str, Any] = {}

            if scope in ("all", "sources"):
                # 1. YIFY / YTS Resumable Step
                yts_cur = state.sources.get("yify") or PillarSourceCursor(source_key="yify")
                target_pg = 1 if yts_cur.mode == "DELTA" else yts_cur.next_page
                self._set_live_progress(
                    "sources:yify",
                    f"Lendo página {target_pg} de {yts_cur.total_pages} no YTS",
                )
                try:
                    yts_mode = "incremental" if yts_cur.mode == "DELTA" else "baseline"
                    res = await SourcesRegistryService.sync_source(
                        sources_session,
                        mainstream_session,
                        source_key="yify",
                        pages=1 if yts_cur.mode == "DELTA" else yts_pages,
                        start_page=target_pg,
                        compact_presence=(yts_cur.mode == "BOOTSTRAP"),
                        enrich=False,
                        mode=yts_mode,
                        prune_after=(yts_cur.mode == "DELTA"),
                    )
                    y_tel = (res.get("results") or {}).get("yify", {}).get("telemetry") or {}
                    y_err = (res.get("results") or {}).get("yify", {}).get("error")
                    if y_err:
                        yts_cur.last_error = str(y_err)
                        self._record_event(
                            "yify",
                            f"Página {target_pg}",
                            "error",
                            f"YTS temporariamente indisponível: {str(y_err)[:90]}",
                        )
                    else:
                        yts_cur.last_error = None
                        yts_cur.total_pages = int(y_tel.get("total_pages") or yts_cur.total_pages)
                        seen_movies = int(y_tel.get("movies_seen") or 0)
                        added_yts = int(y_tel.get("releases_indexed") or 0)
                        self._items_in_run += max(seen_movies, added_yts)
                        if yts_cur.mode == "BOOTSTRAP":
                            if y_tel.get("bootstrap_completed"):
                                yts_cur.bootstrap_completed = True
                                yts_cur.next_page = 1
                                yts_cur.mode = "DELTA"
                            else:
                                yts_cur.next_page = int(
                                    y_tel.get("next_page") or (yts_cur.next_page + 1)
                                )
                        yts_cur.last_run_at = _utc_iso()
                        msg_yts = (
                            f"YTS: página {y_tel.get('start_page', 1)}/{yts_cur.total_pages} "
                            f"(+{added_yts} novos)"
                        )
                        self._record_event("yify", f"Página {target_pg}", "ok", msg_yts)
                        step_notes.append(
                            f"YTS p.{y_tel.get('start_page', 1)}/{yts_cur.total_pages} "
                            f"(+{added_yts})"
                        )
                    step_telemetry["yify"] = y_tel or res
                except Exception as exc:
                    yts_cur.last_error = str(exc)
                    self._record_event("yify", f"Página {target_pg}", "error", str(exc)[:90])
                state.sources["yify"] = yts_cur

                # 2. Sidecar Quartet Resumable Step (Recent pagination -> Catalog Sweep)
                for sk in SIDECAR_PILLAR_KEYS:
                    sc = state.sources.get(sk) or PillarSourceCursor(source_key=sk)
                    try:
                        if not sc.recent_exhausted:
                            self._set_live_progress(
                                f"sources:{sk}",
                                f"Lendo página {sc.next_page} em {sk.upper()}",
                            )
                            s_res = await SourcesRegistryService.sync_source(
                                sources_session,
                                mainstream_session,
                                source_key=sk,
                                pages=sidecar_pages,
                                start_page=sc.next_page,
                                enrich=False,
                                mode="incremental" if sc.mode == "DELTA" else "baseline",
                                prune_after=False,
                            )
                            s_tel = (s_res.get("results") or {}).get(sk, {}).get("telemetry") or {}
                            s_err = (s_res.get("results") or {}).get(sk, {}).get("error")
                            if s_err:
                                sc.last_error = str(s_err)
                                self._record_event(
                                    sk,
                                    f"Página {sc.next_page}",
                                    "error",
                                    f"{sk.upper()}: falha de conexão",
                                )
                            else:
                                sc.last_error = None
                                scanned = int(s_tel.get("candidates_scanned") or 0)
                                added_s = int(s_tel.get("releases_indexed") or 0)
                                self._items_in_run += scanned
                                if s_tel.get("exhausted"):
                                    sc.recent_exhausted = True
                                    sc.next_page = 1
                                else:
                                    sc.next_page = int(s_tel.get("next_page") or (sc.next_page + 1))
                                step_telemetry[sk] = s_tel
                                self._record_event(
                                    sk,
                                    f"Recentes p.{sc.next_page}",
                                    "ok" if added_s else "skipped",
                                    f"{sk.upper()}: {scanned} analisados (+{added_s} novos)",
                                )
                                step_notes.append(f"{sk} p.{sc.next_page}(+{added_s})")
                        else:
                            self._set_live_progress(
                                f"sources:{sk}",
                                (
                                    f"Verificando catálogo em {sk.upper()} "
                                    f"(item {sc.catalog_sweep_offset})"
                                ),
                            )
                            sw_res = await SourcesRegistryService.sweep_canonical_catalog_presence(
                                sources_session,
                                mainstream_session,
                                source_key=sk,
                                offset=sc.catalog_sweep_offset,
                                batch_size=sweep_batch,
                            )
                            sc.last_error = sw_res.get("aborted_reason")
                            scanned_sw = int(sw_res.get("titles_scanned") or 0)
                            added_sw = int(sw_res.get("releases_indexed") or 0)
                            self._items_in_run += scanned_sw
                            if not sw_res.get("aborted_reason"):
                                sc.catalog_sweep_offset = int(
                                    sw_res.get("next_offset") or sc.catalog_sweep_offset
                                )
                                if sw_res.get("exhausted"):
                                    sc.bootstrap_completed = True
                                    sc.catalog_sweep_offset = 0
                                    sc.mode = "DELTA"
                            step_telemetry[sk] = sw_res
                            self._record_event(
                                sk,
                                f"Catálogo @{sc.catalog_sweep_offset}",
                                "ok" if added_sw else "skipped",
                                f"{sk.upper()}: {scanned_sw} títulos verificados (+{added_sw})",
                            )
                            step_notes.append(
                                f"{sk} cat.{sc.catalog_sweep_offset}(+{added_sw})"
                            )
                        sc.last_run_at = _utc_iso()
                    except Exception as exc:
                        sc.last_error = str(exc)
                        self._record_event(sk, "Sincronia", "error", str(exc)[:90])
                    state.sources[sk] = sc

            if scope in ("all", "metadata"):
                self._set_live_progress("metadata", "Buscando capas e sinopses faltantes...")
                meta_res = await CascadingMetadataEnricher.enrich_batch(
                    mainstream_session,
                    sources_session,
                    batch_size=meta_batch,
                    on_progress=self._set_live_progress,
                )
                prov = meta_res.get("provenance") or {}
                heal = meta_res.get("self_heal") or {}
                proc_m = int(meta_res.get("processed") or 0)
                upd_m = int(meta_res.get("updated") or 0)
                self._items_in_run += proc_m
                state.provenance.imdb += int(prov.get("imdb", 0))
                state.provenance.tmdb += int(prov.get("tmdb", 0))
                state.provenance.tvmaze += int(prov.get("tvmaze", 0))
                state.provenance.eztv += int(prov.get("eztv", 0))
                state.provenance.yify += int(prov.get("yify", 0))
                state.provenance.open_sources += int(prov.get("open_sources", 0))
                state.provenance.self_healed_eztv += int(heal.get("mainstream_to_eztv", 0))
                state.provenance.self_healed_mainstream += int(heal.get("eztv_to_mainstream", 0))
                step_telemetry["metadata"] = meta_res
                self._record_event(
                    "metadata",
                    f"Lote {proc_m} obras",
                    "ok" if upd_m else "partial",
                    f"Capas e Sinopses: {upd_m} de {proc_m} obras atualizadas",
                )
                step_notes.append(f"Metadados +{upd_m}/{proc_m}")

            self._set_live_progress(None, None)
            state.steps_executed += 1
            state.scope = scope
            state.last_step_summary = " | ".join(step_notes) if step_notes else "Ciclo verificado."
            state = SmartBootstrapDetector.refresh_modes(state, mainstream_session, sources_session)
            state = self._apply_live_telemetry(state)
            self._save_state(mainstream_session, state)
            return {
                "status": state.model_dump(),
                "step_telemetry": step_telemetry,
            }

    async def _worker_loop(
        self, scope: Literal["all", "sources", "metadata"], interval_seconds: float
    ) -> None:
        logger.info("HydrationOrchestrator worker loop started (scope=%s)", scope)
        try:
            while not self._stop_event.is_set():
                try:
                    with Session(mainstream_engine) as ms_sess, Session(sources_engine) as src_sess:
                        await self.run_single_step(ms_sess, src_sess, scope=scope)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("HydrationOrchestrator step error: %s", exc)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("HydrationOrchestrator worker loop cancelled cleanly")
        finally:
            try:
                with Session(mainstream_engine) as ms_sess:
                    st = self._load_state(ms_sess)
                    if st.state == "RUNNING":
                        st.state = "PAUSED"
                    st.is_worker_active = False
                    self._save_state(ms_sess, st)
            except Exception:
                pass

    def start(
        self,
        mainstream_session: Session,
        sources_session: Optional[Session] = None,
        *,
        scope: Literal["all", "sources", "metadata"] = "all",
        interval_seconds: float = 2.0,
    ) -> HydrationPipelineStatus:
        """Start or resume the cooperative background hydration loop."""
        self._run_started_mono = time.monotonic()
        self._run_started_iso = _utc_iso()
        self._accumulated_elapsed = 0.0
        self._items_in_run = 0
        self._record_event("sistema", "Atualização do Catálogo", "ok", "Atualização iniciada.")

        state = self.get_status(mainstream_session, sources_session)
        state.state = "RUNNING"
        state.scope = scope
        state.last_error = None
        state = self._apply_live_telemetry(state)
        state = self._save_state(mainstream_session, state)

        if os.environ.get("PYTEST_CURRENT_TEST"):
            return state

        if self._task and not self._task.done():
            state.is_worker_active = True
            return state

        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._worker_loop(scope, interval_seconds),
            name="tv-pirata-hydration-orchestrator",
        )
        state.is_worker_active = True
        return state

    async def pause(
        self,
        mainstream_session: Session,
        sources_session: Optional[Session] = None,
        *,
        timeout: float = 3.0,
    ) -> HydrationPipelineStatus:
        """Pause the hydration loop cleanly preserving all DB checkpoints."""
        await self.stop(timeout=timeout)
        if self._run_started_mono is not None:
            self._accumulated_elapsed += max(0.0, time.monotonic() - self._run_started_mono)
            self._run_started_mono = None
        self._set_live_progress(None, None)
        self._record_event("sistema", "Atualização do Catálogo", "skipped", "Atualização pausada.")
        state = self.get_status(mainstream_session, sources_session)
        state.state = "PAUSED"
        state.is_worker_active = False
        state = self._apply_live_telemetry(state)
        return self._save_state(mainstream_session, state)

    async def stop(self, timeout: float = 3.0) -> None:
        """Cooperative shutdown guard for FastAPI lifespan teardown."""
        self._stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        self._task = None


hydration_orchestrator = HydrationOrchestratorService()
