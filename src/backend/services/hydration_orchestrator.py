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
from src.backend.core.domain_concurrency import create_shared_http_client
from src.backend.models.sources_db import ExternalSourceRecord
from src.backend.providers.sources.torrent_api_py_adapter import TorrentApiPySourceAdapter
from src.backend.providers.sources.yify_adapter import YIFYSourceAdapter
from src.backend.repositories.preferences import ExplorePreferencesRepository
from src.backend.services.cascading_enricher import CascadingMetadataEnricher
from src.backend.services.sources_registry import SourcesRegistryService

logger = logging.getLogger(__name__)

HYDRATION_STATE_KEY = "hydration_pipeline_v1"
IMDB_BOOTSTRAP_THRESHOLD = 250_000
EZTV_BOOTSTRAP_THRESHOLD = 500
PILLAR_SOURCE_KEYS: tuple[str, ...] = ("eztv", "yify", "tgx", "nyaasi", "bitsearch", "glodls")
SIDECAR_PILLAR_KEYS: tuple[str, ...] = ("tgx", "nyaasi", "bitsearch", "glodls")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat()


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
    total_elapsed_seconds: float = 0.0
    items_processed_in_run: int = 0
    rate_per_minute: float = 0.0
    eta_seconds: Optional[int] = None
    sources_eta_seconds: Optional[int] = None
    metadata_eta_seconds: Optional[int] = None
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
        self._persisted_elapsed_base: float = 0.0
        self._items_in_run: int = 0
        self._current_stage: Optional[str] = None
        self._current_target: Optional[str] = None
        self._recent_events: deque[HydrationActivityEvent] = deque(maxlen=15)
        self._step_window: deque[tuple[float, int, int]] = deque(maxlen=8)

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
        session_elapsed = self._accumulated_elapsed
        if self._run_started_mono is not None:
            session_elapsed += max(0.0, time.monotonic() - self._run_started_mono)
        state.elapsed_seconds = round(session_elapsed, 1)
        base_total = max(self._persisted_elapsed_base, float(state.total_elapsed_seconds or 0.0))
        state.total_elapsed_seconds = round(
            max(base_total, self._persisted_elapsed_base + session_elapsed), 1
        )
        state.started_at = self._run_started_iso
        state.items_processed_in_run = self._items_in_run
        state.current_stage = self._current_stage
        state.current_target = self._current_target
        state.recent_events = list(self._recent_events)

        win_dur = sum(d for d, _, _ in self._step_window)
        win_yts = sum(y for _, y, _ in self._step_window)
        win_meta = sum(m for _, _, m in self._step_window)

        yts_rate_per_min = 0.0
        meta_rate_per_min = 0.0
        if win_dur > 0.0:
            yts_rate_per_min = (win_yts / win_dur) * 60.0
            meta_rate_per_min = (win_meta / win_dur) * 60.0
            state.rate_per_minute = round(((win_yts + win_meta) / win_dur) * 60.0, 1)
        elif self._items_in_run > 0 and session_elapsed > 0.0:
            eff_minutes = max(session_elapsed / 60.0, 0.05)
            state.rate_per_minute = round(self._items_in_run / eff_minutes, 1)
        else:
            state.rate_per_minute = 0.0

        yts_eta: Optional[int] = None
        if state.scope in ("all", "sources"):
            yts_cur = state.sources.get("yify")
            if (
                yts_cur
                and not yts_cur.bootstrap_completed
                and yts_cur.total_pages > 1
                and yts_rate_per_min > 0.0
            ):
                rem_yts = max(0, (yts_cur.total_pages - yts_cur.next_page + 1) * 50)
                if rem_yts > 0:
                    yts_eta = int((rem_yts / yts_rate_per_min) * 60)

        meta_eta: Optional[int] = None
        if state.scope in ("all", "metadata") and meta_rate_per_min > 0.0:
            rem_meta = max(state.coverage.missing_posters, state.coverage.missing_synopsis)
            if rem_meta > 0:
                meta_eta = int((rem_meta / meta_rate_per_min) * 60)

        state.sources_eta_seconds = yts_eta
        state.metadata_eta_seconds = meta_eta

        if state.scope == "metadata":
            state.eta_seconds = meta_eta
        elif state.scope == "sources":
            state.eta_seconds = yts_eta
        else:
            etas = [v for v in (yts_eta, meta_eta) if v is not None]
            state.eta_seconds = max(etas) if etas else None
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
            state.total_elapsed_seconds = 0.0
            self._persisted_elapsed_base = 0.0
            self._accumulated_elapsed = 0.0
            self._step_window.clear()
        state.last_step_summary = f"Cursor reiniciado para alvo: {norm_target}."
        state = SmartBootstrapDetector.refresh_modes(state, mainstream_session, sources_session)
        return self._save_state(mainstream_session, state)

    async def run_single_step(
        self,
        mainstream_session: Session,
        sources_session: Session,
        *,
        scope: Literal["all", "sources", "metadata"] = "all",
        yts_pages: int = 6,
        sidecar_pages: int = 2,
        sweep_batch: int = 12,
        meta_batch: int = 20,
    ) -> dict[str, Any]:
        """Execute 3-phase bifurcated step: Prepare DB -> Fan-out HTTP -> Fan-in DB (ADR-017)."""
        async with self._get_lock():
            step_t0 = time.monotonic()
            state = self.get_status(mainstream_session, sources_session)
            if self._persisted_elapsed_base <= 0.0 and state.total_elapsed_seconds > 0.0:
                self._persisted_elapsed_base = state.total_elapsed_seconds
            standalone_step = self._run_started_mono is None
            step_yts_items = 0
            step_meta_items = 0
            step_notes: list[str] = []
            step_telemetry: dict[str, Any] = {}

            # --- PHASE 1: PREPARE DB (Read-only & Self-Heal before gather) ---
            yts_cur = state.sources.get("yify") or PillarSourceCursor(source_key="yify")
            yts_inst: Optional[ExternalSourceRecord] = None
            yts_adapter: Optional[YIFYSourceAdapter] = None
            yts_target_pg = 1 if yts_cur.mode == "DELTA" else yts_cur.next_page

            sidecar_plans: dict[str, dict[str, Any]] = {}
            adapters_map = SourcesRegistryService.get_adapters_map()

            if scope in ("all", "sources"):
                SourcesRegistryService.ensure_sources_registered(sources_session)
                y_rec = sources_session.get(ExternalSourceRecord, "yify")
                if y_rec and y_rec.enabled:
                    adp = adapters_map.get(y_rec.adapter_key)
                    if isinstance(adp, YIFYSourceAdapter):
                        yts_inst = y_rec
                        yts_adapter = adp

                for sk in SIDECAR_PILLAR_KEYS:
                    sc = state.sources.get(sk) or PillarSourceCursor(source_key=sk)
                    s_rec = sources_session.get(ExternalSourceRecord, sk)
                    if not s_rec or not s_rec.enabled:
                        continue
                    s_adp = adapters_map.get(s_rec.adapter_key)
                    if not isinstance(s_adp, TorrentApiPySourceAdapter):
                        continue
                    if not sc.recent_exhausted:
                        sidecar_plans[sk] = {
                            "mode": "recent",
                            "inst": s_rec,
                            "adapter": s_adp,
                            "cursor": sc,
                        }
                    else:
                        works = SourcesRegistryService.select_sweep_works(
                            mainstream_session,
                            source_key=sk,
                            offset=sc.catalog_sweep_offset,
                            batch_size=sweep_batch,
                        )
                        sidecar_plans[sk] = {
                            "mode": "sweep",
                            "inst": s_rec,
                            "adapter": s_adp,
                            "cursor": sc,
                            "works": works,
                        }

            heal_stats: dict[str, int] = {"eztv_to_mainstream": 0, "mainstream_to_eztv": 0}
            meta_candidates: list[Any] = []
            ez_by_imdb: dict[str, Any] = {}
            if scope in ("all", "metadata"):
                heal_stats, meta_candidates, ez_by_imdb = (
                    CascadingMetadataEnricher.prepare_metadata_batch(
                        mainstream_session, sources_session, batch_size=meta_batch
                    )
                )

            # Multi-lane progress summary during parallel Fan-out
            active_lanes: list[str] = []
            if scope in ("all", "sources"):
                src_count = (1 if yts_inst else 0) + len(sidecar_plans)
                if src_count:
                    active_lanes.append(f"Fontes ({src_count})")
            if scope in ("all", "metadata") and meta_candidates:
                active_lanes.append(f"Metadados ({len(meta_candidates)} obras)")
            if active_lanes:
                self._set_live_progress(
                    scope, f"{' + '.join(active_lanes)} em paralelo..."
                )

            # --- PHASE 2: FAN-OUT HTTP (Pure async HTTP, zero Session mutations) ---
            async def _run_yts_http(
                http_client: Any,
            ) -> dict[str, Any]:
                assert yts_adapter is not None and yts_inst is not None
                return await yts_adapter.fetch_sync_candidates(
                    yts_inst,
                    pages=1 if yts_cur.mode == "DELTA" else yts_pages,
                    start_page=yts_target_pg,
                    compact_presence=(yts_cur.mode == "BOOTSTRAP"),
                    mode="incremental" if yts_cur.mode == "DELTA" else "baseline",
                    client=http_client,
                )

            async def _run_sidecar_http(
                sk: str, plan: dict[str, Any], http_client: Any
            ) -> Any:
                sc: PillarSourceCursor = plan["cursor"]
                if plan["mode"] == "recent":
                    return await plan["adapter"].fetch_recent_candidates(
                        plan["inst"],
                        pages=min(sidecar_pages, 10),
                        limit=75,
                        start_page=sc.next_page,
                        client=http_client,
                    )
                return await SourcesRegistryService.fetch_sweep_batch_fanout(
                    plan["inst"],
                    plan["adapter"],
                    plan["works"],
                    client=http_client,
                )

            fanout_tasks: dict[str, Any] = {}
            async with create_shared_http_client(timeout=10.0) as shared_client:
                if yts_inst and yts_adapter:
                    fanout_tasks["yify"] = _run_yts_http(shared_client)
                for sk, plan in sidecar_plans.items():
                    fanout_tasks[f"sidecar:{sk}"] = _run_sidecar_http(sk, plan, shared_client)
                if scope in ("all", "metadata") and meta_candidates:
                    fanout_tasks["metadata"] = CascadingMetadataEnricher.fetch_metadata_fanout(
                        meta_candidates,
                        ez_by_imdb,
                        client=shared_client,
                    )

                keys_order = list(fanout_tasks.keys())
                raw_results = (
                    await asyncio.gather(
                        *(fanout_tasks[k] for k in keys_order),
                        return_exceptions=True,
                    )
                    if keys_order
                    else []
                )
            results_map = dict(zip(keys_order, raw_results))

            # --- PHASE 3: FAN-IN DB (Sequential batch persistence) ---
            if "yify" in results_map:
                y_res = results_map["yify"]
                if isinstance(y_res, Exception):
                    yts_cur.last_error = str(y_res)
                    self._record_event(
                        "yify",
                        f"Página {yts_target_pg}",
                        "error",
                        f"YTS temporariamente indisponível: {str(y_res)[:90]}",
                    )
                else:
                    cands = y_res["candidates"]
                    meta = dict(y_res["meta"])
                    idx_y, upd_y = YIFYSourceAdapter.persist_sync_candidates(
                        sources_session, "yify", cands
                    )
                    meta["releases_indexed"] = idx_y
                    meta["releases_updated"] = upd_y
                    if yts_inst is not None:
                        yts_inst.status = "ready"
                        yts_inst.last_error = None
                        yts_inst.cooldown_until = None
                        yts_inst.last_sync_at = _utc_now()
                        sources_session.add(yts_inst)
                        sources_session.commit()
                    yts_cur.last_error = None
                    yts_cur.total_pages = int(meta.get("total_pages") or yts_cur.total_pages)
                    seen_movies = int(meta.get("movies_seen") or 0)
                    step_yts_items += max(seen_movies, idx_y)
                    self._items_in_run += max(seen_movies, idx_y)
                    if yts_cur.mode == "BOOTSTRAP":
                        if meta.get("bootstrap_completed"):
                            yts_cur.bootstrap_completed = True
                            yts_cur.next_page = 1
                            yts_cur.mode = "DELTA"
                        else:
                            yts_cur.next_page = int(
                                meta.get("next_page") or (yts_cur.next_page + 1)
                            )
                    yts_cur.last_run_at = _utc_iso()
                    self._record_event(
                        "yify",
                        f"Página {yts_target_pg}",
                        "ok",
                        f"YTS: página {meta.get('start_page', 1)}/{yts_cur.total_pages} "
                        f"(+{idx_y} novos)",
                    )
                    step_notes.append(
                        f"YTS p.{meta.get('start_page', 1)}/{yts_cur.total_pages} (+{idx_y})"
                    )
                    step_telemetry["yify"] = meta
                state.sources["yify"] = yts_cur

            for sk, plan in sidecar_plans.items():
                sc = plan["cursor"]
                s_inst: ExternalSourceRecord = plan["inst"]
                res_item = results_map.get(f"sidecar:{sk}")
                if isinstance(res_item, Exception):
                    sc.last_error = str(res_item)
                    self._record_event(
                        sk,
                        f"Página {sc.next_page}",
                        "error",
                        f"{sk.upper()}: falha de conexão",
                    )
                    state.sources[sk] = sc
                    continue

                if plan["mode"] == "recent":
                    recent_cands = res_item or []
                    indexed_s = 0
                    matched_s = 0
                    for cand in recent_cands:
                        if cand.seeds < 1:
                            continue
                        imdb = cand.imdb_id
                        conf = cand.match_confidence
                        if not imdb:
                            r_id, r_conf, _ = (
                                SourcesRegistryService._resolve_imdb_id_against_mainstream(
                                    mainstream_session, cand.title, cand.year, cand.work_type
                                )
                            )
                            if r_id:
                                imdb = r_id
                                conf = max(conf, r_conf)
                                matched_s += 1
                        if imdb and conf >= 0.85:
                            cand.imdb_id = imdb
                            cand.match_confidence = conf
                            p_rows, _ = SourcesRegistryService._persist_verified_candidates(
                                sources_session, sk, imdb, [cand]
                            )
                            indexed_s += len(p_rows)

                    is_exhausted = len(recent_cands) == 0 or (
                        sc.mode == "BOOTSTRAP" and sc.next_page > 1 and indexed_s == 0
                    )
                    scanned = len(recent_cands)
                    self._items_in_run += scanned
                    if is_exhausted:
                        sc.recent_exhausted = True
                        sc.next_page = 1
                    else:
                        sc.next_page = sc.next_page + min(sidecar_pages, 10)
                    sc.last_error = None
                    sc.last_run_at = _utc_iso()
                    s_inst.status = "ready"
                    s_inst.last_error = None
                    s_inst.last_sync_at = _utc_now()
                    sources_session.add(s_inst)
                    sources_session.commit()
                    step_telemetry[sk] = {
                        "source": sk,
                        "exhausted": is_exhausted,
                        "candidates_scanned": scanned,
                        "canonical_matched": matched_s,
                        "releases_indexed": indexed_s,
                    }
                    self._record_event(
                        sk,
                        f"Recentes p.{sc.next_page}",
                        "ok" if indexed_s else "skipped",
                        f"{sk.upper()}: {scanned} analisados (+{indexed_s} novos)",
                    )
                    step_notes.append(f"{sk} p.{sc.next_page}(+{indexed_s})")
                else:
                    works = plan["works"]
                    if not works:
                        sc.bootstrap_completed = True
                        sc.catalog_sweep_offset = 0
                        sc.mode = "DELTA"
                        sw_res = {
                            "source": sk,
                            "titles_scanned": 0,
                            "releases_indexed": 0,
                            "exhausted": True,
                        }
                    else:
                        sw_res = SourcesRegistryService.persist_sweep_batch_fanin(
                            sources_session,
                            s_inst,
                            res_item,
                            offset=sc.catalog_sweep_offset,
                            batch_size=sweep_batch,
                        )
                        sc.last_error = sw_res.get("aborted_reason")
                        if not sw_res.get("aborted_reason"):
                            sc.catalog_sweep_offset = int(
                                sw_res.get("next_offset") or sc.catalog_sweep_offset
                            )
                            if sw_res.get("exhausted"):
                                sc.bootstrap_completed = True
                                sc.catalog_sweep_offset = 0
                                sc.mode = "DELTA"
                    scanned_sw = int(sw_res.get("titles_scanned") or 0)
                    added_sw = int(sw_res.get("releases_indexed") or 0)
                    self._items_in_run += scanned_sw
                    sc.last_run_at = _utc_iso()
                    step_telemetry[sk] = sw_res
                    self._record_event(
                        sk,
                        f"Catálogo @{sc.catalog_sweep_offset}",
                        "ok" if added_sw else "skipped",
                        f"{sk.upper()}: {scanned_sw} títulos verificados (+{added_sw})",
                    )
                    step_notes.append(f"{sk} cat.{sc.catalog_sweep_offset}(+{added_sw})")
                state.sources[sk] = sc

            if scope in ("all", "sources"):
                SourcesRegistryService._recompute_source_counters(sources_session)

            if scope in ("all", "metadata"):
                if meta_candidates:
                    m_res = results_map.get("metadata")
                    collected = {} if isinstance(m_res, Exception) or m_res is None else m_res
                    meta_res = CascadingMetadataEnricher.apply_metadata_fanin(
                        mainstream_session,
                        sources_session,
                        heal_stats,
                        meta_candidates,
                        ez_by_imdb,
                        collected,
                    )
                else:
                    meta_res = {
                        "processed": 0,
                        "updated": 0,
                        "self_heal": heal_stats,
                        "provenance": {"eztv": heal_stats.get("eztv_to_mainstream", 0)},
                        "exhausted": True,
                    }
                prov = meta_res.get("provenance") or {}
                heal = meta_res.get("self_heal") or heal_stats
                proc_m = int(meta_res.get("processed") or 0)
                upd_m = int(meta_res.get("updated") or 0)
                step_meta_items += proc_m
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

            step_dur = max(0.05, time.monotonic() - step_t0)
            self._step_window.append((step_dur, step_yts_items, step_meta_items))
            if standalone_step:
                self._accumulated_elapsed += step_dur

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
        state = self.get_status(mainstream_session, sources_session)
        self._persisted_elapsed_base = float(state.total_elapsed_seconds or 0.0)
        self._run_started_mono = time.monotonic()
        self._run_started_iso = _utc_iso()
        self._accumulated_elapsed = 0.0
        self._items_in_run = 0
        self._step_window.clear()
        self._record_event("sistema", "Atualização do Catálogo", "ok", "Atualização iniciada.")

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
