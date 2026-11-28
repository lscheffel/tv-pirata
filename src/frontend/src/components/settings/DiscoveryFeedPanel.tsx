import React from "react";
import {
  ArrowDown,
  ArrowUp,
  Globe,
  RotateCcw,
  ShieldAlert,
  Shuffle,
  SlidersHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useExplorePreferences } from "../../context/PreferencesContext";
import { useToast } from "../../context/ToastContext";
import { ForeignTitlesMode, MoodFilterMode, SmartListConfig, SmartListSort } from "../../types";

const SORT_LABELS: Array<{ key: SmartListSort; label: string }> = [
  { key: "balanced", label: "Equilibrada (Score)" },
  { key: "rating", label: "Maior Nota" },
  { key: "popularity", label: "Mais Populares" },
  { key: "newest", label: "Mais Recentes" },
  { key: "p2p_recent", label: "Mídia P2P Recente" },
];

export const DiscoveryFeedPanel: React.FC = () => {
  const { preferences, syncState, updatePreferences, resetPreferences } = useExplorePreferences();
  const { showToast } = useToast();

  const sortedLists = [...(preferences.smart_lists || [])].sort((a, b) => a.order - b.order);

  const patchList = (id: string, patch: Partial<SmartListConfig>) => {
    const next = sortedLists.map((l) => (l.id === id ? { ...l, ...patch } : l));
    updatePreferences({ smart_lists: next });
  };

  const moveList = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= sortedLists.length) return;
    const copy = [...sortedLists];
    const [moved] = copy.splice(index, 1);
    copy.splice(target, 0, moved);
    const reordered = copy.map((item, idx) => ({ ...item, order: idx }));
    updatePreferences({ smart_lists: reordered });
  };

  const removeCustomShortcut = (id: string) => {
    updatePreferences({
      custom_shortcuts: (preferences.custom_shortcuts || []).filter((c) => c.id !== id),
    });
    showToast("Atalho removido.", "info");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-5 rounded-2xl bg-surface-elevated border border-white/10">
        <div className="flex items-center gap-3">
          <Sparkles className="w-6 h-6 text-brand-red" />
          <div>
            <h2 className="text-lg font-extrabold text-white">
              Vitrine &amp; Listas Inteligentes
            </h2>
            <p className="text-xs text-slate-300">
              Controle a variância orgânica, rotação do Hero, ordem das listas e atalhos salvos
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-white/5 border border-white/10 text-slate-300">
            {syncState === "synced"
              ? "Sincronizado"
              : syncState === "syncing"
                ? "Salvando..."
                : "Local"}
          </span>
          <button
            type="button"
            onClick={() => {
              resetPreferences();
              showToast("Preferências restauradas para o padrão.", "info");
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5 text-brand-red" />
            Restaurar Padrão
          </button>
        </div>
      </div>

      {/* Global Content Policy: Foreign Titles, Mood & Parental Control */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-bold text-white">
            <Globe className="w-4 h-4 text-sky-400" />
            <span>Controle de Títulos Estrangeiros (Global)</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                { key: "off", label: "Desativado (Apenas EN-US e PT-BR)" },
                { key: "lite", label: "Lite (EN, PT-BR, ESP, CHI, KOR)" },
                { key: "all", label: "Todos (Catálogo Completo)" },
              ] as Array<{ key: ForeignTitlesMode; label: string }>
            ).map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => updatePreferences({ foreign_titles_mode: opt.key })}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-bold border cursor-pointer transition-colors ${
                  preferences.foreign_titles_mode === opt.key
                    ? "bg-sky-500/25 text-sky-100 border-sky-400/60"
                    : "bg-canvas text-slate-300 border-white/10 hover:text-white"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-400">
            Afeta globalmente a Vitrine Descobrir e o Catálogo (padrão: apenas EN-US e PT-BR).
          </p>
        </div>

        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-bold text-white">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span>Mood da Vitrine &amp; Catálogo</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                { key: "all", label: "Todos" },
                { key: "no_drama", label: "No Drama" },
                { key: "darkside", label: "Darkside" },
                { key: "riseup", label: "Riseup" },
              ] as Array<{ key: MoodFilterMode; label: string }>
            ).map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => updatePreferences({ mood_mode: opt.key })}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-bold border cursor-pointer transition-colors ${
                  preferences.mood_mode === opt.key
                    ? "bg-purple-500/25 text-purple-100 border-purple-400/60"
                    : "bg-canvas text-slate-300 border-white/10 hover:text-white"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-400">
            No Drama oculta Drama/Romance puros; Darkside foca Suspense/Sci-Fi/Crime; Riseup foca Comédia/Ação/Aventura.
          </p>
        </div>

        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs font-bold text-white">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>Controle Parental (Global)</span>
            </span>
            <input
              type="checkbox"
              checked={preferences.parental_control_enabled}
              onChange={(e) =>
                updatePreferences({ parental_control_enabled: e.target.checked })
              }
              className="accent-amber-400 cursor-pointer"
            />
          </div>
          <p className="text-[11px] text-slate-300">
            {preferences.parental_control_enabled
              ? "Ativo por padrão: animações, desenhos, animes e conteúdos infantis estão ocultos em todo o app."
              : "Desativado: exibe animações, animes e conteúdos infantis normalmente."}
          </p>
        </div>
      </div>

      {/* Global Variance, Hero & Impression TTL */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Shuffle className="w-3.5 h-3.5 text-brand-red" />
              Variância Orgânica Global
            </span>
            <span className="text-xs font-black text-brand-red">
              {preferences.discovery_variance_pct}%
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={preferences.discovery_variance_pct}
            onChange={(e) =>
              updatePreferences({ discovery_variance_pct: Number(e.target.value) })
            }
            className="w-full accent-brand-red cursor-pointer"
          />
          <p className="text-[11px] text-slate-400">
            0% = ordem determinística pura · 100% = máxima alternância dentro do pool de qualidade.
          </p>
        </div>

        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white">Auto-rotação do Hero</span>
            <input
              type="checkbox"
              checked={preferences.hero_auto_rotate}
              onChange={(e) => updatePreferences({ hero_auto_rotate: e.target.checked })}
              className="accent-brand-red cursor-pointer"
            />
          </div>
          <div className="flex items-center justify-between text-xs text-slate-300 pt-1">
            <span>Intervalo (segundos):</span>
            <input
              type="number"
              min={5}
              max={60}
              value={preferences.hero_interval_sec}
              onChange={(e) =>
                updatePreferences({
                  hero_interval_sec: Math.max(5, Math.min(60, Number(e.target.value) || 12)),
                })
              }
              className="w-16 bg-canvas border border-white/15 rounded-lg px-2 py-1 text-xs text-white"
            />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-surface-elevated border border-white/10 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white">Memória de Exposição (TTL)</span>
            <span className="text-xs font-bold text-sky-300">
              {preferences.impression_ttl_hours}h
            </span>
          </div>
          <input
            type="range"
            min={12}
            max={168}
            step={12}
            value={preferences.impression_ttl_hours}
            onChange={(e) =>
              updatePreferences({ impression_ttl_hours: Number(e.target.value) })
            }
            className="w-full accent-sky-400 cursor-pointer"
          />
          <p className="text-[11px] text-slate-400">
            Evita repetir títulos recém-exibidos no Hero e na Roleta durante este período.
          </p>
        </div>
      </div>

      {/* Smart Lists Editor */}
      <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-extrabold text-white">
              Listas Inteligentes ({sortedLists.filter((l) => l.enabled).length} ativas)
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">
            Deduplicação total entre todas as listas (até 100 títulos/lista)
          </span>
        </div>

        <div className="space-y-2">
          {sortedLists.map((list, idx) => (
            <div
              key={list.id}
              className={`p-3 rounded-xl border flex flex-col lg:flex-row lg:items-center justify-between gap-3 ${
                list.enabled
                  ? "bg-canvas border-white/15"
                  : "bg-canvas/40 border-white/5 opacity-60"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <input
                  type="checkbox"
                  checked={list.enabled}
                  onChange={(e) => patchList(list.id, { enabled: e.target.checked })}
                  className="accent-brand-red cursor-pointer"
                />
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    disabled={idx === 0}
                    onClick={() => moveList(idx, -1)}
                    aria-label={`Subir ${list.title}`}
                    className="p-1 rounded bg-white/5 hover:bg-white/15 disabled:opacity-30 cursor-pointer"
                  >
                    <ArrowUp className="w-3.5 h-3.5 text-slate-200" />
                  </button>
                  <button
                    type="button"
                    disabled={idx === sortedLists.length - 1}
                    onClick={() => moveList(idx, 1)}
                    aria-label={`Descer ${list.title}`}
                    className="p-1 rounded bg-white/5 hover:bg-white/15 disabled:opacity-30 cursor-pointer"
                  >
                    <ArrowDown className="w-3.5 h-3.5 text-slate-200" />
                  </button>
                </div>
                <span className="text-xs font-bold text-white">{list.title}</span>
              </div>

              <div className="flex flex-wrap items-center gap-2.5 text-[11px]">
                <label className="flex items-center gap-1.5 text-slate-300">
                  <span>Qtd:</span>
                  <input
                    type="number"
                    min={20}
                    max={100}
                    step={10}
                    value={list.limit}
                    onChange={(e) =>
                      patchList(list.id, {
                        limit: Math.max(20, Math.min(100, Number(e.target.value) || 100)),
                      })
                    }
                    className="w-16 bg-surface border border-white/15 rounded-lg px-2 py-1 text-white"
                  />
                </label>

                <select
                  value={list.sort_by}
                  onChange={(e) =>
                    patchList(list.id, { sort_by: e.target.value as SmartListSort })
                  }
                  className="bg-surface border border-white/15 rounded-lg px-2 py-1 text-white"
                >
                  {SORT_LABELS.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </select>

                <label className="inline-flex items-center gap-1.5 text-slate-200 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={list.only_with_media}
                    onChange={(e) => patchList(list.id, { only_with_media: e.target.checked })}
                    className="accent-emerald-400"
                  />
                  Só c/ Mídia
                </label>

                <label className="flex items-center gap-1.5 text-slate-300">
                  <span>Var%:</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    placeholder={`${preferences.discovery_variance_pct}`}
                    value={list.variance_override ?? ""}
                    onChange={(e) =>
                      patchList(list.id, {
                        variance_override:
                          e.target.value === ""
                            ? null
                            : Math.max(0, Math.min(100, Number(e.target.value))),
                      })
                    }
                    className="w-14 bg-surface border border-white/15 rounded-lg px-2 py-1 text-white"
                  />
                </label>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Custom Shortcuts Manager */}
      <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 space-y-3">
        <h3 className="text-sm font-extrabold text-white">
          Atalhos Fixados pelo Usuário ({(preferences.custom_shortcuts || []).length})
        </h3>
        {(preferences.custom_shortcuts || []).length === 0 ? (
          <p className="text-xs text-slate-400">
            Nenhum atalho customizado ainda. Na aba <strong>Catálogo</strong>, monte qualquer filtro
            e clique em <strong>Fixar como Atalho</strong>.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {preferences.custom_shortcuts.map((sc) => (
              <div
                key={sc.id}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-canvas border border-purple-500/35 text-xs font-bold text-purple-200"
              >
                <span>★ {sc.label}</span>
                <button
                  type="button"
                  onClick={() => removeCustomShortcut(sc.id)}
                  aria-label={`Remover atalho ${sc.label}`}
                  className="text-rose-400 hover:text-rose-200 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
