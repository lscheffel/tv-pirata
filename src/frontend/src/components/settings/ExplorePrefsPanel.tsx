import React from "react";
import { CheckCircle2, RotateCcw } from "lucide-react";
import { useExplorePreferences } from "../../context/PreferencesContext";
import { MediaBadgeAction, ProviderBadgeAction } from "../../types";

export const ExplorePrefsPanel: React.FC = () => {
  const { preferences, syncState, updatePreferences, resetPreferences } =
    useExplorePreferences();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-white">Experiência no Explorar</h2>
          <p className="text-xs text-slate-300 mt-0.5">
            Personalize o comportamento dos selos nos cards e dos filtros de busca.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
              syncState === "synced"
                ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                : "bg-surface-elevated border-white/15 text-slate-300"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            {syncState === "synced" ? "Salvo" : syncState === "syncing" ? "Salvando..." : "Local"}
          </span>
          <button
            type="button"
            onClick={() => resetPreferences()}
            className="min-h-[44px] flex items-center gap-1.5 px-3 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-semibold text-slate-200 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Restaurar padrão
          </button>
        </div>
      </div>

      <div className="rounded-2xl bg-surface-elevated border border-white/10 divide-y divide-white/10">
        <div className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-white">Ao clicar em um selo de streaming</div>
            <div className="text-xs text-slate-400">
              Define o que acontece ao tocar em Netflix, Prime Video, Max, etc.
            </div>
          </div>
          <select
            aria-label="Ação ao clicar no selo de streaming"
            value={preferences.badge_provider_action}
            onChange={(e) =>
              updatePreferences({
                badge_provider_action: e.target.value as ProviderBadgeAction,
              })
            }
            className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
          >
            <option value="filter_provider">Filtrar obras deste streaming</option>
            <option value="open_details">Abrir detalhes do título</option>
            <option value="open_provider_info">Ver informações de disponibilidade</option>
          </select>
        </div>

        <div className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-white">Ao clicar no selo de fontes</div>
            <div className="text-xs text-slate-400">
              Define a ação ao tocar no indicador de links disponíveis.
            </div>
          </div>
          <select
            aria-label="Ação ao clicar no selo de fontes"
            value={preferences.badge_media_action}
            onChange={(e) =>
              updatePreferences({
                badge_media_action: e.target.value as MediaBadgeAction,
              })
            }
            className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
          >
            <option value="open_sources_modal">Abrir janela de fontes e links</option>
            <option value="filter_has_media">Filtrar apenas títulos disponíveis</option>
            <option value="open_details">Abrir detalhes do título</option>
          </select>
        </div>

        <label className="p-4 flex items-center justify-between gap-4 cursor-pointer">
          <div>
            <div className="text-sm font-bold text-white">Aplicar filtros automaticamente</div>
            <div className="text-xs text-slate-400">
              Atualiza os resultados imediatamente ao marcar gêneros ou ano, sem clicar em Aplicar.
            </div>
          </div>
          <input
            type="checkbox"
            checked={preferences.auto_apply_filters}
            onChange={(e) => updatePreferences({ auto_apply_filters: e.target.checked })}
            className="w-5 h-5 accent-cyan-500 cursor-pointer shrink-0"
          />
        </label>

        <label className="p-4 flex items-center justify-between gap-4 cursor-pointer">
          <div>
            <div className="text-sm font-bold text-white">Mostrar todos os gêneros por padrão</div>
            <div className="text-xs text-slate-400">
              Exibe todas as categorias de gênero sem precisar expandir a lista.
            </div>
          </div>
          <input
            type="checkbox"
            checked={preferences.show_all_genres}
            onChange={(e) => updatePreferences({ show_all_genres: e.target.checked })}
            className="w-5 h-5 accent-cyan-500 cursor-pointer shrink-0"
          />
        </label>

        <label className="p-4 flex items-center justify-between gap-4 cursor-pointer">
          <div>
            <div className="text-sm font-bold text-white">
              Manter filtros avançados abertos ao entrar
            </div>
            <div className="text-xs text-slate-400">
              Deixa a barra completa de filtros visível assim que abrir a aba Explorar.
            </div>
          </div>
          <input
            type="checkbox"
            checked={preferences.filter_panel_expanded}
            onChange={(e) => updatePreferences({ filter_panel_expanded: e.target.checked })}
            className="w-5 h-5 accent-cyan-500 cursor-pointer shrink-0"
          />
        </label>
      </div>
    </div>
  );
};
