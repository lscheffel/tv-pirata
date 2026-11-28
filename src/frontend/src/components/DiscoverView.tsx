import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Flame,
  Globe,
  RefreshCw,
  ShieldAlert,
  Shuffle,
  SlidersHorizontal,
  Sparkles,
  Zap,
} from "lucide-react";
import {
  DiscoveryFeedResponse,
  FilterSnapshot,
  ForeignTitlesMode,
  MoodFilterMode,
  RouletteScope,
  UnifiedShow,
} from "../types";
import { api, isAbortError } from "../services/api";
import { useExplorePreferences } from "../context/PreferencesContext";
import { HeroBanner } from "./HeroBanner";
import { ShowCard } from "./ShowCard";
import { ShowCarousel } from "./ShowCarousel";
import { AppTabId } from "./Navbar";

interface DiscoverViewProps {
  fallbackHero: UnifiedShow | null;
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary: (show: UnifiedShow) => void;
  onOpenCatalogWithFilters: (patch: Partial<FilterSnapshot>, label?: string) => void;
  onNavigateTab: (tab: AppTabId) => void;
  savedShowIds: Set<number>;
  refreshSignal?: number;
}

const BUILTIN_SHORTCUTS: Array<{
  id: string;
  label: string;
  accent?: string;
  filters: Partial<FilterSnapshot>;
}> = [
  {
    id: "with_media",
    label: "Com Mídia Disponível",
    accent: "bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-200 border-emerald-500/40",
    filters: { selectedSources: ["media"] },
  },
  {
    id: "upcoming_2026",
    label: "Destaques 2026",
    filters: { yearFrom: "2026", sortBy: "popularity" },
  },
  {
    id: "scifi_thriller",
    label: "Filmes Sci-Fi & Suspense",
    filters: {
      selectedTypes: ["movie"],
      genresAny: ["Ficção Científica", "Suspense"],
      yearFrom: "2014",
      yearTo: "2026",
      minRating: 7.5,
      minRuntime: "100",
    },
  },
  {
    id: "crime_series",
    label: "Séries Criminais ≥ 8.0",
    filters: {
      selectedTypes: ["tv_show", "mini_series"],
      genresAny: ["Crime & Investigação"],
      minRating: 8.0,
    },
  },
  {
    id: "running_top",
    label: "Séries em Exibição",
    filters: {
      selectedTypes: ["tv_show"],
      selectedStatus: "Running",
      minRating: 7.2,
      sortBy: "popularity",
    },
  },
];

const ROULETTE_SCOPE_LABELS: Array<{ key: RouletteScope; label: string }> = [
  { key: "all", label: "Tudo" },
  { key: "movie", label: "Filmes" },
  { key: "tv_show", label: "Séries" },
  { key: "with_media", label: "Com Mídia" },
];

export const DiscoverView: React.FC<DiscoverViewProps> = ({
  fallbackHero,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  onOpenCatalogWithFilters,
  onNavigateTab,
  savedShowIds,
  refreshSignal = 0,
}) => {
  const { preferences, updatePreferences } = useExplorePreferences();
  const [sessionSeed, setSessionSeed] = useState<string>(() =>
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
  );
  const [rouletteScope, setRouletteScope] = useState<RouletteScope>("all");
  const [rouletteSpin, setRouletteSpin] = useState<number>(0);
  const [feed, setFeed] = useState<DiscoveryFeedResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const prefsSignature = useMemo(
    () =>
      JSON.stringify({
        v: preferences.discovery_variance_pct,
        f: preferences.foreign_titles_mode,
        p: preferences.parental_control_enabled,
        m: preferences.mood_mode,
        l: preferences.smart_lists.map((s) => `${s.id}:${s.enabled}:${s.order}:${s.limit}:${s.sort_by}:${s.only_with_media}:${s.variance_override ?? ""}`),
      }),
    [
      preferences.discovery_variance_pct,
      preferences.foreign_titles_mode,
      preferences.parental_control_enabled,
      preferences.mood_mode,
      preferences.smart_lists,
    ]
  );

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    api.explore
      .getFeed(sessionSeed, rouletteScope, rouletteSpin, { signal: ctrl.signal })
      .then((res) => {
        setFeed(res);
      })
      .catch((err) => {
        if (!isAbortError(err)) {
          console.error("Erro ao carregar feed de descoberta:", err);
        }
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [sessionSeed, rouletteScope, rouletteSpin, refreshSignal, prefsSignature]);

  const handleHeroImpression = useCallback((imdbId: string) => {
    api.explore.recordImpressions([imdbId], "hero").catch(() => {});
  }, []);

  const handleSpinRoulette = () => {
    const shownIds = (feed?.roulette || [])
      .map((r) => r.imdb_id)
      .filter((id): id is string => Boolean(id));
    if (shownIds.length > 0) {
      api.explore.recordImpressions(shownIds, "roulette").catch(() => {});
    }
    setRouletteSpin((n) => n + 1);
  };

  const handleRefreshShowcase = () => {
    setSessionSeed(`${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`);
  };

  const heroPool = feed?.hero_pool || [];
  const primaryHero = heroPool[0] || fallbackHero;
  const hiddenSet = new Set(preferences.hidden_builtin_shortcuts || []);
  const visibleBuiltins = BUILTIN_SHORTCUTS.filter((b) => !hiddenSet.has(b.id));
  const dynamicShortcuts = feed?.dynamic_shortcuts || [];
  const customShortcuts = (preferences.custom_shortcuts || []).filter((c) => c.pinned);

  return (
    <div className="space-y-8">
      {/* Live Rotating Hero */}
      <HeroBanner
        show={primaryHero}
        pool={heroPool}
        autoRotate={preferences.hero_auto_rotate}
        intervalSec={preferences.hero_interval_sec}
        onImpression={handleHeroImpression}
        onOpenDetails={onOpenDetails}
        onOpenTorrents={onOpenTorrents}
        onSaveToLibrary={onSaveToLibrary}
        savedShowIds={savedShowIds}
      />

      {/* Quick-Intent Discovery Bar (Builtins + Dynamic + Custom) */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-12 relative z-30">
        <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-2.5 px-3 bg-surface-elevated/90 backdrop-blur-md rounded-2xl border border-white/15 shadow-2xl">
          <span className="text-xs font-extrabold uppercase tracking-wider text-slate-300 shrink-0 px-2 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-brand-red" />
            Atalhos:
          </span>

          {visibleBuiltins.map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => onOpenCatalogWithFilters(sc.filters, sc.label)}
              className={`min-h-[40px] px-3.5 rounded-xl text-xs font-bold border whitespace-nowrap cursor-pointer ${
                sc.accent || "bg-canvas hover:bg-white/10 text-slate-100 border-white/10"
              }`}
            >
              {sc.label}
            </button>
          ))}

          {dynamicShortcuts.map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => onOpenCatalogWithFilters(sc.filters, sc.label)}
              className="min-h-[40px] px-3.5 rounded-xl text-xs font-bold bg-sky-950/50 hover:bg-sky-900/50 text-sky-200 border border-sky-500/30 whitespace-nowrap cursor-pointer"
            >
              {sc.label}
            </button>
          ))}

          {customShortcuts.map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => onOpenCatalogWithFilters(sc.filters, sc.label)}
              className="min-h-[40px] px-3.5 rounded-xl text-xs font-bold bg-purple-950/50 hover:bg-purple-900/50 text-purple-200 border border-purple-500/35 whitespace-nowrap cursor-pointer"
            >
              ★ {sc.label}
            </button>
          ))}
        </div>

        {/* Global Content Policy Bar: Foreign Titles & Parental Control */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2.5 px-3.5 py-2 rounded-2xl bg-surface-elevated/80 border border-white/10">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-wider text-slate-300">
              <Globe className="w-3.5 h-3.5 text-sky-400" />
              Estrangeiros:
            </span>
            {(
              [
                { key: "off", label: "Padrão (EN / PT-BR)" },
                { key: "lite", label: "Lite (+ES / CHI / KOR)" },
                { key: "all", label: "Todos" },
              ] as Array<{ key: ForeignTitlesMode; label: string }>
            ).map((opt) => (
              <button
                key={opt.key}
                type="button"
                onClick={() => updatePreferences({ foreign_titles_mode: opt.key })}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold border cursor-pointer transition-colors ${
                  preferences.foreign_titles_mode === opt.key
                    ? "bg-sky-500/25 text-sky-100 border-sky-400/60"
                    : "bg-canvas text-slate-300 border-white/10 hover:text-white"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-wider text-slate-300">
              <Zap className="w-3.5 h-3.5 text-purple-400" />
              Mood:
            </span>
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
                className={`px-2.5 py-1 rounded-lg text-xs font-bold border cursor-pointer transition-colors ${
                  preferences.mood_mode === opt.key
                    ? "bg-purple-500/25 text-purple-100 border-purple-400/60"
                    : "bg-canvas text-slate-300 border-white/10 hover:text-white"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() =>
              updatePreferences({
                parental_control_enabled: !preferences.parental_control_enabled,
              })
            }
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold border cursor-pointer transition-colors ${
              preferences.parental_control_enabled
                ? "bg-amber-500/25 text-amber-100 border-amber-400/60"
                : "bg-canvas text-slate-300 border-white/10 hover:text-white"
            }`}
            title="Quando ativado, oculta animações, desenhos, animes e conteúdos infantis globalmente"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            Controle Parental: {preferences.parental_control_enabled ? "Ativo" : "Desativado"}
          </button>
        </div>
      </div>

      {/* Contextual 3-Item Contrastive Roulette */}
      <section
        aria-labelledby="roulette-heading"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Shuffle className="w-5 h-5 text-brand-red" />
              <h2 id="roulette-heading" className="text-lg sm:text-xl font-extrabold text-white">
                Roleta de Descoberta
              </h2>
            </div>

            <div className="flex items-center gap-1 bg-surface-elevated p-1 rounded-xl border border-white/10">
              {ROULETTE_SCOPE_LABELS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setRouletteScope(opt.key)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold cursor-pointer transition-colors ${
                    rouletteScope === opt.key
                      ? "bg-brand-red text-white"
                      : "text-slate-300 hover:text-white"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRefreshShowcase}
              title="Gerar nova semente orgânica para toda a vitrine"
              className="min-h-[40px] flex items-center gap-1.5 px-3 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5 text-sky-400" />
              Renovar Vitrine
            </button>
            <button
              type="button"
              onClick={handleSpinRoulette}
              className="min-h-[40px] flex items-center gap-1.5 px-3.5 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-100 cursor-pointer"
            >
              <Shuffle className="w-3.5 h-3.5 text-brand-red" />
              Sortear 3 Novamente
            </button>
            <button
              type="button"
              onClick={() => onNavigateTab("config")}
              title="Configurar Listas Inteligentes e Variância"
              className="min-h-[40px] flex items-center gap-1.5 px-3 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 cursor-pointer"
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-amber-400" />
              Curadoria
            </button>
          </div>
        </div>

        {(feed?.roulette || []).length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-5">
            {feed!.roulette.map((show) => (
              <div key={`roulette-${show.imdb_id || show.id}`} className="space-y-1.5">
                {show.roulette_tag && (
                  <span className="inline-block px-2 py-0.5 rounded-md bg-white/10 text-[10px] font-extrabold uppercase tracking-wider text-amber-300 border border-white/10">
                    {show.roulette_tag}
                  </span>
                )}
                <ShowCard
                  show={show}
                  fluidWidth
                  onOpenDetails={onOpenDetails}
                  onOpenTorrents={onOpenTorrents}
                  onSaveToLibrary={onSaveToLibrary}
                  onFilterProvider={(prov) =>
                    onOpenCatalogWithFilters({ selectedProviders: [prov] }, prov)
                  }
                  onFilterHasMedia={() =>
                    onOpenCatalogWithFilters({ selectedSources: ["media"] }, "Com Mídia")
                  }
                  isSaved={
                    savedShowIds.has(show.id) ||
                    (show.tmdb_id ? savedShowIds.has(show.tmdb_id) : false)
                  }
                />
              </div>
            ))}
          </div>
        ) : loading ? (
          <div className="py-8 text-center text-slate-400 text-sm animate-pulse">
            Sorteando escolhas contrastantes...
          </div>
        ) : null}
      </section>

      {/* 10 Configured Smart Lists (up to 100 unique titles each in circular loop) */}
      <div className="max-w-7xl mx-auto space-y-6">
        {loading && !feed ? (
          <div className="py-10 text-center text-slate-300 animate-pulse">
            Carregando listas inteligentes...
          </div>
        ) : (
          (feed?.smart_lists || []).map((sec) => (
            <ShowCarousel
              key={sec.id}
              title={sec.title}
              icon={<Flame className="w-5 h-5 text-brand-red" />}
              shows={sec.items}
              onOpenDetails={onOpenDetails}
              onOpenTorrents={onOpenTorrents}
              onSaveToLibrary={onSaveToLibrary}
              onFilterProvider={(prov) =>
                onOpenCatalogWithFilters({ selectedProviders: [prov] }, prov)
              }
              onFilterHasMedia={() =>
                onOpenCatalogWithFilters({ selectedSources: ["media"] }, "Com Mídia")
              }
              onOpenInCatalog={() => onOpenCatalogWithFilters(sec.catalog_filter, sec.title)}
              savedShowIds={savedShowIds}
            />
          ))
        )}
      </div>
    </div>
  );
};
