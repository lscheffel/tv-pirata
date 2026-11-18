import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Database,
  RefreshCw,
  RotateCcw,
  Settings,
  Sliders,
  Zap,
  AlertTriangle,
} from "lucide-react";
import {
  ExternalSourceSummary,
  MediaBadgeAction,
  ProviderBadgeAction,
  SchedulerTelemetry,
} from "../types";
import { api } from "../services/api";
import { useExplorePreferences } from "../context/PreferencesContext";
import { useToast } from "../context/ToastContext";

interface StatusConfigViewProps {
  onHealthChange?: (health: "healthy" | "syncing" | "degraded") => void;
  onDataUpdated?: () => void;
}

export const StatusConfigView: React.FC<StatusConfigViewProps> = ({
  onHealthChange,
  onDataUpdated,
}) => {
  const { showToast } = useToast();
  const { preferences, syncState, updatePreferences, resetPreferences } =
    useExplorePreferences();

  const [mainstreamStats, setMainstreamStats] = useState<{
    total_titles: number;
    total_episodes: number;
    hydrated_titles: number;
    eztv_badged_titles: number;
  } | null>(null);
  const [sources, setSources] = useState<ExternalSourceSummary[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerTelemetry | null>(null);

  const [mainstreamMode, setMainstreamMode] = useState<"delta" | "hydrate" | "badges">("delta");
  const [updatingMainstream, setUpdatingMainstream] = useState(false);
  const [syncingSourceKey, setSyncingSourceKey] = useState<string | null>(null);
  const [syncingScheduler, setSyncingScheduler] = useState(false);

  const loadTelemetry = useCallback(() => {
    Promise.all([
      api.explore.getMainstreamStats().catch(() => null),
      api.sources.getSummary().catch(() => null),
      api.notifications.getSchedulerStatus().catch(() => null),
    ]).then(([ms, src, sched]) => {
      if (ms) setMainstreamStats(ms);
      if (src) setSources(src.sources);
      if (sched) setScheduler(sched);

      const hasDegraded = Boolean(src?.sources.some((s) => s.status === "degraded"));
      onHealthChange?.(hasDegraded ? "degraded" : "healthy");
    });
  }, [onHealthChange]);

  useEffect(() => {
    loadTelemetry();
  }, [loadTelemetry]);

  const handleUpdateMainstream = async () => {
    setUpdatingMainstream(true);
    onHealthChange?.("syncing");
    showToast("Atualizando Base Canônica (data/mainstream.db)...", "info");
    try {
      const res = await api.explore.updateMainstream(mainstreamMode, 25);
      setMainstreamStats(res.stats);
      showToast(
        `Base Canônica atualizada! ${res.titles_hydrated} hidratados, ${res.badges_synced} selos cruzados.`,
        "success"
      );
      onDataUpdated?.();
      loadTelemetry();
    } catch {
      onHealthChange?.("degraded");
      showToast("Falha ao atualizar Base Canônica (mainstream.db)", "error");
    } finally {
      setUpdatingMainstream(false);
    }
  };

  const handleSyncSource = async (sourceKey: string) => {
    setSyncingSourceKey(sourceKey);
    onHealthChange?.("syncing");
    showToast(`Sincronizando fonte ${sourceKey.toUpperCase()} (data/sources.db)...`, "info");
    try {
      await api.sources.sync(sourceKey, 5, true);
      showToast(`Fonte ${sourceKey.toUpperCase()} sincronizada!`, "success");
      onDataUpdated?.();
      loadTelemetry();
    } catch {
      onHealthChange?.("degraded");
      showToast(`Erro ao sincronizar ${sourceKey.toUpperCase()}`, "error");
    } finally {
      setSyncingSourceKey(null);
    }
  };

  const handleTriggerScheduler = async () => {
    setSyncingScheduler(true);
    onHealthChange?.("syncing");
    try {
      const res = await api.notifications.triggerSync();
      showToast(
        `Ciclo em background concluído (${res.telemetry?.new_releases ?? 0} novos releases).`,
        "success"
      );
      loadTelemetry();
    } catch {
      showToast("Erro ao disparar ciclo de background", "error");
    } finally {
      setSyncingScheduler(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 lg:pt-24 pb-16 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <Settings className="w-7 h-7 text-brand-red" />
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Status, Sincronização &amp; Configurações
            </h1>
          </div>
          <p className="text-sm text-slate-300 mt-1">
            Monitoramento Dual-SSOT (mainstream.db + sources.db) e comportamento interativo do catálogo
          </p>
        </div>

        <span
          className={`self-start inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${
            syncState === "synced"
              ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
              : syncState === "syncing"
                ? "bg-amber-950/60 border-amber-500/40 text-amber-300"
                : "bg-surface-elevated border-white/15 text-slate-300"
          }`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Preferências:{" "}
          {syncState === "synced"
            ? "Sincronizadas (localStorage + mainstream.db)"
            : syncState === "syncing"
              ? "Salvando..."
              : "Cache local ativo"}
        </span>
      </div>

      {/* SECTION 1: Dual-SSOT Health & Sync */}
      <section aria-labelledby="dual-ssot-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-emerald-400" />
          <h2 id="dual-ssot-heading" className="text-lg font-extrabold text-white">
            Saúde &amp; Sincronização Dual-SSOT
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Canonical DB Card */}
          <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-brand-red" />
                  <h3 className="text-base font-bold text-white">
                    Base Canônica (mainstream.db)
                  </h3>
                </div>
                <p className="text-xs text-slate-300 mt-1">
                  IMDb Universal + TMDB PT-BR + TVMaze + Preferências
                </p>
              </div>
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                Camada 1
              </span>
            </div>

            {mainstreamStats && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                <div className="p-2.5 rounded-xl bg-canvas border border-white/5">
                  <div className="text-sm font-black text-white">
                    {mainstreamStats.total_titles.toLocaleString("pt-BR")}
                  </div>
                  <div className="text-[11px] text-slate-300">Títulos</div>
                </div>
                <div className="p-2.5 rounded-xl bg-canvas border border-white/5">
                  <div className="text-sm font-black text-white">
                    {mainstreamStats.total_episodes.toLocaleString("pt-BR")}
                  </div>
                  <div className="text-[11px] text-slate-300">Episódios</div>
                </div>
                <div className="p-2.5 rounded-xl bg-canvas border border-white/5">
                  <div className="text-sm font-black text-sky-300">
                    {mainstreamStats.hydrated_titles.toLocaleString("pt-BR")}
                  </div>
                  <div className="text-[11px] text-slate-300">Hidratados</div>
                </div>
                <div className="p-2.5 rounded-xl bg-canvas border border-white/5">
                  <div className="text-sm font-black text-emerald-300">
                    {mainstreamStats.eztv_badged_titles.toLocaleString("pt-BR")}
                  </div>
                  <div className="text-[11px] text-slate-300">Com Mídia</div>
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <select
                aria-label="Modo de atualização da base canônica"
                value={mainstreamMode}
                onChange={(e) =>
                  setMainstreamMode(e.target.value as "delta" | "hydrate" | "badges")
                }
                disabled={updatingMainstream}
                className="min-h-[44px] flex-1 bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
              >
                <option value="delta">Delta Completo (Selos + Hidratação)</option>
                <option value="badges">Sincronizar Selos Cruzados</option>
                <option value="hydrate">Hidratar TVMaze / TMDB (Lote 25)</option>
              </select>
              <button
                type="button"
                disabled={updatingMainstream}
                onClick={handleUpdateMainstream}
                className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-brand-red hover:bg-brand-redHover text-white text-xs font-bold shadow-cinema-glow disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw
                  className={`w-4 h-4 ${updatingMainstream ? "animate-spin" : ""}`}
                />
                {updatingMainstream ? "Atualizando..." : "Atualizar Base Canônica"}
              </button>
            </div>
          </div>

          {/* External Sources DB + Auto-Sync Card */}
          <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-base font-bold text-white">
                    Base de Recursos (sources.db)
                  </h3>
                </div>
                <p className="text-xs text-slate-300 mt-1">
                  Indexadores multi-provedor e serviço de auto-sync em background
                </p>
              </div>
              <button
                type="button"
                disabled={syncingSourceKey !== null}
                onClick={() => handleSyncSource("all")}
                className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${syncingSourceKey === "all" ? "animate-spin" : ""}`}
                />
                Sincronizar Todas
              </button>
            </div>

            <div className="space-y-2">
              {sources.map((src) => (
                <div
                  key={src.source_key}
                  className="flex items-center justify-between gap-3 p-3 rounded-xl bg-canvas border border-white/10"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      {src.status === "degraded" ? (
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      )}
                      <span className="text-sm font-bold text-white">{src.display_name}</span>
                      <span className="text-[11px] text-slate-300">
                        ({src.total_titles.toLocaleString("pt-BR")} títulos •{" "}
                        {src.total_releases.toLocaleString("pt-BR")} releases)
                      </span>
                    </div>
                    {src.last_error && (
                      <p className="text-[11px] text-amber-300 mt-0.5">{src.last_error}</p>
                    )}
                  </div>

                  <button
                    type="button"
                    disabled={syncingSourceKey !== null}
                    onClick={() => handleSyncSource(src.source_key)}
                    className="min-h-[44px] px-3 rounded-lg bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-100 disabled:opacity-50 cursor-pointer"
                  >
                    {syncingSourceKey === src.source_key ? "Sincronizando..." : "Sincronizar"}
                  </button>
                </div>
              ))}
            </div>

            {scheduler && (
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/10 text-xs text-slate-300">
                <span>
                  Auto-Sync: <strong className="text-white">{scheduler.status}</strong> (intervalo{" "}
                  {Math.round(scheduler.interval_seconds / 60)}m)
                </span>
                <button
                  type="button"
                  disabled={syncingScheduler}
                  onClick={handleTriggerScheduler}
                  className="min-h-[44px] px-3 rounded-xl bg-white/10 hover:bg-white/15 text-white font-semibold cursor-pointer"
                >
                  {syncingScheduler ? "Executando..." : "Executar Ciclo Agora"}
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* SECTION 2: Interactive Badge & Filter Preferences */}
      <section aria-labelledby="interactive-prefs-heading" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-5 h-5 text-sky-400" />
            <h2 id="interactive-prefs-heading" className="text-lg font-extrabold text-white">
              Comportamento Interativo do Catálogo &amp; Badges
            </h2>
          </div>

          <button
            type="button"
            onClick={() => {
              resetPreferences();
              showToast("Preferências restauradas para o padrão canônico", "info");
            }}
            className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5 text-brand-red" />
            Restaurar Padrões
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Provider Badge Click Action */}
          <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-3">
            <div>
              <h3 className="text-sm font-bold text-white">
                Ação ao clicar na Badge de Streaming (ex: Netflix, Max)
              </h3>
              <p className="text-xs text-slate-300 mt-0.5">
                Define o comportamento das badges empilhadas sobre o pôster no ShowCard.
              </p>
            </div>

            <div className="space-y-2" role="radiogroup" aria-label="Ação de clique na badge de streaming">
              {(
                [
                  {
                    value: "filter_provider",
                    title: "Filtrar catálogo por este provedor",
                    desc: "Aplica o filtro de streaming correspondente no Explorar.",
                  },
                  {
                    value: "open_details",
                    title: "Abrir detalhes completos da obra",
                    desc: "Abre o ShowDetailModal diretamente na ficha da obra.",
                  },
                  {
                    value: "open_provider_info",
                    title: "Exibir disponibilidade e detalhes",
                    desc: "Mostra toast de disponibilidade e abre o modal de detalhes.",
                  },
                ] as Array<{ value: ProviderBadgeAction; title: string; desc: string }>
              ).map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors min-h-[44px] ${
                    preferences.badge_provider_action === opt.value
                      ? "bg-brand-red/15 border-brand-red text-white"
                      : "bg-canvas border-white/10 text-slate-300 hover:border-white/25"
                  }`}
                >
                  <input
                    type="radio"
                    name="badge_provider_action"
                    checked={preferences.badge_provider_action === opt.value}
                    onChange={() =>
                      updatePreferences({ badge_provider_action: opt.value })
                    }
                    className="mt-1 accent-brand-red"
                  />
                  <div>
                    <div className="text-xs font-bold text-white">{opt.title}</div>
                    <div className="text-[11px] text-slate-300">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Media Badge Click Action */}
          <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-3">
            <div>
              <h3 className="text-sm font-bold text-white">
                Ação ao clicar na Badge Media (abaixo da nota IMDb)
              </h3>
              <p className="text-xs text-slate-300 mt-0.5">
                Define o comportamento ao clicar no indicador unificado de magnets/torrents/links.
              </p>
            </div>

            <div className="space-y-2" role="radiogroup" aria-label="Ação de clique na badge Media">
              {(
                [
                  {
                    value: "open_sources_modal",
                    title: "Abrir modal de Fontes de Mídia",
                    desc: "Lista magnets, torrents e links agrupados por provedor (EZTV, YIFY, 1337x).",
                  },
                  {
                    value: "filter_has_media",
                    title: "Filtrar títulos com mídia disponível",
                    desc: "Restringe a grade do Explorar apenas a obras presentes em sources.db.",
                  },
                  {
                    value: "open_details",
                    title: "Abrir ficha completa da obra",
                    desc: "Abre o ShowDetailModal completo com sinopse e episódios.",
                  },
                ] as Array<{ value: MediaBadgeAction; title: string; desc: string }>
              ).map((opt) => (
                <label
                  key={opt.value}
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors min-h-[44px] ${
                    preferences.badge_media_action === opt.value
                      ? "bg-emerald-500/15 border-emerald-400 text-white"
                      : "bg-canvas border-white/10 text-slate-300 hover:border-white/25"
                  }`}
                >
                  <input
                    type="radio"
                    name="badge_media_action"
                    checked={preferences.badge_media_action === opt.value}
                    onChange={() => updatePreferences({ badge_media_action: opt.value })}
                    className="mt-1 accent-emerald-400"
                  />
                  <div>
                    <div className="text-xs font-bold text-white">{opt.title}</div>
                    <div className="text-[11px] text-slate-300">{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Hybrid Filter Engine Toggles */}
        <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="flex items-start gap-3 p-3 rounded-xl bg-canvas border border-white/10 cursor-pointer min-h-[44px]">
            <input
              type="checkbox"
              checked={preferences.auto_apply_filters}
              onChange={(e) => updatePreferences({ auto_apply_filters: e.target.checked })}
              className="mt-1 accent-brand-red"
            />
            <div>
              <div className="text-xs font-bold text-white">
                Auto-aplicar filtros avançados
              </div>
              <div className="text-[11px] text-slate-300">
                Quando desativado (padrão híbrido), usa o botão &quot;Aplicar Filtros&quot; no painel booleano.
              </div>
            </div>
          </label>

          <label className="flex items-start gap-3 p-3 rounded-xl bg-canvas border border-white/10 cursor-pointer min-h-[44px]">
            <input
              type="checkbox"
              checked={preferences.show_all_genres}
              onChange={(e) => updatePreferences({ show_all_genres: e.target.checked })}
              className="mt-1 accent-brand-red"
            />
            <div>
              <div className="text-xs font-bold text-white">
                Exibir todos os 31 gêneros por padrão
              </div>
              <div className="text-[11px] text-slate-300">
                Desmarcado exibe os top-10 gêneros iniciais para reduzir carga visual.
              </div>
            </div>
          </label>

          <label className="flex items-start gap-3 p-3 rounded-xl bg-canvas border border-white/10 cursor-pointer min-h-[44px]">
            <input
              type="checkbox"
              checked={preferences.filter_panel_expanded}
              onChange={(e) => updatePreferences({ filter_panel_expanded: e.target.checked })}
              className="mt-1 accent-brand-red"
            />
            <div>
              <div className="text-xs font-bold text-white">
                Abrir painel booleano expandido
              </div>
              <div className="text-[11px] text-slate-300">
                Mantém o accordion de filtros avançados aberto ao entrar no Explorar.
              </div>
            </div>
          </label>
        </div>
      </section>
    </div>
  );
};
