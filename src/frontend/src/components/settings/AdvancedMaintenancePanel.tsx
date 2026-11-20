import React, { useState } from "react";
import { Clock, Database, RefreshCw, RotateCcw, Zap } from "lucide-react";
import { SchedulerTelemetry } from "../../types";
import { api } from "../../services/api";
import { useToast } from "../../context/ToastContext";

interface AdvancedMaintenancePanelProps {
  mainstreamStats: {
    total_titles: number;
    total_episodes: number;
    hydrated_titles: number;
    eztv_badged_titles: number;
  } | null;
  scheduler: SchedulerTelemetry | null;
  onRefresh: () => void;
  onDataUpdated?: () => void;
}

export const AdvancedMaintenancePanel: React.FC<AdvancedMaintenancePanelProps> = ({
  mainstreamStats,
  scheduler,
  onRefresh,
  onDataUpdated,
}) => {
  const { showToast } = useToast();
  const [syncingBadges, setSyncingBadges] = useState(false);
  const [triggeringSched, setTriggeringSched] = useState(false);
  const [resetting, setResetting] = useState(false);

  const handleSyncBadges = async () => {
    setSyncingBadges(true);
    try {
      const res = await api.explore.updateMainstream("badges", 25);
      showToast(`${res.badges_synced} selos cruzados atualizados.`, "success");
      onDataUpdated?.();
      onRefresh();
    } catch {
      showToast("Erro ao sincronizar selos cruzados.", "error");
    } finally {
      setSyncingBadges(false);
    }
  };

  const handleTriggerScheduler = async () => {
    setTriggeringSched(true);
    try {
      const res = await api.notifications.triggerSync();
      showToast(
        `Verificação da biblioteca concluída (${res.telemetry?.new_releases ?? 0} novidades).`,
        "success"
      );
      onRefresh();
    } catch {
      showToast("Erro ao verificar novos episódios da biblioteca.", "error");
    } finally {
      setTriggeringSched(false);
    }
  };

  const handleResetCursors = async () => {
    setResetting(true);
    try {
      await api.explore.hydration.resetCursor("all");
      showToast("Marcadores de varredura inicial reiniciados.", "info");
      onRefresh();
    } catch {
      showToast("Erro ao reiniciar marcadores.", "error");
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-extrabold text-white">Avançado &amp; Manutenção</h2>
        <p className="text-xs text-slate-300 mt-0.5">
          Agendador periódico da biblioteca, manutenção pontual de selos e indicadores do banco.
        </p>
      </div>

      {/* Auto-Sync Scheduler */}
      <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-sky-400" />
            <span className="text-sm font-bold text-white">
              Verificação Automática da Minha Biblioteca
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Status: {scheduler?.enabled ? "Ativo" : "Desativado"} • Intervalo a cada{" "}
            {Math.round((scheduler?.interval_seconds || 3600) / 60)} min
            {scheduler?.last_run_at
              ? ` • Última execução: ${new Date(scheduler.last_run_at).toLocaleString("pt-BR")}`
              : ""}
          </p>
        </div>

        <button
          type="button"
          disabled={triggeringSched}
          onClick={handleTriggerScheduler}
          className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-sky-600 hover:bg-sky-500 text-xs font-bold text-white cursor-pointer disabled:opacity-50 shrink-0"
        >
          <Zap className={`w-4 h-4 ${triggeringSched ? "animate-pulse" : ""}`} />
          Verificar Biblioteca Agora
        </button>
      </div>

      {/* Maintenance Actions */}
      <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-3">
        <div className="text-sm font-bold text-white">Ações de Manutenção</div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={syncingBadges}
            onClick={handleSyncBadges}
            className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-bold text-white cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${syncingBadges ? "animate-spin" : ""}`} />
            Reconciliar Selos de Disponibilidade
          </button>

          <button
            type="button"
            disabled={resetting}
            onClick={handleResetCursors}
            className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-canvas hover:bg-rose-500/15 border border-white/15 hover:border-rose-500/35 text-xs font-bold text-slate-200 cursor-pointer disabled:opacity-50"
          >
            <RotateCcw className="w-4 h-4" />
            Reiniciar Varredura Inicial das Fontes
          </button>
        </div>
      </div>

      {/* Technical DB Counters (Secondary) */}
      {mainstreamStats && (
        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-white">
            <Database className="w-4 h-4 text-slate-400" />
            Resumo do Armazenamento Local
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
            <div className="p-3 rounded-xl bg-canvas border border-white/5">
              <div className="text-sm font-black text-white">
                {mainstreamStats.total_titles.toLocaleString("pt-BR")}
              </div>
              <div className="text-[11px] text-slate-400">Obras Catalogadas</div>
            </div>
            <div className="p-3 rounded-xl bg-canvas border border-white/5">
              <div className="text-sm font-black text-white">
                {mainstreamStats.total_episodes.toLocaleString("pt-BR")}
              </div>
              <div className="text-[11px] text-slate-400">Episódios</div>
            </div>
            <div className="p-3 rounded-xl bg-canvas border border-white/5">
              <div className="text-sm font-black text-sky-300">
                {mainstreamStats.hydrated_titles.toLocaleString("pt-BR")}
              </div>
              <div className="text-[11px] text-slate-400">Com Metadados</div>
            </div>
            <div className="p-3 rounded-xl bg-canvas border border-white/5">
              <div className="text-sm font-black text-emerald-300">
                {mainstreamStats.eztv_badged_titles.toLocaleString("pt-BR")}
              </div>
              <div className="text-[11px] text-slate-400">Com Fontes Ativas</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
