import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Database,
  Plus,
  RefreshCw,
  RotateCcw,
  Settings,
  Sliders,
  Trash2,
  Wifi,
  Zap,
} from "lucide-react";
import {
  ExternalSourceSummary,
  MediaBadgeAction,
  ProviderBadgeAction,
  SchedulerTelemetry,
  SourceAdapterMetadata,
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
  const [adapters, setAdapters] = useState<SourceAdapterMetadata[]>([]);
  const [scheduler, setScheduler] = useState<SchedulerTelemetry | null>(null);

  const [mainstreamMode, setMainstreamMode] = useState<"delta" | "hydrate" | "badges">("delta");
  const [updatingMainstream, setUpdatingMainstream] = useState(false);
  const [syncingSourceKey, setSyncingSourceKey] = useState<string | null>(null);
  const [testingSourceKey, setTestingSourceKey] = useState<string | null>(null);
  const [syncingScheduler, setSyncingScheduler] = useState(false);

  // Expandable source config drawer state
  const [expandedSourceKey, setExpandedSourceKey] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<{
    display_name: string;
    source_kind: string;
    priority: number;
    base_url: string;
    mirrors_text: string;
    site: string;
    api_key: string;
    categories: string;
    browser_search_url: string;
    ttl_hours: number;
  } | null>(null);

  // Add Source Instance form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newAdapterKey, setNewAdapterKey] = useState("torrent_api_py");
  const [newSourceKey, setNewSourceKey] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newSourceKind, setNewSourceKind] = useState("torrent_mirrorable");
  const [newBaseUrl, setNewBaseUrl] = useState("http://127.0.0.1:8009");
  const [newSite, setNewSite] = useState("tgx");
  const [newApiKey, setNewApiKey] = useState("");
  const [newBrowserUrl, setNewBrowserUrl] = useState("");

  const loadTelemetry = useCallback(() => {
    Promise.all([
      api.explore.getMainstreamStats().catch(() => null),
      api.sources.getSummary().catch(() => null),
      api.sources.getAdapters().catch(() => null),
      api.notifications.getSchedulerStatus().catch(() => null),
    ]).then(([ms, src, adp, sched]) => {
      if (ms) setMainstreamStats(ms);
      if (src) setSources(src.sources);
      if (adp) setAdapters(adp.adapters);
      if (sched) setScheduler(sched);

      const hasDegraded = Boolean(
        src?.sources.some((s) => s.status === "degraded" || s.status === "challenge_required")
      );
      onHealthChange?.(hasDegraded ? "degraded" : "healthy");
    });
  }, [onHealthChange]);

  useEffect(() => {
    loadTelemetry();
  }, [loadTelemetry]);

  const handleOpenEditSource = (src: ExternalSourceSummary) => {
    if (expandedSourceKey === src.source_key) {
      setExpandedSourceKey(null);
      setEditDraft(null);
      return;
    }
    const cfg = src.config || {};
    setExpandedSourceKey(src.source_key);
    setEditDraft({
      display_name: src.display_name,
      source_kind: src.source_kind || "torrent_mirrorable",
      priority: src.priority ?? 100,
      base_url: String(cfg.base_url || src.base_url || ""),
      mirrors_text: Array.isArray(cfg.mirrors) ? cfg.mirrors.join(", ") : "",
      site: String(cfg.site || "1337x"),
      api_key: String(cfg.api_key || ""),
      categories: String(cfg.categories || "2000,5000"),
      browser_search_url: String(cfg.browser_search_url || cfg.public_web_Search_url || ""),
      ttl_hours: Number(cfg.ttl_hours || 24),
    });
  };

  const handleSaveSourceConfig = async (src: ExternalSourceSummary) => {
    if (!editDraft) return;
    try {
      const mirrors = editDraft.mirrors_text
        .split(",")
        .map((m) => m.trim())
        .filter(Boolean);
      const nextCfg: Record<string, any> = {
        ...(src.config || {}),
        base_url: editDraft.base_url.trim(),
        mirrors,
        ttl_hours: editDraft.ttl_hours,
      };
      if (src.adapter_key === "torrent_api_py") {
        nextCfg.site = editDraft.site;
        nextCfg.api_key = editDraft.api_key;
        if (editDraft.browser_search_url.trim()) {
          nextCfg.public_web_Search_url = editDraft.browser_search_url.trim();
        }
      } else if (src.adapter_key === "torznab") {
        nextCfg.api_key = editDraft.api_key;
        nextCfg.categories = editDraft.categories;
      } else if (src.adapter_key === "unique_web") {
        nextCfg.api_key = editDraft.api_key;
        nextCfg.browser_search_url = editDraft.browser_search_url.trim();
      }

      await api.sources.updateSource(src.source_key, {
        display_name: editDraft.display_name,
        source_kind: editDraft.source_kind,
        priority: editDraft.priority,
        config: nextCfg,
        clear_cooldown: true,
      });
      showToast(`Configurações de "${editDraft.display_name}" salvas!`, "success");
      setExpandedSourceKey(null);
      setEditDraft(null);
      onDataUpdated?.();
      loadTelemetry();
    } catch (err: any) {
      showToast(err?.message || "Erro ao salvar configuração da fonte", "error");
    }
  };

  const handleToggleSourceEnabled = async (src: ExternalSourceSummary) => {
    try {
      await api.sources.updateSource(src.source_key, { enabled: !src.enabled });
      showToast(
        `Fonte ${src.display_name} ${!src.enabled ? "ativada" : "desativada"}.`,
        "info"
      );
      onDataUpdated?.();
      loadTelemetry();
    } catch {
      showToast("Erro ao alternar status da fonte", "error");
    }
  };

  const handleTestSource = async (sourceKey: string) => {
    setTestingSourceKey(sourceKey);
    try {
      const res = await api.sources.testSource(sourceKey);
      if (res.status === "ok") {
        showToast(
          `Conexão OK (${res.latency_ms}ms) • ${res.releases_found ?? 0} resultados de teste.`,
          "success"
        );
      } else if (res.status === "challenge_required") {
        showToast(`Desafio CAPTCHA detectado (${res.latency_ms}ms): ${res.message}`, "info");
      } else {
        showToast(`Falha no teste (${res.latency_ms}ms): ${res.message || res.status}`, "error");
      }
      loadTelemetry();
    } catch {
      showToast("Erro ao testar conexão com a fonte", "error");
    } finally {
      setTestingSourceKey(null);
    }
  };

  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const config: Record<string, any> = { base_url: newBaseUrl.trim() };
      if (newAdapterKey === "torrent_api_py") {
        config.site = newSite;
        if (newApiKey.trim()) config.api_key = newApiKey.trim();
      } else if (newAdapterKey === "torznab") {
        config.api_key = newApiKey.trim();
      } else if (newAdapterKey === "unique_web") {
        if (newApiKey.trim()) config.api_key = newApiKey.trim();
        if (newBrowserUrl.trim()) config.browser_search_url = newBrowserUrl.trim();
      }

      await api.sources.createSource({
        adapter_key: newAdapterKey,
        source_key: newSourceKey.trim() || newDisplayName.trim(),
        display_name: newDisplayName.trim() || newSourceKey.trim(),
        source_kind: newSourceKind,
        config,
      });
      showToast("Nova fonte adicionada com sucesso!", "success");
      setShowAddForm(false);
      setNewSourceKey("");
      setNewDisplayName("");
      setNewApiKey("");
      onDataUpdated?.();
      loadTelemetry();
    } catch (err: any) {
      showToast(err?.message || "Erro ao criar nova fonte", "error");
    }
  };

  const handleDeleteSource = async (sourceKey: string) => {
    try {
      await api.sources.deleteSource(sourceKey);
      showToast(`Fonte '${sourceKey}' removida.`, "info");
      setExpandedSourceKey(null);
      onDataUpdated?.();
      loadTelemetry();
    } catch (err: any) {
      showToast(err?.message || "Erro ao remover fonte", "error");
    }
  };

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
            Monitoramento Dual-SSOT (mainstream.db + sources.db), plugins de fontes externas e preferências
          </p>
        </div>

        <span
          className={`self-start inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${syncState === "synced"
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

      {/* SECTION 1: Dual-SSOT Health, Plugins & Sync */}
      <section aria-labelledby="dual-ssot-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-emerald-400" />
          <h2 id="dual-ssot-heading" className="text-lg font-extrabold text-white">
            Saúde Dual-SSOT &amp; Plugins de Fontes Externas
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
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

          {/* External Sources DB + Dynamic Plugins Card */}
          <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Zap className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-base font-bold text-white">
                    Base de Recursos &amp; Plugins (sources.db)
                  </h3>
                </div>
                <p className="text-xs text-slate-300 mt-1">
                  EZTV base + plugins 1:N (Torrent-Api-py, Torznab, YIFY, Fontes Web Únicas)
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddForm((prev) => !prev)}
                  className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                  + Adicionar Fonte
                </button>
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
            </div>

            {/* + Adicionar Fonte Drawer */}
            {showAddForm && (
              <form
                onSubmit={handleCreateSource}
                className="p-4 rounded-xl bg-canvas border border-sky-500/40 space-y-3"
              >
                <div className="text-xs font-extrabold uppercase tracking-wider text-sky-300">
                  Instanciar Novo Plugin de Fonte Externa
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-300 mb-1">
                      Tipo de Adapter (Plugin)
                    </label>
                    <select
                      value={newAdapterKey}
                      onChange={(e) => {
                        const ak = e.target.value;
                        setNewAdapterKey(ak);
                        const found = adapters.find((a) => a.adapter_key === ak);
                        if (found) setNewSourceKind(found.default_source_kind);
                        if (ak === "torznab") setNewBaseUrl("http://127.0.0.1:9696/1/api");
                        else if (ak === "torrent_api_py") setNewBaseUrl("http://127.0.0.1:8009");
                        else if (ak === "unique_web") setNewBaseUrl("https://example.org/api/search");
                      }}
                      className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                    >
                      {adapters
                        .filter((a) => a.adapter_key !== "eztv")
                        .map((a) => (
                          <option key={a.adapter_key} value={a.adapter_key}>
                            {a.display_name}
                          </option>
                        ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-300 mb-1">
                      Comportamento de Fallback
                    </label>
                    <select
                      value={newSourceKind}
                      onChange={(e) => setNewSourceKind(e.target.value)}
                      className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                    >
                      <option value="torrent_mirrorable">
                        Torrent Multi-Mirror (Rotação Automática)
                      </option>
                      <option value="unique_web_source">
                        Fonte Web Única (Aviso Manual CAPTCHA)
                      </option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-300 mb-1">
                      Identificador (source_key)
                    </label>
                    <input
                      type="text"
                      required
                      value={newSourceKey}
                      onChange={(e) => setNewSourceKey(e.target.value)}
                      placeholder="Ex: tgx, nyaasi, prowlarr_4k..."
                      className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-300 mb-1">
                      Nome de Exibição
                    </label>
                    <input
                      type="text"
                      required
                      value={newDisplayName}
                      onChange={(e) => setNewDisplayName(e.target.value)}
                      placeholder="Ex: TorrentGalaxy, Prowlarr..."
                      className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] font-bold text-slate-300 mb-1">
                      URL Base (http:// ou https://)
                    </label>
                    <input
                      type="url"
                      required
                      value={newBaseUrl}
                      onChange={(e) => setNewBaseUrl(e.target.value)}
                      className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                    />
                  </div>
                  {newAdapterKey === "torrent_api_py" && (
                    <div>
                      <label className="block text-[11px] font-bold text-slate-300 mb-1">
                        Site no Torrent-Api-py
                      </label>
                      <select
                        value={newSite}
                        onChange={(e) => setNewSite(e.target.value)}
                        className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                      >
                        <option value="tgx">TorrentGalaxy (tgx)</option>
                        <option value="nyaasi">Nyaa.si (nyaasi)</option>
                        <option value="bitsearch">BitSearch (bitsearch)</option>
                        <option value="glodls">GloDLS (glodls)</option>
                        <option value="magnetdl">MagnetDL (magnetdl)</option>
                        <option value="limetorrent">LimeTorrents (limetorrent)</option>
                        <option value="torlock">Torlock (torlock)</option>
                        <option value="kickass">Kickass (kickass)</option>
                        <option value="zooqle">Zooqle (zooqle)</option>
                        <option value="yts">YTS Sidecar (yts)</option>
                        <option value="1337x">1337x (Legado / Cloudflare)</option>
                        <option value="piratebay">ThePirateBay (Legado / Cloudflare)</option>
                      </select>
                    </div>
                  )}
                  {(newAdapterKey === "torznab" ||
                    newAdapterKey === "torrent_api_py" ||
                    newAdapterKey === "unique_web") && (
                      <div>
                        <label className="block text-[11px] font-bold text-slate-300 mb-1">
                          API Key / Token (Secreto)
                        </label>
                        <input
                          type="password"
                          value={newApiKey}
                          onChange={(e) => setNewApiKey(e.target.value)}
                          placeholder="Opcional (mascarado na API)"
                          className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                        />
                      </div>
                    )}
                  {newAdapterKey === "unique_web" && (
                    <div className="sm:col-span-2">
                      <label className="block text-[11px] font-bold text-slate-300 mb-1">
                        URL Manual do Navegador p/ CAPTCHA (use {"{query}"})
                      </label>
                      <input
                        type="url"
                        value={newBrowserUrl}
                        onChange={(e) => setNewBrowserUrl(e.target.value)}
                        placeholder="https://example.org/search?q={query}"
                        className="w-full min-h-[40px] bg-surface-elevated border border-white/15 rounded-lg px-2.5 text-xs text-white"
                      />
                    </div>
                  )}
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAddForm(false)}
                    className="min-h-[40px] px-3 rounded-lg bg-white/10 text-xs font-bold text-slate-200 cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="min-h-[40px] px-4 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-extrabold cursor-pointer"
                  >
                    Salvar Nova Fonte
                  </button>
                </div>
              </form>
            )}

            {/* Registered Source Instances List */}
            <div className="space-y-2.5">
              {sources.map((src) => {
                const isExpanded = expandedSourceKey === src.source_key;
                const isChallenge = src.status === "challenge_required";
                const isDegraded = src.status === "degraded" || src.status === "cooldown";

                return (
                  <div
                    key={src.source_key}
                    className="rounded-xl bg-canvas border border-white/10 overflow-hidden"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 p-3">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <input
                            type="checkbox"
                            checked={src.enabled}
                            onChange={() => handleToggleSourceEnabled(src)}
                            aria-label={`Ativar ou desativar ${src.display_name}`}
                            className="accent-emerald-400 cursor-pointer"
                          />
                          {isChallenge || isDegraded ? (
                            <AlertTriangle className="w-4 h-4 text-amber-400" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          )}
                          <span className="text-sm font-bold text-white">
                            {src.display_name}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] font-mono text-slate-300">
                            {src.adapter_key || src.kind}
                          </span>
                          <span className="text-[11px] text-slate-300">
                            ({src.total_titles.toLocaleString("pt-BR")} títulos •{" "}
                            {src.total_releases.toLocaleString("pt-BR")} releases)
                          </span>
                        </div>
                        {src.last_error && (
                          <p className="text-[11px] text-amber-300">{src.last_error}</p>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          disabled={testingSourceKey === src.source_key}
                          onClick={() => handleTestSource(src.source_key)}
                          className="min-h-[40px] px-2.5 rounded-lg bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-sky-300 flex items-center gap-1 cursor-pointer"
                          title="Testar conectividade da fonte"
                        >
                          <Wifi className="w-3.5 h-3.5" />
                          {testingSourceKey === src.source_key ? "Testando..." : "Testar"}
                        </button>

                        <button
                          type="button"
                          disabled={syncingSourceKey !== null}
                          onClick={() => handleSyncSource(src.source_key)}
                          className="min-h-[40px] px-2.5 rounded-lg bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-100 disabled:opacity-50 cursor-pointer"
                        >
                          {syncingSourceKey === src.source_key ? "Sync..." : "Sync"}
                        </button>

                        <button
                          type="button"
                          onClick={() => handleOpenEditSource(src)}
                          aria-expanded={isExpanded}
                          className="min-h-[40px] px-2.5 rounded-lg bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 flex items-center gap-1 cursor-pointer"
                        >
                          <span>Config</span>
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Expanded Instance Configuration Drawer (DEC-005) */}
                    {isExpanded && editDraft && (
                      <div className="p-4 bg-surface-elevated/90 border-t border-white/10 space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-[11px] font-bold text-slate-300 mb-1">
                              Nome de Exibição
                            </label>
                            <input
                              type="text"
                              value={editDraft.display_name}
                              onChange={(e) =>
                                setEditDraft({ ...editDraft, display_name: e.target.value })
                              }
                              className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-bold text-slate-300 mb-1">
                              Política de Fallback
                            </label>
                            <select
                              value={editDraft.source_kind}
                              onChange={(e) =>
                                setEditDraft({ ...editDraft, source_kind: e.target.value })
                              }
                              className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
                            >
                              <option value="torrent_mirrorable">
                                Torrent Multi-Mirror (Rotação Automática)
                              </option>
                              <option value="unique_web_source">
                                Fonte Web Única (Aviso CAPTCHA Manual)
                              </option>
                            </select>
                          </div>
                          <div className="sm:col-span-2">
                            <label className="block text-[11px] font-bold text-slate-300 mb-1">
                              URL Principal
                            </label>
                            <input
                              type="url"
                              value={editDraft.base_url}
                              onChange={(e) =>
                                setEditDraft({ ...editDraft, base_url: e.target.value })
                              }
                              className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
                            />
                          </div>
                          <div className="sm:col-span-2">
                            <label className="block text-[11px] font-bold text-slate-300 mb-1">
                              Mirrors Alternativos (separados por vírgula)
                            </label>
                            <input
                              type="text"
                              value={editDraft.mirrors_text}
                              onChange={(e) =>
                                setEditDraft({ ...editDraft, mirrors_text: e.target.value })
                              }
                              placeholder="https://mirror1.org, https://mirror2.org"
                              className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
                            />
                          </div>
                          {(src.adapter_key === "torznab" ||
                            src.adapter_key === "torrent_api_py" ||
                            src.adapter_key === "unique_web") && (
                              <div>
                                <label className="block text-[11px] font-bold text-slate-300 mb-1">
                                  API Key / Token Secreto (preservado se mantiver ••••)
                                </label>
                                <input
                                  type="password"
                                  value={editDraft.api_key}
                                  onChange={(e) =>
                                    setEditDraft({ ...editDraft, api_key: e.target.value })
                                  }
                                  placeholder="•••• (não alterado)"
                                  className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
                                />
                              </div>
                            )}
                          <div>
                            <label className="block text-[11px] font-bold text-slate-300 mb-1">
                              TTL do Cache Lazy (Horas)
                            </label>
                            <input
                              type="number"
                              min={1}
                              max={720}
                              value={editDraft.ttl_hours}
                              onChange={(e) =>
                                setEditDraft({
                                  ...editDraft,
                                  ttl_hours: Number(e.target.value) || 24,
                                })
                              }
                              className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
                            />
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                          {src.source_key !== "eztv" ? (
                            <button
                              type="button"
                              onClick={() => handleDeleteSource(src.source_key)}
                              className="min-h-[40px] px-3 rounded-lg bg-rose-950/70 hover:bg-rose-900 text-rose-200 border border-rose-500/40 text-xs font-bold flex items-center gap-1.5 cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                              Remover Fonte
                            </button>
                          ) : (
                            <span className="text-[11px] text-slate-400">
                              Catálogo Base Protegido
                            </span>
                          )}

                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setExpandedSourceKey(null)}
                              className="min-h-[40px] px-3 rounded-lg bg-white/10 text-xs font-bold text-slate-200 cursor-pointer"
                            >
                              Fechar
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSaveSourceConfig(src)}
                              className="min-h-[40px] px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-extrabold cursor-pointer"
                            >
                              Salvar Configuração
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
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
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors min-h-[44px] ${preferences.badge_provider_action === opt.value
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
                    desc: "Lista magnets, torrents e links agrupados por provedor (EZTV, YIFY, 1337x...).",
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
                  className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors min-h-[44px] ${preferences.badge_media_action === opt.value
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
