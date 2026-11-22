import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Clock,
  Database,
  FastForward,
  Film,
  Gauge,
  KeyRound,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Sparkles,
  StepForward,
  Table2,
  Tv,
} from "lucide-react";
import { api } from "../services/api";
import { HydrationPipelineStatus, IMDbSyncJobStatus, PillarSourceCursor } from "../types";
import { useToast } from "../context/ToastContext";

interface HydrationConsoleCardProps {
  onStepCompleted?: () => void;
  onStatusChange?: (status: HydrationPipelineStatus) => void;
  compact?: boolean;
}

  const MODE_LABELS: Record<"BOOTSTRAP" | "DELTA", { label: string; style: string }> = {
  DELTA: {
    label: "Apenas Novidades",
      style: "bg-emerald-500/20 text-emerald-300 border-emerald-500/35",
  },
  BOOTSTRAP: {
    label: "Varredura Inicial",
      style: "bg-amber-500/20 text-amber-200 border-amber-400/40",
  },
};

const SOURCE_LABELS: Record<string, string> = {
  yify: "YTS",
  tgx: "TorrentGalaxy",
  nyaasi: "Nyaa.si",
  bitsearch: "BitSearch",
  glodls: "GloDLS",
  eztv: "EZTV",
};

function formatDuration(totalSeconds?: number | null): string {
  if (totalSeconds === undefined || totalSeconds === null || totalSeconds < 0) {
    return "Calculando...";
  }
  const s = Math.floor(totalSeconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rem = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(rem).padStart(2, "0")}s`;
  return `${rem}s`;
}

function formatSourceProgress(key: string, cur: PillarSourceCursor): string {
  if (key === "yify") {
    if (cur.mode === "DELTA" || cur.bootstrap_completed) {
      return `100% varrido (${cur.total_pages.toLocaleString("pt-BR")} págs.) • checando novidades`;
    }
    const pct = cur.total_pages > 0 ? Math.round((cur.next_page / cur.total_pages) * 100) : 0;
    return `Página ${cur.next_page} de ${cur.total_pages} (${pct}%)`;
  }
  if (key === "eztv") return `${cur.releases_indexed.toLocaleString("pt-BR")} episódios`;
  if (cur.mode === "DELTA" || cur.bootstrap_completed) {
    return "100% varrido • em dia";
  }
  if (cur.recent_exhausted) {
    const pct = cur.sweep_pct ?? 0;
    const total = cur.sweep_total ?? 0;
    return total > 0
      ? `Catálogo ${pct}% (${cur.catalog_sweep_offset.toLocaleString("pt-BR")}/${total.toLocaleString("pt-BR")})`
      : `Verificando catálogo (item ${cur.catalog_sweep_offset})`;
  }
  return `Recentes p.${cur.next_page}`;
}

function formatRelativeDays(iso?: string | null): string {
  if (!iso) return "Base local pronta";
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return "Base local pronta";
  const days = Math.max(0, Math.floor((Date.now() - ts) / 86400000));
  if (days === 0) return "Atualizada hoje";
  if (days === 1) return "Atualizada há 1 dia";
  return `Atualizada há ${days} dias`;
}

export const HydrationConsoleCard: React.FC<HydrationConsoleCardProps> = ({
  onStepCompleted,
  onStatusChange,
  compact = false,
}) => {
  const { showToast } = useToast();
  const [status, setStatus] = useState<HydrationPipelineStatus | null>(null);
  const [imdbStatus, setImdbStatus] = useState<IMDbSyncJobStatus | null>(null);
  const [includeEpisodes, setIncludeEpisodes] = useState(false);
  const [scope, setScope] = useState<"all" | "sources" | "metadata">("all");
  const [busy, setBusy] = useState(false);
  const [activityOpen, setActivityOpen] = useState(!compact);
  const [techTableOpen, setTechTableOpen] = useState(false);

  const applyStatus = useCallback(
    (next: HydrationPipelineStatus) => {
      setStatus(next);
      onStatusChange?.(next);
    },
    [onStatusChange]
  );

  const loadStatus = useCallback(() => {
    api.explore.hydration
      .getStatus()
      .then((res) => applyStatus(res))
      .catch(() => null);
    api.explore.imdb
      .getStatus()
      .then((res) => setImdbStatus(res))
      .catch(() => null);
  }, [applyStatus]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    const shouldPoll =
      (status && status.state === "RUNNING") || (imdbStatus && imdbStatus.state === "RUNNING");
    if (!shouldPoll) return;
    const poll = () => {
      if (!document.hidden) loadStatus();
    };
    const id = window.setInterval(poll, 1000);
    const onVis = () => {
      if (!document.hidden) loadStatus();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [status, imdbStatus, loadStatus]);

  const handleToggleRun = async () => {
    if (!status) return;
    setBusy(true);
    try {
      const next =
        status.state === "RUNNING"
          ? await api.explore.hydration.pause()
          : await api.explore.hydration.start(scope);
      applyStatus(next);
      showToast(
        next.state === "RUNNING"
          ? "Atualização do catálogo iniciada em segundo plano."
          : "Atualização pausada. Seu progresso foi salvo.",
        "info"
      );
      onStepCompleted?.();
    } catch (err: any) {
      showToast(`Erro na atualização: ${err?.message || "falha inesperada"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleClearFocus = async () => {
    setBusy(true);
    try {
      const next = await api.explore.hydration.start("all", null, "pending");
      applyStatus(next);
      showToast("Foco removido: retomando atualização completa.", "info");
    } catch (err: any) {
      showToast(`Erro ao limpar foco: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleFocusProvider = async (
    provider: "tmdb" | "tvmaze",
    metaMode: "pending" | "missing_synopsis_ptbr"
  ) => {
    setBusy(true);
    try {
      const next = await api.explore.hydration.start("metadata", provider, metaMode);
      applyStatus(next);
      showToast(
        `Focando ${provider.toUpperCase()} (${
          metaMode === "missing_synopsis_ptbr" ? "re-enriquecer PT-BR" : "pendentes"
        }).`,
        "info"
      );
    } catch (err: any) {
      showToast(`Erro ao focar ${provider.toUpperCase()}: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleSkipRecent = async (sourceKey: string) => {
    setBusy(true);
    try {
      const next = await api.explore.hydration.skipRecent(sourceKey);
      applyStatus(next);
      showToast(`${SOURCE_LABELS[sourceKey] || sourceKey} avançado para varredura.`, "info");
    } catch (err: any) {
      showToast(`Erro ao pular recentes: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleImdbSync = async () => {
    setBusy(true);
    try {
      const next = await api.explore.imdb.sync(includeEpisodes);
      setImdbStatus(next);
      showToast("Atualização dos datasets IMDb iniciada em segundo plano.", "info");
    } catch (err: any) {
      showToast(`Erro ao iniciar sync IMDb: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleImdbReindex = async () => {
    setBusy(true);
    try {
      const next = await api.explore.imdb.reindexFts();
      setImdbStatus(next);
      showToast("Reindexação FTS5 iniciada em segundo plano.", "info");
    } catch (err: any) {
      showToast(`Erro ao reindexar FTS5: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleSingleStep = async () => {
    setBusy(true);
    try {
      const out = await api.explore.hydration.step(scope);
      applyStatus(out.status);
      showToast("Lote processado e progresso salvo.", "success");
      onStepCompleted?.();
    } catch (err: any) {
      showToast(`Falha ao processar lote: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    try {
      const next = await api.explore.hydration.resetCursor("all");
      applyStatus(next);
      showToast("Progresso de varredura inicial reiniciado.", "info");
    } catch (err: any) {
      showToast(`Erro ao reiniciar varredura: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return null;
  }

  const cov = status.coverage;
  const prov = status.provenance;
  const isRunning = status.state === "RUNNING";
  const sourceOrder = ["yify", "tgx", "nyaasi", "bitsearch", "glodls", "eztv"];
  const events = status.recent_events || [];
  const coreReady =
    (cov.pending_details ?? 0) === 0 && Boolean(status.sources?.yify?.bootstrap_completed);
  const sidecarSweeping = sourceOrder
    .filter((k) => k !== "yify" && k !== "eztv")
    .filter((k) => status.sources[k]?.mode === "BOOTSTRAP");
  const emaRates = status.ema_rates || {};
  const sidecarTotalRate = sourceOrder
    .filter((k) => k !== "yify" && k !== "eztv")
    .reduce((acc, k) => acc + (emaRates[k] || 0), 0);

return (
  <div
    className={`${compact ? "p-4" : "p-5"
      } rounded-2xl bg-surface-elevated border border-cyan-500/25 space-y-4`}
  >
    {/* Header + Primary Actions */}
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
      <div className="space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Sparkles className="w-5 h-5 text-cyan-400" />
          <h3 className="text-base font-extrabold text-white">
            Atualização do Catálogo
          </h3>
          <span
              className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${MODE_LABELS[status.overall_mode].style
              }`}
          >
            {MODE_LABELS[status.overall_mode].label}
          </span>
          {isRunning && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-cyan-500/20 text-cyan-200 border border-cyan-400/40">
              <span className="w-2 h-2 rounded-full bg-cyan-300 animate-ping" />
              Em execução
            </span>
          )}
        </div>
        <p className="text-xs text-slate-300">
          {isRunning && status.current_target
            ? status.current_target
            : "Atualize capas, sinopses e disponibilidade nas fontes de forma retomável."}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="O que atualizar"
          value={scope}
          onChange={(e) => setScope(e.target.value as "all" | "sources" | "metadata")}
          disabled={busy || isRunning}
          className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
        >
          <option value="all">Tudo (Fontes + Capas)</option>
          <option value="sources">Disponibilidade nas Fontes</option>
          <option value="metadata">Capas e Sinopses</option>
        </select>

        <button
          type="button"
          disabled={busy}
          onClick={handleToggleRun}
          className={`min-h-[44px] flex items-center gap-2 px-4 rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50 ${isRunning
              ? "bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-400/40"
              : "bg-cyan-600 hover:bg-cyan-500 text-white shadow-cinema-glow"
            }`}
        >
          {isRunning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          {isRunning ? "Pausar" : "Iniciar / Retomar"}
        </button>

        <button
          type="button"
          disabled={busy || isRunning}
          onClick={handleSingleStep}
          title="Processar apenas um lote rápido agora"
          className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-xs font-bold text-white cursor-pointer disabled:opacity-50"
        >
          <StepForward className="w-4 h-4" />
          {busy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : "1 Lote"}
        </button>

        {!compact && (
          <button
            type="button"
            disabled={busy || isRunning}
            onClick={handleReset}
            title="Reiniciar varredura inicial do zero"
            className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-semibold text-slate-300 cursor-pointer disabled:opacity-50"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reiniciar
          </button>
        )}
      </div>
    </div>

    {/* Two-Level Readiness Banner (ADR-018) */}
    {coreReady && (
      <div className="px-3.5 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <span className="font-bold text-emerald-200">
          Pronto para uso: Catálogo Principal, Capas e YTS em dia
        </span>
        {sidecarSweeping.length > 0 && (
          <span className="text-[11px] text-cyan-200 font-semibold">
            Varredura P2P contínua ({sidecarSweeping.map((k) => SOURCE_LABELS[k] || k).join(", ")})
          </span>
        )}
      </div>
    )}

    {/* Live Telemetry Bar (Speed, Elapsed, ETA, Processed) */}
    {(isRunning ||
      (status.total_elapsed_seconds ?? status.elapsed_seconds ?? 0) > 0 ||
      (status.items_processed_in_run ?? 0) > 0) && (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-xl bg-canvas/90 border border-cyan-500/20">
        <div className="flex items-center gap-2.5">
          <Gauge className="w-4 h-4 text-cyan-400 shrink-0" />
          <div>
            <div className="text-[11px] text-slate-400">Velocidade</div>
            <div className="text-xs font-extrabold text-white">
              {status.rate_per_minute
                ? `${status.rate_per_minute} itens/min`
                : isRunning
                  ? "1º lote em andamento..."
                  : "Aguardando"}
            </div>
            {sidecarTotalRate > 0 && (
              <div className="text-[10px] text-slate-400 truncate">
                Sidecar: {sidecarTotalRate.toFixed(1)}/min
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Clock className="w-4 h-4 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[11px] text-slate-400">Tempo decorrido</div>
            <div className="text-xs font-extrabold text-white">
              {formatDuration(status.total_elapsed_seconds ?? status.elapsed_seconds ?? 0)}
            </div>
            {(status.total_elapsed_seconds ?? 0) > (status.elapsed_seconds ?? 0) + 10 && (
              <div className="text-[10px] text-slate-400">
                Sessão: {formatDuration(status.elapsed_seconds ?? 0)}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Clock className="w-4 h-4 text-amber-300 shrink-0" />
          <div>
            <div className="text-[11px] text-slate-400">Tempo restante (est.)</div>
            <div className="text-xs font-extrabold text-white">
              {status.eta_seconds != null
                ? formatDuration(status.eta_seconds)
                : coreReady && sidecarSweeping.length === 0
                  ? "Concluído"
                  : "Calculando..."}
            </div>
            {(status.sources_eta_seconds != null ||
              status.metadata_eta_seconds != null ||
              status.sidecar_eta_seconds != null) && (
              <div className="text-[10px] text-slate-400 truncate">
                {status.sources_eta_seconds != null
                  ? `YTS: ${formatDuration(status.sources_eta_seconds)}`
                  : ""}
                {status.sources_eta_seconds != null && status.metadata_eta_seconds != null
                  ? " • "
                  : ""}
                {status.metadata_eta_seconds != null
                  ? `Capas: ${formatDuration(status.metadata_eta_seconds)}`
                  : ""}
                {(status.sources_eta_seconds != null || status.metadata_eta_seconds != null) &&
                status.sidecar_eta_seconds != null
                  ? " • "
                  : ""}
                {status.sidecar_eta_seconds != null
                  ? `Sidecar: ${formatDuration(status.sidecar_eta_seconds)}`
                  : ""}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Activity className="w-4 h-4 text-sky-400 shrink-0" />
          <div>
            <div className="text-[11px] text-slate-400">Nesta sessão</div>
            <div className="text-xs font-extrabold text-white">
              {(status.items_processed_in_run ?? 0).toLocaleString("pt-BR")} processados
            </div>
            <div className="text-[10px] text-slate-400">
              {status.steps_executed.toLocaleString("pt-BR")} ciclos do motor
            </div>
          </div>
        </div>
      </div>
    )}

    {/* Coverage Progress Bars */}
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div className="p-3 rounded-xl bg-canvas border border-white/10 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-slate-200">Capas no Catálogo</span>
          <span className="font-black text-emerald-300">{cov.posters_pct}%</span>
        </div>
        <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full bg-emerald-400 transition-all duration-300"
            style={{ width: `${Math.min(100, cov.posters_pct)}%` }}
          />
        </div>
        <p className="text-[11px] text-slate-400">
          {cov.with_poster.toLocaleString("pt-BR")} de {cov.total_shows.toLocaleString("pt-BR")}{" "}
          {(cov.pending_details ?? 0) === 0 ? (
            <span className="text-emerald-300 font-semibold">
              • 100% verificado (máximo das APIs)
            </span>
          ) : (
            `(${(cov.pending_details ?? cov.missing_posters).toLocaleString("pt-BR")} na fila)`
          )}
        </p>
      </div>

      <div className="p-3 rounded-xl bg-canvas border border-white/10 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-slate-200">Sinopses (PT-BR / EN)</span>
          <span className="font-black text-sky-300">
            {cov.synopsis_ptbr_pct}% / {cov.synopsis_pct}%
          </span>
        </div>
        <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full bg-sky-400 transition-all duration-300"
            style={{
              width: `${Math.min(100, Math.max(cov.synopsis_ptbr_pct, cov.synopsis_pct))}%`,
            }}
          />
        </div>
        <p className="text-[11px] text-slate-400">
          {cov.with_synopsis_ptbr.toLocaleString("pt-BR")} em português •{" "}
          {cov.with_synopsis.toLocaleString("pt-BR")} em inglês
        </p>
      </div>

      <div className="p-3 rounded-xl bg-canvas border border-white/10 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-slate-200">Metadados por Provedor</span>
          <span className="font-black text-amber-200">
            {(status.metadata_batches_executed ?? status.steps_executed).toLocaleString("pt-BR")} lotes
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px] font-semibold">
          <span className="px-2 py-0.5 rounded bg-white/5 text-slate-200">IMDb {prov.imdb}</span>
          <span className="px-2 py-0.5 rounded bg-white/5 text-slate-200">TMDB {prov.tmdb}</span>
          <span className="px-2 py-0.5 rounded bg-white/5 text-slate-200">
            TVMaze {prov.tvmaze}
          </span>
          <span className="px-2 py-0.5 rounded bg-white/5 text-slate-200">
            EZTV {prov.eztv + prov.self_healed_eztv}
          </span>
          <span className="px-2 py-0.5 rounded bg-white/5 text-slate-200">YTS {prov.yify}</span>
          <span className="px-2 py-0.5 rounded bg-white/5 text-slate-200">
            Wikipédia/Outros {prov.open_sources}
          </span>
        </div>
      </div>
    </div>

    {/* Mainstream Canonical & Enrichment Providers (ADR-018) */}
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-extrabold uppercase tracking-wider text-slate-300">
          Base Canônica &amp; Metadados (Mainstream)
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
        {/* IMDb Canonical Base Card */}
        <div className="p-3 rounded-xl bg-canvas border border-amber-400/25 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-extrabold text-white">
              <Database className="w-3.5 h-3.5 text-amber-300" />
              IMDb (Base Canônica)
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-200 border border-amber-400/30">
              {imdbStatus?.state === "RUNNING"
                ? `${Math.round(imdbStatus.progress_pct)}%`
                : formatRelativeDays(imdbStatus?.last_sync_at || cov.imdb_last_sync_at)}
            </span>
          </div>
          {imdbStatus?.state === "RUNNING" ? (
            <div className="space-y-1">
              <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div
                  className="h-full bg-amber-400 transition-all duration-300"
                  style={{ width: `${Math.min(100, imdbStatus.progress_pct)}%` }}
                />
              </div>
              <p className="text-[10px] text-amber-200 truncate">
                {imdbStatus.message || imdbStatus.stage}
              </p>
            </div>
          ) : (
            <p className="text-[11px] text-slate-400">
              {cov.total_shows.toLocaleString("pt-BR")} obras •{" "}
              {(cov.total_episodes ?? 0).toLocaleString("pt-BR")} episódios
            </p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <label className="inline-flex items-center gap-1.5 text-[10px] text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={includeEpisodes}
                onChange={(e) => setIncludeEpisodes(e.target.checked)}
                disabled={busy || imdbStatus?.state === "RUNNING"}
                className="rounded border-white/20 bg-canvas"
              />
              Incluir episódios
            </label>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={busy || imdbStatus?.state === "RUNNING"}
                onClick={handleImdbSync}
                className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-[10px] font-bold text-amber-100 cursor-pointer disabled:opacity-50"
              >
                Atualizar TSV
              </button>
              <button
                type="button"
                disabled={busy || imdbStatus?.state === "RUNNING"}
                onClick={handleImdbReindex}
                title="Reconstruir índice de busca FTS5"
                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/15 text-[10px] font-bold text-slate-200 cursor-pointer disabled:opacity-50"
              >
                <Search className="w-3 h-3" />
                FTS5
              </button>
            </div>
          </div>
        </div>

        {/* TMDB Card */}
        <div
          className={`p-3 rounded-xl bg-canvas border space-y-2 transition-all ${
            isRunning && status.target_provider === "tmdb"
              ? "border-sky-400 ring-1 ring-sky-400/50"
              : "border-sky-400/25"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-extrabold text-white">
              <Film className="w-3.5 h-3.5 text-sky-400" />
              TMDB
              {isRunning && status.target_provider === "tmdb" && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-sky-500/25 text-sky-200 text-[9px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-300 animate-ping" />
                  Em foco ({status.metadata_mode === "missing_synopsis_ptbr" ? "PT-BR" : "Pendentes"})
                </span>
              )}
            </span>
            {cov.tmdb_configured === false ? (
              <span
                title="Configure TMDB_API_KEY ou TMDB_READ_TOKEN no .env para habilitar o TMDB"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-200 border border-amber-400/40"
              >
                <KeyRound className="w-3 h-3" />
                Chave ausente
              </span>
            ) : (
              <span className="text-xs font-black text-sky-300">{cov.tmdb_pct ?? 0}%</span>
            )}
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div
              className={`h-full bg-sky-400 transition-all duration-300 ${
                isRunning && status.target_provider === "tmdb" ? "animate-pulse" : ""
              }`}
              style={{ width: `${Math.min(100, cov.tmdb_pct ?? 0)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400 truncate">
            {isRunning && status.target_provider === "tmdb"
              ? status.current_target ||
                `Varrendo ${status.focus_cursor_imdb || "..."} (${(cov.with_tmdb_id ?? 0).toLocaleString("pt-BR")} vinculadas)`
              : `${(cov.with_tmdb_id ?? 0).toLocaleString("pt-BR")} de ${cov.total_shows.toLocaleString("pt-BR")} obras vinculadas`}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <button
              type="button"
              disabled={busy || cov.tmdb_configured === false}
              onClick={() => handleFocusProvider("tmdb", "pending")}
              title="Pausa outras fontes temporariamente e dedica o motor às obras pendentes no TMDB."
              className="px-2.5 py-1 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 border border-sky-400/40 text-[10px] font-bold text-sky-100 cursor-pointer disabled:opacity-50"
            >
              Focar pendentes
            </button>
            <button
              type="button"
              disabled={busy || cov.tmdb_configured === false}
              onClick={() => handleFocusProvider("tmdb", "missing_synopsis_ptbr")}
              title="Varre obras sem sinopse em português buscando tradução/sinopse diretamente no TMDB."
              className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/15 text-[10px] font-bold text-slate-200 cursor-pointer disabled:opacity-50"
            >
              Re-enriquecer PT-BR
            </button>
            {isRunning && status.target_provider === "tmdb" && (
              <button
                type="button"
                disabled={busy}
                onClick={handleClearFocus}
                title="Remove o foco exclusivo e volta para o modo completo (Tudo)."
                className="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-[10px] font-bold text-amber-100 cursor-pointer disabled:opacity-50"
              >
                Limpar foco
              </button>
            )}
          </div>
        </div>

        {/* TVMaze Card */}
        <div
          className={`p-3 rounded-xl bg-canvas border space-y-2 transition-all ${
            isRunning && status.target_provider === "tvmaze"
              ? "border-cyan-400 ring-1 ring-cyan-400/50"
              : "border-cyan-400/25"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-extrabold text-white">
              <Tv className="w-3.5 h-3.5 text-cyan-400" />
              TVMaze (Séries)
              {isRunning && status.target_provider === "tvmaze" && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-500/25 text-cyan-200 text-[9px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-300 animate-ping" />
                  Em foco ({status.metadata_mode === "missing_synopsis_ptbr" ? "PT-BR" : "Pendentes"})
                </span>
              )}
            </span>
            <span className="text-xs font-black text-cyan-300">{cov.tvmaze_pct ?? 0}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div
              className={`h-full bg-cyan-400 transition-all duration-300 ${
                isRunning && status.target_provider === "tvmaze" ? "animate-pulse" : ""
              }`}
              style={{ width: `${Math.min(100, cov.tvmaze_pct ?? 0)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400 truncate">
            {isRunning && status.target_provider === "tvmaze"
              ? status.current_target ||
                `Varrendo ${status.focus_cursor_imdb || "..."} (${(cov.series_with_tvmaze_id ?? 0).toLocaleString("pt-BR")} vinculadas)`
              : `${(cov.series_with_tvmaze_id ?? 0).toLocaleString("pt-BR")} de ${(cov.series_total ?? 0).toLocaleString("pt-BR")} séries vinculadas`}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => handleFocusProvider("tvmaze", "pending")}
              title="Pausa outras fontes temporariamente e dedica o motor às séries pendentes no TVMaze."
              className="px-2.5 py-1 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/40 text-[10px] font-bold text-cyan-100 cursor-pointer disabled:opacity-50"
            >
              Focar pendentes
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => handleFocusProvider("tvmaze", "missing_synopsis_ptbr")}
              title="Varre séries sem sinopse em português buscando metadados atualizados no TVMaze."
              className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/15 text-[10px] font-bold text-slate-200 cursor-pointer disabled:opacity-50"
            >
              Re-enriquecer PT-BR
            </button>
            {isRunning && status.target_provider === "tvmaze" && (
              <button
                type="button"
                disabled={busy}
                onClick={handleClearFocus}
                title="Remove o foco exclusivo e volta para o modo completo (Tudo)."
                className="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-[10px] font-bold text-amber-100 cursor-pointer disabled:opacity-50"
              >
                Limpar foco
              </button>
            )}
          </div>
        </div>
      </div>
    </div>

    {/* Per-Source Human-Readable Progress Cards */}
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-extrabold uppercase tracking-wider text-slate-300">
          Fontes P2P
        </span>
        <button
          type="button"
          onClick={() => setTechTableOpen((v) => !v)}
          className="inline-flex items-center gap-1.5 text-[11px] font-bold text-cyan-300 hover:text-cyan-200 cursor-pointer"
        >
          <Table2 className="w-3.5 h-3.5" />
          {techTableOpen ? "Ocultar tabela técnica" : "Ver tabela técnica"}
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {sourceOrder.map((key) => {
          const cur = status.sources[key];
          if (!cur) return null;
          const badge = MODE_LABELS[cur.mode];
          const canSkipRecent =
            key !== "yify" && key !== "eztv" && cur.mode === "BOOTSTRAP" && !cur.recent_exhausted;
          const pct = cur.sweep_pct ?? 0;
          return (
            <div
              key={key}
              className="p-2.5 rounded-xl bg-canvas border border-white/10 flex flex-col justify-between gap-1.5"
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-extrabold text-white">
                  {SOURCE_LABELS[key] || key}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${badge.style}`}>
                  {cur.mode === "DELTA" ? "Em dia" : "Inicial"}
                </span>
              </div>
              <div className="text-[11px] font-bold text-cyan-300">
                {cur.titles_indexed.toLocaleString("pt-BR")} títulos
              </div>
              {((cur.recent_exhausted && cur.mode === "BOOTSTRAP") ||
                (key === "yify" && cur.total_pages > 1)) && (
                <div className="w-full h-1 rounded-full bg-white/10 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      cur.mode === "DELTA" || cur.bootstrap_completed
                        ? "bg-emerald-400"
                        : "bg-cyan-400"
                    }`}
                    style={{
                      width: `${Math.min(
                        100,
                        cur.mode === "DELTA" || cur.bootstrap_completed
                          ? 100
                          : key === "yify"
                            ? Math.round((cur.next_page / Math.max(1, cur.total_pages)) * 100)
                            : pct
                      )}%`,
                    }}
                  />
                </div>
              )}
              <div className="text-[10px] text-slate-400 truncate">
                {formatSourceProgress(key, cur)}
              </div>
              {canSkipRecent && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleSkipRecent(key)}
                  className="inline-flex items-center justify-center gap-1 px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-[9px] font-bold text-slate-300 cursor-pointer disabled:opacity-50"
                >
                  <FastForward className="w-2.5 h-2.5" />
                  Pular recentes
                </button>
              )}
            </div>
          );
        })}
      </div>

      {techTableOpen && (
        <div className="overflow-x-auto rounded-xl bg-canvas border border-white/10">
          <table className="w-full text-left text-[11px] text-slate-300">
            <thead className="bg-white/5 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="px-3 py-2">Fonte</th>
                <th className="px-3 py-2">Modo</th>
                <th className="px-3 py-2">Progresso</th>
                <th className="px-3 py-2">Taxa EMA</th>
                <th className="px-3 py-2">ETA</th>
                <th className="px-3 py-2">Erro / Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {sourceOrder.map((key) => {
                const cur = status.sources[key];
                if (!cur) return null;
                return (
                  <tr key={key} className="hover:bg-white/5">
                    <td className="px-3 py-1.5 font-bold text-white">
                      {SOURCE_LABELS[key] || key}
                    </td>
                    <td className="px-3 py-1.5">{cur.mode}</td>
                    <td className="px-3 py-1.5">{formatSourceProgress(key, cur)}</td>
                    <td className="px-3 py-1.5">
                      {(cur.rate_per_minute ?? 0) > 0 ? `${cur.rate_per_minute}/min` : "-"}
                    </td>
                    <td className="px-3 py-1.5">
                      {cur.eta_seconds != null ? formatDuration(cur.eta_seconds) : "-"}
                    </td>
                    <td className="px-3 py-1.5 text-rose-300 truncate max-w-[200px]">
                      {cur.last_error || "OK"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>

        {/* Collapsible Live Activity Monitor */}
        {!compact && (
          <div className="rounded-xl bg-canvas border border-white/10 overflow-hidden">
            <button
              type="button"
              onClick={() => setActivityOpen((o) => !o)}
              className="w-full min-h-[44px] px-3.5 py-2 flex items-center justify-between text-xs font-bold text-slate-200 hover:bg-white/5 cursor-pointer"
            >
              <span className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                Monitor de Atividade ({events.length})
              </span>
              {activityOpen ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>
            {activityOpen && (
              <div className="border-t border-white/10 max-h-48 overflow-y-auto divide-y divide-white/5">
                {events.length === 0 ? (
                  <div className="px-3.5 py-3 text-xs text-slate-400">
                    Nenhuma atividade registrada ainda nesta sessão. Clique em{" "}
                    <strong>Iniciar / Retomar</strong> ou <strong>1 Lote</strong> para acompanhar.
                  </div>
                ) : (
                  events.map((ev, idx) => (
                    <div
                      key={`${ev.timestamp}-${idx}`}
                      className="px-3.5 py-2 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={`w-2 h-2 rounded-full shrink-0 ${ev.outcome === "error"
                              ? "bg-rose-400"
                              : ev.outcome === "ok"
                                ? "bg-emerald-400"
                                : "bg-slate-400"
                            }`}
                        />
                        <span className="font-semibold text-white truncate">{ev.message}</span>
                      </div>
                      <span className="text-[10px] text-slate-400 shrink-0">
                        {new Date(ev.timestamp).toLocaleTimeString("pt-BR")}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </div>
      );
};
