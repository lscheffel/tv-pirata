import React, { useCallback, useEffect, useState } from "react";
import {
  Layers,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  StepForward,
} from "lucide-react";
import { api } from "../services/api";
import { HydrationPipelineStatus } from "../types";
import { useToast } from "../context/ToastContext";

interface HydrationConsoleCardProps {
  onStepCompleted?: () => void;
  compact?: boolean;
}

const MODE_BADGE_STYLES: Record<"BOOTSTRAP" | "DELTA", string> = {
  DELTA: "bg-emerald-500/20 text-emerald-300 border-emerald-500/35",
  BOOTSTRAP: "bg-amber-500/20 text-amber-200 border-amber-400/40",
};

export const HydrationConsoleCard: React.FC<HydrationConsoleCardProps> = ({
  onStepCompleted,
  compact = false,
}) => {
  const { showToast } = useToast();
  const [status, setStatus] = useState<HydrationPipelineStatus | null>(null);
  const [scope, setScope] = useState<"all" | "sources" | "metadata">("all");
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(() => {
    api.explore.hydration
      .getStatus()
      .then((res) => setStatus(res))
      .catch(() => null);
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (!status || status.state !== "RUNNING") return;
    const id = window.setInterval(loadStatus, 2500);
    return () => window.clearInterval(id);
  }, [status, loadStatus]);

  const handleToggleRun = async () => {
    if (!status) return;
    setBusy(true);
    try {
      const next =
        status.state === "RUNNING"
          ? await api.explore.hydration.pause()
          : await api.explore.hydration.start(scope);
      setStatus(next);
      showToast(
        next.state === "RUNNING"
          ? "Motor Unificado dos 3 Pilares iniciado em segundo plano."
          : "Hidratação pausada com checkpoint preservado.",
        "info"
      );
      onStepCompleted?.();
    } catch (err: any) {
      showToast(`Erro no motor de hidratação: ${err?.message || "falha"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleSingleStep = async () => {
    setBusy(true);
    try {
      const out = await api.explore.hydration.step(scope);
      setStatus(out.status);
      showToast(
        out.status.last_step_summary || "Passo de hidratação concluído com checkpoint.",
        "success"
      );
      onStepCompleted?.();
    } catch (err: any) {
      showToast(`Falha ao executar passo: ${err?.message || "erro"}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    try {
      const next = await api.explore.hydration.resetCursor("all");
      setStatus(next);
      showToast("Cursores de Bootstrap reiniciados para página 1 / offset 0.", "info");
    } catch (err: any) {
      showToast(`Erro ao reiniciar cursores: ${err?.message || "erro"}`, "error");
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

  return (
    <div
      className={`${
        compact ? "p-4" : "p-5"
      } rounded-2xl bg-surface-elevated border border-cyan-500/25 space-y-4`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h3 className="text-base font-extrabold text-white">
              Motor Unificado dos 3 Pilares (Checkpoint --resume)
            </h3>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-black border ${
                MODE_BADGE_STYLES[status.overall_mode]
              }`}
            >
              {status.overall_mode}
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/5 text-slate-300 border border-white/10">
              IMDb: {status.imdb_backbone_mode} • EZTV: {status.eztv_mode}
            </span>
          </div>
          <p className="text-xs text-slate-300">
            Pilar 1B Presença (YTS + Sidecar) + Pilar 2 JIT On-Demand + Pilar 3 Cascata 6-Níveis
            {status.last_step_summary ? ` • ${status.last_step_summary}` : ""}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Escopo do Motor de Hidratação"
            value={scope}
            onChange={(e) => setScope(e.target.value as "all" | "sources" | "metadata")}
            disabled={busy || isRunning}
            className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
          >
            <option value="all">Todos os 3 Pilares</option>
            <option value="sources">Pilar 1B: Fontes P2P</option>
            <option value="metadata">Pilar 3: Cascata Capas/Sinopses</option>
          </select>

          <button
            type="button"
            disabled={busy}
            onClick={handleToggleRun}
            className={`min-h-[44px] flex items-center gap-2 px-4 rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50 ${
              isRunning
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
            className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-xs font-bold text-white cursor-pointer disabled:opacity-50"
          >
            <StepForward className="w-4 h-4" />
            {busy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : "1 Passo"}
          </button>

          <button
            type="button"
            disabled={busy || isRunning}
            onClick={handleReset}
            title="Reiniciar cursores de Bootstrap para página 1 / offset 0"
            className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-semibold text-slate-300 cursor-pointer disabled:opacity-50"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>
      </div>

      {/* Coverage Progress Bars */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-3 rounded-xl bg-canvas border border-white/10 space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-200">Pilar 3: Capas Canônicas</span>
            <span className="font-black text-emerald-300">{cov.posters_pct}%</span>
          </div>
          <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full bg-emerald-400 transition-all"
              style={{ width: `${Math.min(100, cov.posters_pct)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">
            {cov.with_poster.toLocaleString("pt-BR")} / {cov.total_shows.toLocaleString("pt-BR")}{" "}
            obras ({cov.missing_posters.toLocaleString("pt-BR")} faltando)
          </p>
        </div>

        <div className="p-3 rounded-xl bg-canvas border border-white/10 space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-200">Sinopses Bilíngues (PT/EN)</span>
            <span className="font-black text-sky-300">
              {cov.synopsis_ptbr_pct}% / {cov.synopsis_pct}%
            </span>
          </div>
          <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full bg-sky-400 transition-all"
              style={{ width: `${Math.min(100, Math.max(cov.synopsis_ptbr_pct, cov.synopsis_pct))}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">
            PT-BR: {cov.with_synopsis_ptbr.toLocaleString("pt-BR")} • EN:{" "}
            {cov.with_synopsis.toLocaleString("pt-BR")} • Auto-Heal EZTV: {cov.eztv_missing_meta}{" "}
            pendentes
          </p>
        </div>

        <div className="p-3 rounded-xl bg-canvas border border-white/10 space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-200 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              Cascata 6-Níveis (Atribuição)
            </span>
            <span className="font-black text-amber-200">Passos: {status.steps_executed}</span>
          </div>
          <div className="flex flex-wrap gap-1.5 text-[10px] font-bold">
            <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">
              1.IMDb {prov.imdb}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">
              2.TMDB {prov.tmdb}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">
              3.TVMaze {prov.tvmaze}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">
              4.EZTV {prov.eztv + prov.self_healed_eztv}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">
              5.YTS {prov.yify}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-200">
              6.Wiki/Jikan {prov.open_sources}
            </span>
          </div>
        </div>
      </div>

      {/* Per-Source Resumable Cursors */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {sourceOrder.map((key) => {
          const cur = status.sources[key];
          if (!cur) return null;
          return (
            <div
              key={key}
              className="p-2.5 rounded-xl bg-canvas border border-white/10 flex flex-col justify-between gap-1"
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-xs font-extrabold text-white uppercase">{key}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-black border ${
                    MODE_BADGE_STYLES[cur.mode]
                  }`}
                >
                  {cur.mode}
                </span>
              </div>
              <div className="text-[11px] font-bold text-cyan-300">
                {cur.titles_indexed.toLocaleString("pt-BR")} títulos
              </div>
              <div className="text-[10px] text-slate-400 truncate">
                {key === "yify"
                  ? `Pág ${cur.next_page}/${cur.total_pages}`
                  : key === "eztv"
                    ? `${cur.releases_indexed.toLocaleString("pt-BR")} rel.`
                    : cur.recent_exhausted
                      ? `Sweep @${cur.catalog_sweep_offset}`
                      : `Recent p.${cur.next_page}`}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
