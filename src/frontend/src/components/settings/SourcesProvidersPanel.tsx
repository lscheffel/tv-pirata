import React, { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Plus,
  RefreshCw,
  Settings2,
  Trash2,
  Wifi,
  X,
} from "lucide-react";
import { ExternalSourceSummary, SourceAdapterMetadata } from "../../types";
import { api } from "../../services/api";
import { useToast } from "../../context/ToastContext";

interface SourcesProvidersPanelProps {
  sources: ExternalSourceSummary[];
  adapters: SourceAdapterMetadata[];
  onRefresh: () => void;
  onDataUpdated?: () => void;
  onHealthChange?: (health: "healthy" | "syncing" | "degraded") => void;
}

interface EditDraft {
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
}

function getFriendlyStatus(src: ExternalSourceSummary): { label: string; badge: string } {
  if (!src.enabled) {
    return { label: "Desativada", badge: "bg-slate-500/20 text-slate-300 border-slate-500/30" };
  }
  if (src.status === "challenge_required") {
    return {
      label: "Requer verificação",
      badge: "bg-amber-500/20 text-amber-200 border-amber-400/40",
    };
  }
  if (src.status === "degraded") {
    return { label: "Instável", badge: "bg-rose-500/20 text-rose-200 border-rose-400/40" };
  }
  if (src.status === "cooldown") {
    return { label: "Em pausa", badge: "bg-amber-500/20 text-amber-200 border-amber-400/40" };
  }
  return { label: "Ativa", badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/35" };
}

export const SourcesProvidersPanel: React.FC<SourcesProvidersPanelProps> = ({
  sources,
  adapters,
  onRefresh,
  onDataUpdated,
  onHealthChange,
}) => {
  const { showToast } = useToast();
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [syncingKey, setSyncingKey] = useState<string | null>(null);

  const [editingSrc, setEditingSrc] = useState<ExternalSourceSummary | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft | null>(null);

  const [showAddModal, setShowAddModal] = useState(false);
  const [newAdapterKey, setNewAdapterKey] = useState("torrent_api_py");
  const [newSourceKey, setNewSourceKey] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const newSourceKind = "torrent_mirrorable";
  const [newBaseUrl, setNewBaseUrl] = useState("http://127.0.0.1:8009");
  const [newSite, setNewSite] = useState("tgx");
  const [newApiKey, setNewApiKey] = useState("");
  const [newBrowserUrl, setNewBrowserUrl] = useState("");

  const openEditModal = (src: ExternalSourceSummary) => {
    const cfg = src.config || {};
    setEditingSrc(src);
    setEditDraft({
      display_name: src.display_name,
      source_kind: src.source_kind || "torrent_mirrorable",
      priority: src.priority ?? 100,
      base_url: String(cfg.base_url || src.base_url || ""),
      mirrors_text: Array.isArray(cfg.mirrors) ? cfg.mirrors.join(", ") : "",
      site: String(cfg.site || "tgx"),
      api_key: String(cfg.api_key || ""),
      categories: String(cfg.categories || "2000,5000"),
      browser_search_url: String(cfg.browser_search_url || cfg.public_web_Search_url || ""),
      ttl_hours: Number(cfg.ttl_hours || 24),
    });
  };

  const handleToggleEnabled = async (src: ExternalSourceSummary) => {
    try {
      await api.sources.updateSource(src.source_key, { enabled: !src.enabled });
      showToast(
        `${src.display_name} ${!src.enabled ? "ativada" : "desativada"}.`,
        "info"
      );
      onDataUpdated?.();
      onRefresh();
    } catch {
      showToast("Não foi possível alterar o status da fonte.", "error");
    }
  };

  const handleTest = async (sourceKey: string) => {
    setTestingKey(sourceKey);
    try {
      const res = await api.sources.testSource(sourceKey);
      if (res.status === "ok") {
        showToast(
          `Conexão OK (${res.latency_ms}ms • ${res.releases_found ?? 0} resultados).`,
          "success"
        );
      } else if (res.status === "challenge_required") {
        showToast(`Verificação manual necessária (${res.latency_ms}ms).`, "info");
      } else {
        showToast(`Falha no teste (${res.latency_ms}ms): ${res.message || res.status}`, "error");
      }
      onRefresh();
    } catch {
      showToast("Erro ao testar conexão com a fonte.", "error");
    } finally {
      setTestingKey(null);
    }
  };

  const handleSyncOne = async (src: ExternalSourceSummary) => {
    setSyncingKey(src.source_key);
    onHealthChange?.("syncing");
    showToast(`Atualizando ${src.display_name}...`, "info");
    try {
      await api.sources.sync(src.source_key, 3, true);
      showToast(`${src.display_name} atualizada com sucesso.`, "success");
      onDataUpdated?.();
      onRefresh();
    } catch {
      onHealthChange?.("degraded");
      showToast(`Não foi possível atualizar ${src.display_name}.`, "error");
    } finally {
      setSyncingKey(null);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSrc || !editDraft) return;
    try {
      const mirrors = editDraft.mirrors_text
        .split(",")
        .map((m) => m.trim())
        .filter(Boolean);
      const nextCfg: Record<string, any> = {
        ...(editingSrc.config || {}),
        base_url: editDraft.base_url.trim(),
        mirrors,
        ttl_hours: editDraft.ttl_hours,
      };
      if (editingSrc.adapter_key === "torrent_api_py") {
        nextCfg.site = editDraft.site;
        nextCfg.api_key = editDraft.api_key;
        if (editDraft.browser_search_url.trim()) {
          nextCfg.public_web_Search_url = editDraft.browser_search_url.trim();
        }
      } else if (editingSrc.adapter_key === "torznab") {
        nextCfg.api_key = editDraft.api_key;
        nextCfg.categories = editDraft.categories;
      } else if (editingSrc.adapter_key === "unique_web") {
        nextCfg.api_key = editDraft.api_key;
        nextCfg.browser_search_url = editDraft.browser_search_url.trim();
      }
      await api.sources.updateSource(editingSrc.source_key, {
        display_name: editDraft.display_name,
        source_kind: editDraft.source_kind,
        priority: editDraft.priority,
        config: nextCfg,
        clear_cooldown: true,
      });
      showToast(`Ajustes de "${editDraft.display_name}" salvos!`, "success");
      setEditingSrc(null);
      setEditDraft(null);
      onDataUpdated?.();
      onRefresh();
    } catch (err: any) {
      showToast(err?.message || "Erro ao salvar configuração da fonte.", "error");
    }
  };

  const handleDelete = async (sourceKey: string) => {
    try {
      await api.sources.deleteSource(sourceKey);
      showToast(`Fonte "${sourceKey}" removida.`, "info");
      setEditingSrc(null);
      setEditDraft(null);
      onDataUpdated?.();
      onRefresh();
    } catch (err: any) {
      showToast(err?.message || "Erro ao remover fonte.", "error");
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
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
      showToast("Nova fonte adicionada!", "success");
      setShowAddModal(false);
      setNewSourceKey("");
      setNewDisplayName("");
      setNewApiKey("");
      onDataUpdated?.();
      onRefresh();
    } catch (err: any) {
      showToast(err?.message || "Erro ao adicionar fonte.", "error");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-white">Fontes &amp; Provedores</h2>
          <p className="text-xs text-slate-300 mt-0.5">
            Ative, teste a conexão ou configure endereços e cache de cada fonte externa.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="min-h-[44px] flex items-center gap-1.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          Adicionar Fonte
        </button>
      </div>

      {/* Clean Source List */}
      <div className="divide-y divide-white/10 rounded-2xl bg-surface-elevated border border-white/10 overflow-hidden">
        {sources.map((src) => {
          const st = getFriendlyStatus(src);
          return (
            <div
              key={src.source_key}
              className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-white/[0.02]"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold text-white">{src.display_name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${st.badge}`}>
                    {st.label}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  {src.total_titles.toLocaleString("pt-BR")} títulos •{" "}
                  {src.total_releases.toLocaleString("pt-BR")} links disponíveis
                  {src.last_error && (
                    <span className="text-amber-300 inline-flex items-center gap-1 ml-2">
                      <AlertTriangle className="w-3 h-3" />
                      {src.last_error}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => handleToggleEnabled(src)}
                  className={`min-h-[44px] px-3 rounded-xl text-xs font-bold border cursor-pointer ${
                    src.enabled
                      ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-200 hover:bg-emerald-500/25"
                      : "bg-canvas border-white/15 text-slate-300 hover:text-white"
                  }`}
                >
                  {src.enabled ? "Ativada" : "Desativada"}
                </button>

                <button
                  type="button"
                  disabled={testingKey === src.source_key}
                  onClick={() => handleTest(src.source_key)}
                  className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-semibold text-white cursor-pointer disabled:opacity-50"
                >
                  <Wifi className={`w-3.5 h-3.5 ${testingKey === src.source_key ? "animate-pulse" : ""}`} />
                  Testar
                </button>

                {src.supports_sync && (
                  <button
                    type="button"
                    disabled={syncingKey === src.source_key || !src.enabled}
                    onClick={() => handleSyncOne(src)}
                    className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-semibold text-white cursor-pointer disabled:opacity-50"
                  >
                    <RefreshCw
                      className={`w-3.5 h-3.5 ${syncingKey === src.source_key ? "animate-spin" : ""}`}
                    />
                    Atualizar
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => openEditModal(src)}
                  className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-xs font-bold text-white cursor-pointer"
                >
                  <Settings2 className="w-3.5 h-3.5" />
                  Configurar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Focused Edit Source Modal (AMP-04) */}
      {editingSrc && editDraft && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <form
            onSubmit={handleSaveEdit}
            className="w-full max-w-lg rounded-2xl bg-surface-elevated border border-white/15 p-5 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto"
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-extrabold text-white">
                  Configurar {editingSrc.display_name}
                </h3>
                <p className="text-xs text-slate-400">Ajustes de conexão e tempo de cache</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setEditingSrc(null);
                  setEditDraft(null);
                }}
                aria-label="Fechar configuração"
                className="w-9 h-9 rounded-xl bg-canvas border border-white/10 flex items-center justify-center text-slate-300 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">Nome de exibição</span>
                <input
                  value={editDraft.display_name}
                  onChange={(e) => setEditDraft({ ...editDraft, display_name: e.target.value })}
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">
                  Tempo de cache das buscas (horas)
                </span>
                <input
                  type="number"
                  min={1}
                  max={168}
                  value={editDraft.ttl_hours}
                  onChange={(e) =>
                    setEditDraft({ ...editDraft, ttl_hours: Number(e.target.value) || 24 })
                  }
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              <label className="space-y-1 sm:col-span-2">
                <span className="text-slate-300 font-semibold">Endereço principal</span>
                <input
                  value={editDraft.base_url}
                  onChange={(e) => setEditDraft({ ...editDraft, base_url: e.target.value })}
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              <label className="space-y-1 sm:col-span-2">
                <span className="text-slate-300 font-semibold">
                  Endereços alternativos (separados por vírgula)
                </span>
                <input
                  value={editDraft.mirrors_text}
                  onChange={(e) => setEditDraft({ ...editDraft, mirrors_text: e.target.value })}
                  placeholder="https://espelho1.org, https://espelho2.org"
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              {(editingSrc.adapter_key === "torznab" ||
                editingSrc.adapter_key === "torrent_api_py" ||
                editingSrc.adapter_key === "unique_web") && (
                <label className="space-y-1 sm:col-span-2">
                  <span className="text-slate-300 font-semibold">Chave de API / Token</span>
                  <input
                    type="password"
                    value={editDraft.api_key}
                    onChange={(e) => setEditDraft({ ...editDraft, api_key: e.target.value })}
                    placeholder="Manter atual ou informar nova chave"
                    className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                  />
                </label>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/10">
              {!["eztv", "yify"].includes(editingSrc.source_key) ? (
                <button
                  type="button"
                  onClick={() => handleDelete(editingSrc.source_key)}
                  className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-xs font-bold text-rose-200 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Remover
                </button>
              ) : (
                <span />
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setEditingSrc(null);
                    setEditDraft(null);
                  }}
                  className="min-h-[44px] px-4 rounded-xl bg-canvas border border-white/15 text-xs font-semibold text-slate-300 hover:text-white cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="min-h-[44px] flex items-center gap-1.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white cursor-pointer"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Salvar Ajustes
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Add New Source Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <form
            onSubmit={handleCreate}
            className="w-full max-w-lg rounded-2xl bg-surface-elevated border border-white/15 p-5 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-base font-extrabold text-white">Adicionar Nova Fonte</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                aria-label="Fechar"
                className="w-9 h-9 rounded-xl bg-canvas border border-white/10 flex items-center justify-center text-slate-300 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">Tipo de conector</span>
                <select
                  value={newAdapterKey}
                  onChange={(e) => {
                    const val = e.target.value;
                    setNewAdapterKey(val);
                    if (val === "torznab") setNewBaseUrl("http://127.0.0.1:9117/api/v2.0/indexers/all/results/torznab");
                    if (val === "torrent_api_py") setNewBaseUrl("http://127.0.0.1:8009");
                  }}
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                >
                  {adapters.map((a) => (
                    <option key={a.adapter_key} value={a.adapter_key}>
                      {a.display_name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">Nome de exibição</span>
                <input
                  required
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  placeholder="Ex.: Prowlarr Local"
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">Identificador curto</span>
                <input
                  value={newSourceKey}
                  onChange={(e) => setNewSourceKey(e.target.value)}
                  placeholder="Ex.: prowlarr"
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">Endereço principal</span>
                <input
                  required
                  value={newBaseUrl}
                  onChange={(e) => setNewBaseUrl(e.target.value)}
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              {newAdapterKey === "torrent_api_py" && (
                <label className="space-y-1">
                  <span className="text-slate-300 font-semibold">Site indexador</span>
                  <input
                    value={newSite}
                    onChange={(e) => setNewSite(e.target.value)}
                    className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                  />
                </label>
              )}

              <label className="space-y-1">
                <span className="text-slate-300 font-semibold">Chave de API (se necessário)</span>
                <input
                  type="password"
                  value={newApiKey}
                  onChange={(e) => setNewApiKey(e.target.value)}
                  className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                />
              </label>

              {newAdapterKey === "unique_web" && (
                <label className="space-y-1 sm:col-span-2">
                  <span className="text-slate-300 font-semibold">
                    Link para busca manual no navegador
                  </span>
                  <input
                    value={newBrowserUrl}
                    onChange={(e) => setNewBrowserUrl(e.target.value)}
                    placeholder="https://site.exemplo/search?q={query}"
                    className="w-full min-h-[40px] bg-canvas border border-white/15 rounded-xl px-3 text-white"
                  />
                </label>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="min-h-[44px] px-4 rounded-xl bg-canvas border border-white/15 text-xs font-semibold text-slate-300 cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="min-h-[44px] px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white cursor-pointer"
              >
                Criar Fonte
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
