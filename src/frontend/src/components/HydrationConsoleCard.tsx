import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Clock,
  Gauge,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  StepForward,
} from "lucide-react";
import { api } from "../services/api";
import { HydrationPipelineStatus, PillarSourceCursor } from "../types";
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
  if (key === "yify") return `Página ${cur.next_page} de ${cur.total_pages}`;
  if (key === "eztv") return `${cur.releases_indexed.toLocaleString("pt-BR")} episódios`;
  if (cur.recent_exhausted) return `Verificando catálogo (item ${cur.catalog_sweep_offset})`;
  return `Lendo página ${cur.next_page}`;
}

export const HydrationConsoleCard: React.FC<HydrationConsoleCardProps> = ({
  onStepCompleted,
  onStatusChange,
  compact = false,
}) => {
  const { showToast } = useToast();
  const [status, setStatus] = useState<HydrationPipelineStatus | null>(null);
  const [scope, setScope] = useState<"all" | "sources" | "metadata">("all");
  const [busy, setBusy] = useState(false);
  const [activityOpen, setActivityOpen] = useState(!compact);

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
}, [applyStatus]);

useEffect(() => {
  loadStatus();
}, [loadStatus]);

useEffect(() => {
  if (!status || status.state !== "RUNNING") return;
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
}, [status, loadStatus]);

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
              {status.rate_per_minute ? `${status.rate_per_minute} itens/min` : "Medindo..."}
            </div>
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
              {formatDuration(status.eta_seconds)}
            </div>
            {(status.sources_eta_seconds != null || status.metadata_eta_seconds != null) && (
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
          ({cov.missing_posters.toLocaleString("pt-BR")} pendentes)
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
          <span className="font-black text-amber-200">{status.steps_executed} lotes</span>
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

        {/* Per-Source Human-Readable Progress Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {sourceOrder.map((key) => {
            const cur = status.sources[key];
            if (!cur) return null;
            const badge = MODE_LABELS[cur.mode];
            return (
              <div
                key={key}
                className="p-2.5 rounded-xl bg-canvas border border-white/10 flex flex-col justify-between gap-1"
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
                <div className="text-[10px] text-slate-400 truncate">
                  {formatSourceProgress(key, cur)}
                </div>
              </div>
            );
          })}
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
