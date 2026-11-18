import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Award,
  Bookmark,
  Calendar,
  ChevronDown,
  ChevronUp,
  Clock,
  Compass,
  Database,
  Download,
  Filter,
  Flame,
  GitMerge,
  Globe,
  RotateCcw,
  Shuffle,
  SlidersHorizontal,
  Sparkles,
  Star,
  Tv,
  Users,
  X,
} from "lucide-react";
import {
  CalendarEventItem,
  CatalogSection,
  DiscoveryFacets,
  MediaWorkDossier,
  MediaWorkSummary,
  PersonDossier,
  PersonSummary,
  SharedCollaborationResponse,
  UnifiedShow,
} from "../types";
import { api, isAbortError, RequestAbortChannel } from "../services/api";
import { useExplorePreferences } from "../context/PreferencesContext";
import { useToast } from "../context/ToastContext";
import { HeroBanner } from "./HeroBanner";
import { MediaBadge } from "./MediaBadge";
import { ProviderBadge, StatusBadge } from "./ShowBadges";
import { ShowCard } from "./ShowCard";
import { ShowCarousel } from "./ShowCarousel";
import { AppTabId } from "./Navbar";

interface ExplorerViewProps {
  heroShow: UnifiedShow | null;
  trendingShows: UnifiedShow[];
  curatedSections: CatalogSection[];
  loadingDiscovery: boolean;
  globalSearchQuery: string;
  onGlobalSearchChange: (q: string) => void;
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary: (show: UnifiedShow) => void;
  onNavigateTab: (tab: AppTabId) => void;
  savedShowIds: Set<number>;
  catalogToUnified: (cat: any) => UnifiedShow;
  refreshSignal?: number;
}

interface FilterSnapshot {
  selectedTypes: string[];
  genresAny: string[];
  genresAll: string[];
  genresNot: string[];
  selectedProviders: string[];
  selectedSources: string[];
  selectedStatus: string;
  yearFrom: string;
  yearTo: string;
  minRating: number;
  minRuntime: string;
  personFilter: string;
  roleFilter: string;
  excludeWatched: boolean;
  onlyWithP2P: boolean;
  sortBy: string;
}

const INITIAL_FILTERS: FilterSnapshot = {
  selectedTypes: [],
  genresAny: [],
  genresAll: [],
  genresNot: [],
  selectedProviders: [],
  selectedSources: [],
  selectedStatus: "",
  yearFrom: "",
  yearTo: "",
  minRating: 0,
  minRuntime: "",
  personFilter: "",
  roleFilter: "",
  excludeWatched: false,
  onlyWithP2P: false,
  sortBy: "rating",
};

const WORK_TYPE_LABELS: Record<string, string> = {
  movie: "Filme",
  tv_show: "Série de TV",
  mini_series: "Minissérie",
  tv_movie: "Telefilme",
  documentary: "Documentário",
  animation: "Animação",
  special: "Especial & Reality",
  short: "Curta-Metragem",
};

const DATA_SOURCE_OPTIONS: Array<{ key: string; label: string; accent: string }> = [
  { key: "eztv", label: "EZTV P2P (sources.db)", accent: "text-yellow-200 border-yellow-400/50 bg-yellow-500/20" },
  { key: "yify", label: "YIFY / YTS (sources.db)", accent: "text-emerald-200 border-emerald-400/50 bg-emerald-500/20" },
  { key: "1337x", label: "1337x (sources.db)", accent: "text-cyan-200 border-cyan-400/50 bg-cyan-500/20" },
  { key: "p2p_active", label: "Seeds Ativos", accent: "text-emerald-200 border-emerald-400/50 bg-emerald-500/20" },
  { key: "imdb", label: "IMDb Universal", accent: "text-amber-200 border-amber-400/50 bg-amber-500/20" },
  { key: "tmdb", label: "TMDB Hidratado", accent: "text-sky-200 border-sky-400/50 bg-sky-500/20" },
  { key: "ptbr", label: "Sinopse PT-BR", accent: "text-green-200 border-green-400/50 bg-green-500/20" },
  { key: "youtube_trailer", label: "Trailer YouTube", accent: "text-rose-200 border-rose-400/50 bg-rose-500/20" },
  { key: "tvmaze", label: "TVMaze Séries", accent: "text-cyan-200 border-cyan-400/50 bg-cyan-500/20" },
  { key: "personal_library", label: "Minha Biblioteca", accent: "text-purple-200 border-purple-400/50 bg-purple-500/20" },
];

const STATUS_OPTIONS: Array<{ key: string; label: string }> = [
  { key: "", label: "Qualquer Status" },
  { key: "Running", label: "Em Exibição (Running)" },
  { key: "Ended", label: "Finalizada (Ended)" },
  { key: "Released", label: "Lançado (Released)" },
  { key: "To Be Determined", label: "A Definir (TBD)" },
  { key: "Canceled", label: "Cancelada" },
];

const ALL_CANONICAL_GENRES_FALLBACK: string[] = [
  "Drama",
  "Comédia",
  "Romance",
  "Suspense",
  "Ação",
  "Crime & Investigação",
  "Documentário",
  "Aventura",
  "Terror",
  "Família",
  "Mistério",
  "Fantasia",
  "Ficção Científica",
  "Cinema TV",
  "Animação",
  "História",
  "Música",
  "Biografia",
  "Guerra & Política",
  "Reality-TV",
  "Faroeste",
  "Musical",
  "Esporte",
  "Infantil / Kids",
  "Talk-Show",
  "Game-Show",
  "Adulto",
  "Novela / Soap",
  "Notícias",
  "Film-Noir",
  "Curta-Metragem",
];

const ALL_CANONICAL_PROVIDERS_FALLBACK: string[] = [
  "Netflix",
  "Prime Video",
  "Max",
  "Disney+",
  "Globoplay",
  "Apple TV+",
  "Paramount+",
  "Crunchyroll",
  "MUBI",
  "Looke",
  "Claro tv+",
  "Hulu",
  "Peacock / NBC",
  "BBC",
  "Discovery",
  "FOX / FX",
  "CBS",
  "ABC",
  "YouTube",
  "AMC+",
  "Cartoon Network",
  "Nickelodeon",
  "MTV / Comedy Central",
  "History / A&E",
  "The CW",
];

const CONFIDENCE_BADGES: Record<string, { label: string; color: string }> = {
  confirmed: {
    label: "Confirmado",
    color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  },
  estimated: {
    label: "Estimado",
    color: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  },
  announced: {
    label: "Anunciado",
    color: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  },
};

function formatFacetCount(n: number): string {
  return (n ?? 0).toLocaleString("pt-BR");
}

function normalizeLookupKey(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function countActiveFilters(f: FilterSnapshot): number {
  return (
    (f.personFilter.trim() ? 1 : 0) +
    (f.roleFilter ? 1 : 0) +
    f.selectedTypes.length +
    f.genresAny.length +
    f.genresAll.length +
    f.genresNot.length +
    f.selectedProviders.length +
    f.selectedSources.length +
    (f.selectedStatus ? 1 : 0) +
    (f.yearFrom ? 1 : 0) +
    (f.yearTo ? 1 : 0) +
    (f.minRating > 0 ? 1 : 0) +
    (f.minRuntime ? 1 : 0) +
    (f.excludeWatched ? 1 : 0) +
    (f.onlyWithP2P ? 1 : 0) +
    (f.sortBy !== "rating" ? 1 : 0)
  );
}

export const ExplorerView: React.FC<ExplorerViewProps> = ({
  heroShow,
  trendingShows,
  curatedSections,
  loadingDiscovery,
  globalSearchQuery,
  onGlobalSearchChange,
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  onNavigateTab,
  savedShowIds,
  catalogToUnified,
  refreshSignal = 0,
}) => {
  const { showToast } = useToast();
  const { preferences, updatePreferences } = useExplorePreferences();
  const abortChannelRef = useRef<RequestAbortChannel>(new RequestAbortChannel());

  const [subMode, setSubMode] = useState<"filters" | "people" | "calendar">("filters");
  const [panelOpen, setPanelOpen] = useState<boolean>(preferences.filter_panel_expanded);
  const [showAllProviders, setShowAllProviders] = useState<boolean>(false);
  const [rouletteOffset, setRouletteOffset] = useState<number>(0);

  // Synchronize text query cleanly with global search bar (350ms debounce)
  const [debouncedQueryText, setDebouncedQueryText] = useState<string>(globalSearchQuery);
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQueryText(globalSearchQuery);
    }, 350);
    return () => clearTimeout(timer);
  }, [globalSearchQuery]);

  useEffect(() => {
    setPanelOpen(preferences.filter_panel_expanded);
  }, [preferences.filter_panel_expanded]);

  // Hybrid filter states: draft (UI edits) & applied (API queries)
  const [draft, setDraft] = useState<FilterSnapshot>(INITIAL_FILTERS);
  const [applied, setApplied] = useState<FilterSnapshot>(INITIAL_FILTERS);
  const [debouncedPerson, setDebouncedPerson] = useState<string>("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedPerson(draft.personFilter);
    }, 350);
    return () => clearTimeout(timer);
  }, [draft.personFilter]);

  // Auto-apply mode synchronizes draft -> applied immediately when enabled
  useEffect(() => {
    if (preferences.auto_apply_filters) {
      setApplied({ ...draft, personFilter: debouncedPerson });
    }
  }, [draft, debouncedPerson, preferences.auto_apply_filters]);

  const hasPendingDraftChanges = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(applied),
    [draft, applied]
  );

  // Results & Facets
  const [works, setWorks] = useState<MediaWorkSummary[]>([]);
  const [totalWorks, setTotalWorks] = useState<number>(0);
  const [facets, setFacets] = useState<DiscoveryFacets | null>(null);
  const [initialLoading, setInitialLoading] = useState<boolean>(true);
  const [isRefetching, setIsRefetching] = useState<boolean>(false);
  const [selectedDossier, setSelectedDossier] = useState<MediaWorkDossier | null>(null);

  // People & Calendar state
  const [peopleList, setPeopleList] = useState<PersonSummary[]>([]);
  const [selectedPerson, setSelectedPerson] = useState<PersonDossier | null>(null);
  const [collabA, setCollabA] = useState<string>("Denis Villeneuve");
  const [collabB, setCollabB] = useState<string>("Rebecca Ferguson");
  const [collabResult, setCollabResult] = useState<SharedCollaborationResponse | null>(null);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEventItem[]>([]);
  const [calendarConfidenceFilter, setCalendarConfidenceFilter] = useState<string>("");

  useEffect(() => {
    const ch = abortChannelRef.current;
    return () => ch.abort();
  }, []);

  const executeExploreQuery = useCallback(() => {
    const signal = abortChannelRef.current.nextSignal();
    setIsRefetching(true);

    api.explore
      .getWorks(
        {
          q: debouncedQueryText.trim() || undefined,
          work_types: applied.selectedTypes.length ? applied.selectedTypes.join(",") : undefined,
          genres_any: applied.genresAny.length ? applied.genresAny.join(",") : undefined,
          genres_all: applied.genresAll.length ? applied.genresAll.join(",") : undefined,
          genres_not: applied.genresNot.length ? applied.genresNot.join(",") : undefined,
          streaming_providers: applied.selectedProviders.length
            ? applied.selectedProviders.join(",")
            : undefined,
          status: applied.selectedStatus || undefined,
          year_from: applied.yearFrom ? parseInt(applied.yearFrom, 10) : undefined,
          year_to: applied.yearTo ? parseInt(applied.yearTo, 10) : undefined,
          min_rating: applied.minRating > 0 ? applied.minRating : undefined,
          min_runtime: applied.minRuntime ? parseInt(applied.minRuntime, 10) : undefined,
          person_query: applied.personFilter.trim() || undefined,
          role_type: applied.roleFilter || undefined,
          exclude_watched: applied.excludeWatched || undefined,
          only_with_p2p: applied.onlyWithP2P || undefined,
          data_sources: applied.selectedSources.length
            ? applied.selectedSources.join(",")
            : undefined,
          sort_by: applied.sortBy,
          page_size: 48,
        },
        { signal }
      )
      .then((res) => {
        setWorks(res.items);
        setTotalWorks(res.total);
        setFacets(res.facets);
      })
      .catch((err) => {
        if (isAbortError(err)) return;
        console.error("Erro ao consultar motor de descoberta:", err);
        showToast("Erro ao consultar catálogo unificado", "error");
      })
      .finally(() => {
        if (!signal.aborted) {
          setInitialLoading(false);
          setIsRefetching(false);
        }
      });
  }, [debouncedQueryText, applied, showToast, refreshSignal]);

  useEffect(() => {
    executeExploreQuery();
  }, [executeExploreQuery]);

  useEffect(() => {
    if (subMode === "people") {
      api.explore
        .getPeople()
        .then((data) => {
          setPeopleList(data);
          if (data.length > 0 && !selectedPerson) {
            api.explore.getPersonDossier(data[0].id).then(setSelectedPerson);
          }
        })
        .catch(() => {});
      api.explore
        .getCollaborations(collabA, collabB)
        .then(setCollabResult)
        .catch(() => {});
    } else if (subMode === "calendar") {
      api.explore
        .getCalendar({ confidence_level: calendarConfidenceFilter || undefined })
        .then(setCalendarEvents)
        .catch(() => {});
    }
  }, [subMode, calendarConfidenceFilter]);

  const appliedFiltersCount = countActiveFilters(applied);
  const isIdleExplore =
    subMode === "filters" && appliedFiltersCount === 0 && !debouncedQueryText.trim();

  const convertWorkToUnified = useCallback(
    (w: MediaWorkSummary): UnifiedShow => ({
      id: w.tmdb_id || w.id,
      tmdb_id: w.tmdb_id || w.id,
      tvmaze_id: w.tvmaze_id || undefined,
      imdb_id: w.imdb_id || undefined,
      title: w.title,
      original_title: w.original_title || undefined,
      overview: w.overview,
      poster_url: w.poster_url || undefined,
      backdrop_url: w.backdrop_url || undefined,
      rating: w.canonical_rating,
      genres: w.genres,
      first_air_date: w.release_date || undefined,
      status: w.status,
      network: w.network_or_studio || undefined,
      streaming_providers: w.streaming_providers || [],
      eztv_available: w.eztv_available,
      eztv_show_id: w.eztv_show_id || undefined,
      has_media: Boolean(w.has_media ?? w.eztv_available),
      media_sources: w.media_sources || (w.eztv_available ? ["eztv"] : []),
      sources_count: w.sources_count ?? (w.eztv_available ? 1 : 0),
      source_provider: w.rating_source || "imdb",
      seasons: [],
    }),
    []
  );

  // Contrastive 3-item Roulette for Adaptive Idle Mode (DEC-001)
  const rouletteShows = useMemo(() => {
    const pool: UnifiedShow[] = [];
    const seen = new Set<string>();
    for (const s of [...trendingShows, ...works.slice(0, 18).map(convertWorkToUnified)]) {
      const k = s.imdb_id || `${s.id}-${s.title}`;
      if (!seen.has(k)) {
        seen.add(k);
        pool.push(s);
      }
    }
    if (pool.length === 0) return [];
    const picks: UnifiedShow[] = [];
    for (let i = 0; i < Math.min(3, pool.length); i++) {
      picks.push(pool[(rouletteOffset * 3 + i) % pool.length]);
    }
    return picks;
  }, [trendingShows, works, convertWorkToUnified, rouletteOffset]);

  const handleOpenDossier = async (workId: number | string) => {
    try {
      const dossier = await api.explore.getWorkDossier(workId);
      setSelectedDossier(dossier);
    } catch {
      showToast("Erro ao abrir dossiê canônico da obra", "error");
    }
  };

  const handleApplyDraftFilters = () => {
    setApplied(draft);
  };

  const handleResetFilters = () => {
    onGlobalSearchChange("");
    setDebouncedQueryText("");
    setDraft(INITIAL_FILTERS);
    setApplied(INITIAL_FILTERS);
    showToast("Todos os filtros foram limpos e restaurados", "info");
  };

  const handleImmediateProviderFilter = (provider: string) => {
    const updater = (prev: FilterSnapshot): FilterSnapshot => ({
      ...prev,
      selectedProviders: prev.selectedProviders.includes(provider)
        ? prev.selectedProviders
        : [...prev.selectedProviders, provider],
    });
    setDraft(updater);
    setApplied(updater);
    setSubMode("filters");
    showToast(`Filtrando catálogo por: ${provider}`, "info");
  };

  const handleImmediateMediaFilter = () => {
    const updater = (prev: FilterSnapshot): FilterSnapshot => ({
      ...prev,
      selectedSources: prev.selectedSources.includes("media")
        ? prev.selectedSources
        : [...prev.selectedSources, "media"],
    });
    setDraft(updater);
    setApplied(updater);
    setSubMode("filters");
    showToast("Exibindo títulos disponíveis em Fontes de Dados", "info");
  };

  const applyPreset = (presetId: string) => {
    onGlobalSearchChange("");
    let next: FilterSnapshot = { ...INITIAL_FILTERS };
    if (presetId === "scifi_thriller") {
      next = {
        ...next,
        selectedTypes: ["movie"],
        genresAny: ["Ficção Científica", "Suspense"],
        yearFrom: "2014",
        yearTo: "2026",
        minRating: 7.5,
        minRuntime: "100",
      };
    } else if (presetId === "crime_series") {
      next = {
        ...next,
        selectedTypes: ["tv_show", "mini_series"],
        genresAny: ["Crime & Investigação"],
        minRating: 8.0,
      };
    } else if (presetId === "with_media") {
      next = {
        ...next,
        selectedSources: ["media"],
      };
    } else if (presetId === "villeneuve") {
      next = {
        ...next,
        personFilter: "Denis Villeneuve",
        roleFilter: "director",
      };
    } else if (presetId === "upcoming_2026") {
      next = {
        ...next,
        yearFrom: "2026",
        sortBy: "popularity",
      };
    }
    setDraft(next);
    setApplied(next);
  };

  const handleCycleGenre = (genreName: string) => {
    setDraft((prev) => {
      if (prev.genresAny.includes(genreName)) {
        return {
          ...prev,
          genresAny: prev.genresAny.filter((g) => g !== genreName),
          genresAll: [...prev.genresAll, genreName],
        };
      }
      if (prev.genresAll.includes(genreName)) {
        return {
          ...prev,
          genresAll: prev.genresAll.filter((g) => g !== genreName),
          genresNot: [...prev.genresNot, genreName],
        };
      }
      if (prev.genresNot.includes(genreName)) {
        return {
          ...prev,
          genresNot: prev.genresNot.filter((g) => g !== genreName),
        };
      }
      return { ...prev, genresAny: [...prev.genresAny, genreName] };
    });
  };

  const genreCountMap = new Map<string, number>();
  for (const fg of facets?.genres ?? []) {
    genreCountMap.set(normalizeLookupKey(fg.key), fg.count);
  }
  const getGenreCount = (g: string): number =>
    facets?.genres.find((fg) => fg.key === g)?.count ??
    genreCountMap.get(normalizeLookupKey(g)) ??
    0;

  const allMergedGenres = Array.from(
    new Set([
      ...(facets?.genres.map((fg) => fg.key) ?? []),
      ...ALL_CANONICAL_GENRES_FALLBACK,
    ])
  ).sort((a, b) => getGenreCount(b) - getGenreCount(a));
  // DEC-005: showAllGenres=false displays Top-10 genres
  const availableGenres = preferences.show_all_genres
    ? allMergedGenres
    : allMergedGenres.slice(0, 10);

  const providerCountMap = new Map<string, number>();
  for (const fp of facets?.streaming_providers ?? []) {
    providerCountMap.set(normalizeLookupKey(fp.key), fp.count);
  }
  const getProviderCount = (p: string): number =>
    facets?.streaming_providers.find((fp) => fp.key === p)?.count ??
    providerCountMap.get(normalizeLookupKey(p)) ??
    0;

  const allMergedProviders = Array.from(
    new Set([
      ...(facets?.streaming_providers.map((fp) => fp.key) ?? []),
      ...ALL_CANONICAL_PROVIDERS_FALLBACK,
    ])
  ).sort((a, b) => getProviderCount(b) - getProviderCount(a));
  const availableProviders = showAllProviders
    ? allMergedProviders
    : allMergedProviders.slice(0, 12);

  return (
    <div className="space-y-8">
      {/* ===================================================================== */}
      {/* ADAPTIVE HERO + QUICK-INTENT + ROULETTE (VISIBLE ONLY WHEN IDLE)       */}
      {/* ===================================================================== */}
      {isIdleExplore && (
        <div className="space-y-8">
          <HeroBanner
            show={heroShow}
            onOpenDetails={onOpenDetails}
            onOpenTorrents={onOpenTorrents}
            onSaveToLibrary={onSaveToLibrary}
            isSaved={
              heroShow
                ? savedShowIds.has(heroShow.id) ||
                  (heroShow.tmdb_id ? savedShowIds.has(heroShow.tmdb_id) : false)
                : false
            }
          />

          {/* Quick-Intent Discovery Bar */}
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-12 relative z-30">
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-2.5 px-3 bg-surface-elevated/90 backdrop-blur-md rounded-2xl border border-white/15 shadow-2xl">
              <span className="text-xs font-extrabold uppercase tracking-wider text-slate-300 shrink-0 px-2 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-brand-red" />
                Atalhos:
              </span>
              <button
                type="button"
                onClick={() => applyPreset("scifi_thriller")}
                className="min-h-[44px] px-3.5 rounded-xl text-xs font-bold bg-canvas hover:bg-white/10 text-slate-100 border border-white/10 whitespace-nowrap cursor-pointer"
              >
                Filmes Sci-Fi &amp; Suspense
              </button>
              <button
                type="button"
                onClick={() => applyPreset("crime_series")}
                className="min-h-[44px] px-3.5 rounded-xl text-xs font-bold bg-canvas hover:bg-white/10 text-slate-100 border border-white/10 whitespace-nowrap cursor-pointer"
              >
                Séries Criminais ≥ 8.0
              </button>
              <button
                type="button"
                onClick={() => applyPreset("with_media")}
                className="min-h-[44px] px-3.5 rounded-xl text-xs font-bold bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-200 border border-emerald-500/40 whitespace-nowrap cursor-pointer"
              >
                Com Mídia Disponível
              </button>
              <button
                type="button"
                onClick={() => applyPreset("villeneuve")}
                className="min-h-[44px] px-3.5 rounded-xl text-xs font-bold bg-canvas hover:bg-white/10 text-slate-100 border border-white/10 whitespace-nowrap cursor-pointer"
              >
                Direção: Denis Villeneuve
              </button>
              <button
                type="button"
                onClick={() => applyPreset("upcoming_2026")}
                className="min-h-[44px] px-3.5 rounded-xl text-xs font-bold bg-canvas hover:bg-white/10 text-slate-100 border border-white/10 whitespace-nowrap cursor-pointer"
              >
                Destaques 2026
              </button>
            </div>
          </div>

          {/* Contrastive 3-Item Roulette */}
          {rouletteShows.length > 0 && (
            <section
              aria-labelledby="roulette-heading"
              className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Shuffle className="w-5 h-5 text-brand-red" />
                  <h2 id="roulette-heading" className="text-lg sm:text-xl font-extrabold text-white">
                    Roleta de Descoberta (3 Escolhas Contrastantes)
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setRouletteOffset((n) => n + 1)}
                  className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-100 cursor-pointer"
                >
                  <Shuffle className="w-3.5 h-3.5 text-brand-red" />
                  Sortear 3 Novamente
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-5">
                {rouletteShows.map((show) => (
                  <ShowCard
                    key={`roulette-${show.id}-${show.title}`}
                    show={show}
                    fluidWidth
                    onOpenDetails={onOpenDetails}
                    onOpenTorrents={onOpenTorrents}
                    onSaveToLibrary={onSaveToLibrary}
                    onFilterProvider={handleImmediateProviderFilter}
                    onFilterHasMedia={handleImmediateMediaFilter}
                    isSaved={
                      savedShowIds.has(show.id) ||
                      (show.tmdb_id ? savedShowIds.has(show.tmdb_id) : false)
                    }
                  />
                ))}
              </div>
            </section>
          )}

          {/* Curated Discovery Carousels */}
          <div className="max-w-7xl mx-auto space-y-6">
            {loadingDiscovery ? (
              <div className="py-8 text-center text-slate-300 animate-pulse">
                Carregando carrosséis curados...
              </div>
            ) : (
              <>
                {trendingShows.length > 0 && (
                  <ShowCarousel
                    title="Em Alta no Momento"
                    icon={<Flame className="w-6 h-6 text-brand-red" />}
                    shows={trendingShows}
                    onOpenDetails={onOpenDetails}
                    onOpenTorrents={onOpenTorrents}
                    onSaveToLibrary={onSaveToLibrary}
                    savedShowIds={savedShowIds}
                  />
                )}
                {curatedSections.slice(0, 3).map((sec) => (
                  <ShowCarousel
                    key={sec.id}
                    title={sec.title}
                    icon={<Sparkles className="w-5 h-5 text-purple-400" />}
                    shows={sec.items.map(catalogToUnified)}
                    onOpenDetails={onOpenDetails}
                    onOpenTorrents={onOpenTorrents}
                    onSaveToLibrary={onSaveToLibrary}
                    savedShowIds={savedShowIds}
                  />
                ))}
              </>
            )}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* UNIFIED EXPLORE ENGINE & MULTIDIMENSIONAL FILTER SECTION              */}
      {/* ===================================================================== */}
      <div
        className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6 ${
          isIdleExplore ? "pt-4" : "pt-28 lg:pt-24"
        }`}
      >
        {/* Header & Perspective Switcher */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-white/10 pb-5">
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <Compass className="w-7 h-7 text-brand-red" />
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Explorar Catálogo
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-brand-red/20 text-brand-red border border-brand-red/30">
                {totalWorks.toLocaleString("pt-BR")} OBRAS
              </span>
            </div>
            <p className="text-sm text-slate-300 mt-1">
              Descoberta unificada PT-BR / EN-US com SQL Pushdown, filtros booleanos e multi-provedor
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Sub-Mode Tabs */}
            <div className="flex items-center gap-1 bg-surface-elevated p-1 rounded-2xl border border-white/10">
              <button
                type="button"
                onClick={() => setSubMode("filters")}
                className={`min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  subMode === "filters"
                    ? "bg-brand-red text-white shadow-cinema-glow"
                    : "text-slate-300 hover:text-white"
                }`}
              >
                <Filter className="w-3.5 h-3.5" />
                Catálogo ({totalWorks.toLocaleString("pt-BR")})
              </button>
              <button
                type="button"
                onClick={() => setSubMode("people")}
                className={`min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  subMode === "people"
                    ? "bg-brand-red text-white shadow-cinema-glow"
                    : "text-slate-300 hover:text-white"
                }`}
              >
                <Users className="w-3.5 h-3.5" />
                Pessoas
              </button>
              <button
                type="button"
                onClick={() => setSubMode("calendar")}
                className={`min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  subMode === "calendar"
                    ? "bg-brand-red text-white shadow-cinema-glow"
                    : "text-slate-300 hover:text-white"
                }`}
              >
                <Calendar className="w-3.5 h-3.5" />
                Agenda
              </button>
            </div>

            <button
              type="button"
              onClick={() => onNavigateTab("config")}
              className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 cursor-pointer"
              title="Abrir Central de Status, Sincronização e Preferências"
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-sky-400" />
              Status &amp; Config
            </button>
          </div>
        </div>

        {/* ===================================================================== */}
        {/* SUB-MODE 1: COLLAPSIBLE HYBRID FILTER ACCORDION + UNIFIED GRID        */}
        {/* ===================================================================== */}
        {subMode === "filters" && (
          <div className="space-y-5">
            {/* Compact Filter Accordion Header */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-2xl bg-surface-elevated border border-white/10">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  aria-expanded={panelOpen}
                  onClick={() => {
                    const next = !panelOpen;
                    setPanelOpen(next);
                    updatePreferences({ filter_panel_expanded: next });
                  }}
                  className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-extrabold text-white cursor-pointer"
                >
                  <Filter className="w-4 h-4 text-brand-red" />
                  <span>Filtros Avançados &amp; Booleanos</span>
                  {appliedFiltersCount > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-brand-red text-white">
                      {appliedFiltersCount}
                    </span>
                  )}
                  {panelOpen ? (
                    <ChevronUp className="w-4 h-4 text-slate-300" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-300" />
                  )}
                </button>

                {(appliedFiltersCount > 0 || globalSearchQuery.trim()) && (
                  <button
                    type="button"
                    onClick={handleResetFilters}
                    className="min-h-[44px] flex items-center gap-1.5 px-3.5 rounded-xl text-xs font-bold text-brand-red bg-brand-red/10 hover:bg-brand-red/20 border border-brand-red/40 cursor-pointer"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Limpar Filtros
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <label htmlFor="explore-sort-select" className="text-xs font-bold text-slate-300">
                  Ordenar:
                </label>
                <select
                  id="explore-sort-select"
                  value={draft.sortBy}
                  onChange={(e) => {
                    const nextSort = e.target.value;
                    setDraft((p) => ({ ...p, sortBy: nextSort }));
                    setApplied((p) => ({ ...p, sortBy: nextSort }));
                  }}
                  className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
                >
                  <option value="rating">Relevância &amp; Avaliação</option>
                  <option value="relevance">Correspondência Exata</option>
                  <option value="popularity">Popularidade / Votos</option>
                  <option value="year_desc">Mais Recentes</option>
                  <option value="year_asc">Mais Antigos</option>
                  <option value="runtime">Maior Duração</option>
                  <option value="title">Alfabética (A-Z)</option>
                </select>
              </div>
            </div>

            {/* Expandable Multidimensional Filter Panel */}
            {panelOpen && (
              <div className="p-5 rounded-2xl bg-surface-elevated/95 border border-white/15 shadow-2xl space-y-5">
                {/* Text, Person, Role */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label
                      htmlFor="explore-query-input"
                      className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1"
                    >
                      Pesquisa Livre (PT-BR / EN)
                    </label>
                    <input
                      id="explore-query-input"
                      type="text"
                      value={globalSearchQuery}
                      onChange={(e) => onGlobalSearchChange(e.target.value)}
                      placeholder="Título, tema, franquia..."
                      className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs text-white placeholder-slate-400"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="explore-person-input"
                      className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1"
                    >
                      Pessoa (Ator, Diretor, Criador)
                    </label>
                    <input
                      id="explore-person-input"
                      type="text"
                      value={draft.personFilter}
                      onChange={(e) =>
                        setDraft((p) => ({ ...p, personFilter: e.target.value }))
                      }
                      placeholder="Ex: Denis Villeneuve..."
                      className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs text-white placeholder-slate-400"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="explore-role-select"
                      className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1"
                    >
                      Função na Obra
                    </label>
                    <select
                      id="explore-role-select"
                      value={draft.roleFilter}
                      onChange={(e) => setDraft((p) => ({ ...p, roleFilter: e.target.value }))}
                      className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs text-white"
                    >
                      <option value="">Qualquer função</option>
                      <option value="director">Diretor(a)</option>
                      <option value="creator">Criador(a)</option>
                      <option value="actor">Ator / Atriz</option>
                      <option value="writer">Roteirista</option>
                    </select>
                  </div>
                </div>

                {/* Data Sources */}
                <div className="pt-2 border-t border-white/10 space-y-2">
                  <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-300">
                    Fontes de Dados &amp; Provedores
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {DATA_SOURCE_OPTIONS.map((src) => {
                      const active = draft.selectedSources.includes(src.key);
                      const count =
                        facets?.data_sources?.find((ds) => ds.key === src.key)?.count ?? 0;
                      return (
                        <button
                          key={src.key}
                          type="button"
                          onClick={() =>
                            setDraft((p) => ({
                              ...p,
                              selectedSources: active
                                ? p.selectedSources.filter((s) => s !== src.key)
                                : [...p.selectedSources, src.key],
                            }))
                          }
                          className={`px-2.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 border cursor-pointer ${
                            active
                              ? `${src.accent} ring-1 ring-white/40`
                              : "bg-canvas text-slate-200 border-white/15 hover:border-white/30"
                          }`}
                        >
                          <Database className="w-3 h-3 shrink-0" />
                          <span>{src.label}</span>
                          <span className="px-1.5 py-0.5 rounded bg-black/30 text-[10px] font-mono">
                            {formatFacetCount(count)}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Format + Quantitative */}
                <div className="pt-2 border-t border-white/10 flex flex-col xl:flex-row xl:items-end justify-between gap-4">
                  <div className="space-y-1.5">
                    <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-300">
                      Formato Audiovisual
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(WORK_TYPE_LABELS).map(([key, label]) => {
                        const active = draft.selectedTypes.includes(key);
                        const count = facets?.work_types.find((f) => f.key === key)?.count ?? 0;
                        return (
                          <button
                            key={key}
                            type="button"
                            onClick={() =>
                              setDraft((p) => ({
                                ...p,
                                selectedTypes: active
                                  ? p.selectedTypes.filter((t) => t !== key)
                                  : [...p.selectedTypes, key],
                              }))
                            }
                            className={`px-2.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 border cursor-pointer ${
                              active
                                ? "bg-brand-red text-white border-brand-red"
                                : "bg-canvas text-slate-200 border-white/15 hover:border-white/30"
                            }`}
                          >
                            <span>{label}</span>
                            <span className="px-1.5 py-0.5 rounded bg-black/30 text-[10px] font-mono">
                              {formatFacetCount(count)}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 shrink-0">
                    <div>
                      <label htmlFor="explore-status" className="block text-[10px] font-bold uppercase text-slate-300 mb-1">
                        Status
                      </label>
                      <select
                        id="explore-status"
                        value={draft.selectedStatus}
                        onChange={(e) => setDraft((p) => ({ ...p, selectedStatus: e.target.value }))}
                        className="bg-canvas border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-white"
                      >
                        {STATUS_OPTIONS.map((opt) => (
                          <option key={opt.key || "all"} value={opt.key}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label htmlFor="explore-yr-from" className="block text-[10px] font-bold uppercase text-slate-300 mb-1">
                        Ano Início
                      </label>
                      <input
                        id="explore-yr-from"
                        type="number"
                        placeholder="1970"
                        value={draft.yearFrom}
                        onChange={(e) => setDraft((p) => ({ ...p, yearFrom: e.target.value }))}
                        className="w-20 bg-canvas border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-white"
                      />
                    </div>
                    <div>
                      <label htmlFor="explore-yr-to" className="block text-[10px] font-bold uppercase text-slate-300 mb-1">
                        Ano Fim
                      </label>
                      <input
                        id="explore-yr-to"
                        type="number"
                        placeholder="2026"
                        value={draft.yearTo}
                        onChange={(e) => setDraft((p) => ({ ...p, yearTo: e.target.value }))}
                        className="w-20 bg-canvas border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-white"
                      />
                    </div>
                    <div>
                      <label htmlFor="explore-rating" className="block text-[10px] font-bold uppercase text-slate-300 mb-1">
                        Nota Mín: {draft.minRating > 0 ? draft.minRating.toFixed(1) : "Todas"}
                      </label>
                      <input
                        id="explore-rating"
                        type="range"
                        min="0"
                        max="9"
                        step="0.5"
                        value={draft.minRating}
                        onChange={(e) =>
                          setDraft((p) => ({ ...p, minRating: parseFloat(e.target.value) }))
                        }
                        className="w-28 accent-brand-red cursor-pointer"
                      />
                    </div>
                  </div>
                </div>

                {/* Top-10 / Expandable Boolean Genres */}
                <div className="pt-2 border-t border-white/10 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
                      Gêneros Combináveis (1x = OR • 2x = AND • 3x = NOT)
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        updatePreferences({ show_all_genres: !preferences.show_all_genres })
                      }
                      className="text-xs font-bold text-sky-300 hover:text-white underline underline-offset-2 cursor-pointer"
                    >
                      {preferences.show_all_genres
                        ? "Mostrar Top 10"
                        : `Ver todas as ${allMergedGenres.length} categorias`}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {availableGenres.map((g) => {
                      const isOr = draft.genresAny.includes(g);
                      const isAnd = draft.genresAll.includes(g);
                      const isNot = draft.genresNot.includes(g);
                      const count = getGenreCount(g);
                      let btnStyle = "bg-canvas text-slate-200 border-white/15 hover:border-white/30";
                      let prefix = "";
                      if (isOr) {
                        btnStyle = "bg-brand-red/20 text-brand-red border-brand-red font-extrabold";
                        prefix = "OR: ";
                      } else if (isAnd) {
                        btnStyle = "bg-emerald-500/20 text-emerald-300 border-emerald-500 font-extrabold";
                        prefix = "AND: ";
                      } else if (isNot) {
                        btnStyle = "bg-rose-950/60 text-rose-300 border-rose-500/40 line-through";
                        prefix = "NOT: ";
                      }
                      return (
                        <button
                          key={g}
                          type="button"
                          onClick={() => handleCycleGenre(g)}
                          className={`px-2.5 py-1.5 rounded-lg text-xs border flex items-center gap-1.5 cursor-pointer ${btnStyle}`}
                        >
                          <span>
                            {prefix}
                            {g}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-black/30 text-[10px] font-mono">
                            {formatFacetCount(count)}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Streaming Providers + Explicit Apply Button */}
                <div className="pt-2 border-t border-white/10 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
                      Streaming &amp; Redes ({allMergedProviders.length})
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowAllProviders((p) => !p)}
                      className="text-xs font-bold text-sky-300 hover:text-white underline underline-offset-2 cursor-pointer"
                    >
                      {showAllProviders
                        ? "Mostrar principais (12)"
                        : `Ver todos (${allMergedProviders.length})`}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {availableProviders.map((prov) => {
                      const active = draft.selectedProviders.includes(prov);
                      const count = getProviderCount(prov);
                      return (
                        <button
                          key={prov}
                          type="button"
                          onClick={() =>
                            setDraft((p) => ({
                              ...p,
                              selectedProviders: active
                                ? p.selectedProviders.filter((x) => x !== prov)
                                : [...p.selectedProviders, prov],
                            }))
                          }
                          className={`px-2.5 py-1.5 rounded-lg text-xs font-bold border flex items-center gap-1.5 cursor-pointer ${
                            active
                              ? "bg-white text-black border-white"
                              : "bg-canvas text-slate-200 border-white/15 hover:border-white/30"
                          }`}
                        >
                          <Tv className="w-3 h-3 shrink-0" />
                          <span>{prov}</span>
                          <span className="px-1.5 py-0.5 rounded bg-black/20 text-[10px] font-mono">
                            {formatFacetCount(count)}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Hybrid Footer Actions */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-white/10">
                    <div className="flex flex-wrap items-center gap-4">
                      <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer min-h-[44px]">
                        <input
                          type="checkbox"
                          checked={draft.excludeWatched}
                          onChange={(e) =>
                            setDraft((p) => ({ ...p, excludeWatched: e.target.checked }))
                          }
                          className="accent-brand-red"
                        />
                        Ocultar assistidos
                      </label>
                      <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer min-h-[44px]">
                        <input
                          type="checkbox"
                          checked={draft.onlyWithP2P}
                          onChange={(e) =>
                            setDraft((p) => ({ ...p, onlyWithP2P: e.target.checked }))
                          }
                          className="accent-brand-red"
                        />
                        Com Seeds P2P
                      </label>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleResetFilters}
                        className="min-h-[44px] flex items-center gap-1.5 px-4 rounded-xl bg-canvas hover:bg-white/10 border border-white/15 text-xs font-bold text-slate-200 cursor-pointer"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-brand-red" />
                        Resetar
                      </button>
                      {!preferences.auto_apply_filters && (
                        <button
                          type="button"
                          onClick={handleApplyDraftFilters}
                          className={`min-h-[44px] flex items-center gap-2 px-5 rounded-xl text-xs font-extrabold transition-all cursor-pointer ${
                            hasPendingDraftChanges
                              ? "bg-brand-red hover:bg-brand-redHover text-white shadow-cinema-glow"
                              : "bg-emerald-600 hover:bg-emerald-500 text-white"
                          }`}
                        >
                          <Filter className="w-3.5 h-3.5" />
                          {hasPendingDraftChanges ? "Aplicar Filtros *" : "Aplicar Filtros"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Non-destructive linear progress bar keeping grid mounted */}
            {isRefetching && (
              <div
                className="w-full h-1 bg-surface-elevated overflow-hidden rounded-full"
                aria-hidden="true"
              >
                <div className="h-full w-1/3 bg-brand-red animate-pulse rounded-full" />
              </div>
            )}

            {/* Unified Works Grid rendered with ShowCard */}
            <div aria-busy={isRefetching}>
              {initialLoading && works.length === 0 ? (
                <div className="py-16 text-center text-slate-300 animate-pulse">
                  Consultando catálogo canônico...
                </div>
              ) : works.length === 0 ? (
                <div className="py-16 text-center rounded-2xl border border-dashed border-white/15 bg-surface/50 p-8 space-y-3">
                  <Compass className="w-12 h-12 mx-auto text-slate-400" />
                  <h3 className="text-lg font-bold text-white">
                    Nenhuma obra corresponde aos filtros atuais
                  </h3>
                  <p className="text-xs text-slate-300 max-w-md mx-auto">
                    Experimente remover restrições booleanas ou restaurar os filtros padrão.
                  </p>
                  <button
                    type="button"
                    onClick={handleResetFilters}
                    className="min-h-[44px] px-5 rounded-xl text-xs font-bold bg-brand-red text-white cursor-pointer"
                  >
                    Restaurar Filtros
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-5">
                  {works.map((w) => {
                    const unified = convertWorkToUnified(w);
                    const isSaved =
                      savedShowIds.has(unified.id) ||
                      (w.tmdb_id ? savedShowIds.has(w.tmdb_id) : false);
                    return (
                      <ShowCard
                        key={w.imdb_id || w.id}
                        show={unified}
                        fluidWidth
                        workTypeLabel={WORK_TYPE_LABELS[w.work_type] || w.work_type}
                        runtimeMinutes={w.runtime_minutes}
                        originCountry={w.origin_country}
                        directors={w.directors}
                        onOpenDetails={() => handleOpenDossier(w.imdb_id || w.id)}
                        onOpenTorrents={onOpenTorrents}
                        onSaveToLibrary={onSaveToLibrary}
                        onAddToCollection={() => onNavigateTab("collections")}
                        onFilterProvider={handleImmediateProviderFilter}
                        onFilterHasMedia={handleImmediateMediaFilter}
                        isSaved={isSaved}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ===================================================================== */}
        {/* SUB-MODE 2: PEOPLE & COLLABORATIONS                                   */}
        {/* ===================================================================== */}
        {subMode === "people" && (
          <div className="space-y-8">
            <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 shadow-xl space-y-4">
              <div className="flex items-center gap-2">
                <GitMerge className="w-5 h-5 text-brand-red" />
                <h2 className="text-base font-bold text-white">
                  Descoberta Relacional: Obras Compartilhadas
                </h2>
              </div>
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!collabA.trim() || !collabB.trim()) return;
                  try {
                    setCollabResult(
                      await api.explore.getCollaborations(collabA.trim(), collabB.trim())
                    );
                  } catch {
                    showToast("Erro ao buscar colaborações", "error");
                  }
                }}
                className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3"
              >
                <div className="flex-1">
                  <label htmlFor="collab-a" className="block text-[11px] font-bold uppercase text-slate-300 mb-1">
                    Profissional A
                  </label>
                  <input
                    id="collab-a"
                    type="text"
                    value={collabA}
                    onChange={(e) => setCollabA(e.target.value)}
                    className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs text-white"
                  />
                </div>
                <div className="flex-1">
                  <label htmlFor="collab-b" className="block text-[11px] font-bold uppercase text-slate-300 mb-1">
                    Profissional B
                  </label>
                  <input
                    id="collab-b"
                    type="text"
                    value={collabB}
                    onChange={(e) => setCollabB(e.target.value)}
                    className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs text-white"
                  />
                </div>
                <button
                  type="submit"
                  className="min-h-[44px] px-5 rounded-xl text-xs font-bold bg-brand-red text-white hover:bg-brand-redHover cursor-pointer"
                >
                  Cruzar Filmografias
                </button>
              </form>

              {collabResult && (
                <div className="pt-3 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {collabResult.shared_works.map((sw) => (
                    <button
                      type="button"
                      key={sw.id}
                      onClick={() => handleOpenDossier(sw.id)}
                      className="text-left p-3 rounded-xl bg-canvas border border-white/10 hover:border-brand-red flex items-center justify-between cursor-pointer"
                    >
                      <div>
                        <h4 className="text-xs font-bold text-white">{sw.title}</h4>
                        <p className="text-[11px] text-slate-300">
                          {sw.release_year} • {WORK_TYPE_LABELS[sw.work_type] || sw.work_type}
                        </p>
                      </div>
                      {sw.canonical_rating > 0 && (
                        <span className="text-xs font-bold text-yellow-300 flex items-center gap-1">
                          <Star className="w-3 h-3 fill-yellow-400" />
                          {sw.canonical_rating.toFixed(1)}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="space-y-2 max-h-[550px] overflow-y-auto pr-1">
                {peopleList.map((p) => (
                  <button
                    type="button"
                    key={p.id}
                    onClick={() => api.explore.getPersonDossier(p.id).then(setSelectedPerson)}
                    className={`w-full min-h-[44px] text-left p-3 rounded-xl border flex items-center justify-between cursor-pointer ${
                      selectedPerson?.id === p.id
                        ? "bg-brand-red/15 border-brand-red text-white"
                        : "bg-surface border-white/10 hover:border-white/25 text-slate-200"
                    }`}
                  >
                    <div>
                      <div className="text-sm font-bold">{p.name}</div>
                      <div className="text-[11px] text-slate-300">
                        {p.known_for_department} • {p.works_count} obras
                      </div>
                    </div>
                    <div className="text-xs font-bold text-yellow-300 flex items-center gap-1">
                      <Star className="w-3 h-3 fill-yellow-400" />
                      {p.average_rating.toFixed(1)}
                    </div>
                  </button>
                ))}
              </div>

              <div className="lg:col-span-2">
                {selectedPerson && (
                  <div className="p-6 rounded-2xl bg-surface border border-white/10 space-y-5">
                    <div>
                      <h2 className="text-2xl font-extrabold text-white">{selectedPerson.name}</h2>
                      <p className="text-xs text-slate-300 mt-0.5">
                        {selectedPerson.known_for_department}{" "}
                        {selectedPerson.country ? `• ${selectedPerson.country}` : ""}
                      </p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {selectedPerson.filmography.map((f) => (
                        <button
                          type="button"
                          key={f.work_id}
                          onClick={() => handleOpenDossier(f.work_id)}
                          className="text-left p-3 rounded-xl bg-surface-elevated border border-white/10 hover:border-brand-red/50 flex items-center justify-between cursor-pointer"
                        >
                          <div>
                            <div className="text-sm font-bold text-white">{f.title}</div>
                            <div className="text-[11px] text-slate-300">
                              {f.release_year || f.status} •{" "}
                              {WORK_TYPE_LABELS[f.work_type] || f.work_type}
                            </div>
                          </div>
                          {f.canonical_rating > 0 && (
                            <div className="text-xs font-bold text-yellow-300 flex items-center gap-1">
                              <Star className="w-3.5 h-3.5 fill-yellow-400" />
                              {f.canonical_rating.toFixed(1)}
                            </div>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ===================================================================== */}
        {/* SUB-MODE 3: RELEASE CALENDAR                                          */}
        {/* ===================================================================== */}
        {subMode === "calendar" && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Calendar className="w-5 h-5 text-brand-red" />
                Agenda Unificada de Estreias
              </h2>
              <div className="flex items-center gap-2">
                {["", "confirmed", "estimated", "announced"].map((lvl) => (
                  <button
                    type="button"
                    key={lvl || "all"}
                    onClick={() => setCalendarConfidenceFilter(lvl)}
                    className={`min-h-[44px] px-3.5 rounded-xl text-xs font-bold border cursor-pointer ${
                      calendarConfidenceFilter === lvl
                        ? "bg-brand-red text-white border-brand-red"
                        : "bg-surface-elevated text-slate-200 border-white/10"
                    }`}
                  >
                    {lvl === "" ? "Todos" : CONFIDENCE_BADGES[lvl]?.label || lvl}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {calendarEvents.map((ev) => {
                const badge = CONFIDENCE_BADGES[ev.confidence_level] || {
                  label: ev.confidence_level,
                  color: "bg-white/10 text-white border-white/20",
                };
                return (
                  <button
                    type="button"
                    key={ev.id}
                    onClick={() => ev.work_id && handleOpenDossier(ev.work_id)}
                    className="text-left p-4 rounded-2xl bg-surface border border-white/10 hover:border-brand-red/50 flex items-start justify-between gap-4 cursor-pointer"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded-md bg-brand-red/20 text-brand-red text-xs font-black">
                          {ev.event_date}
                        </span>
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${badge.color}`}>
                          {badge.label}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-white">{ev.event_title}</h3>
                      <p className="text-xs text-slate-300">
                        Obra: <strong className="text-white">{ev.work_title}</strong> • {ev.territory}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ===================================================================== */}
      {/* CANONICAL WORK DOSSIER MODAL                                          */}
      {/* ===================================================================== */}
      {selectedDossier && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto"
          onClick={() => setSelectedDossier(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl bg-surface border border-white/15 shadow-2xl p-6 space-y-6"
          >
            <button
              type="button"
              onClick={() => setSelectedDossier(null)}
              aria-label="Fechar dossiê"
              className="absolute top-4 right-4 min-w-[44px] min-h-[44px] rounded-full flex items-center justify-center bg-black/60 text-slate-200 hover:text-white cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex flex-col sm:flex-row gap-6">
              {selectedDossier.poster_url && (
                <img
                  src={selectedDossier.poster_url}
                  alt={selectedDossier.title}
                  className="w-36 sm:w-44 aspect-[2/3] object-cover rounded-xl border border-white/10 shrink-0"
                />
              )}
              <div className="space-y-3 flex-1 pr-8">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-md bg-brand-red text-white text-xs font-black uppercase">
                    {WORK_TYPE_LABELS[selectedDossier.work_type] || selectedDossier.work_type}
                  </span>
                  <StatusBadge status={selectedDossier.status} />
                  {(selectedDossier.streaming_providers || []).map((prov) => (
                    <ProviderBadge key={prov} provider={prov} />
                  ))}
                  {(selectedDossier.has_media || selectedDossier.eztv_available) && (
                    <MediaBadge sources={selectedDossier.media_sources || ["eztv"]} />
                  )}
                </div>

                <h2 className="text-2xl sm:text-3xl font-extrabold text-white">
                  {selectedDossier.title}
                </h2>
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
                  {selectedDossier.release_year && (
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-brand-red" />
                      {selectedDossier.release_year}
                    </span>
                  )}
                  {selectedDossier.runtime_minutes && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-brand-red" />
                      {selectedDossier.runtime_minutes} min
                    </span>
                  )}
                  {selectedDossier.origin_country && (
                    <span className="flex items-center gap-1">
                      <Globe className="w-3.5 h-3.5 text-brand-red" />
                      {selectedDossier.origin_country} ({selectedDossier.original_language.toUpperCase()})
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-200 leading-relaxed">{selectedDossier.overview}</p>

                <div className="pt-2 flex flex-wrap items-center gap-3">
                  {Object.entries(selectedDossier.ratings_breakdown || {}).map(([src, val]) => (
                    <div
                      key={src}
                      className="px-3 py-1.5 rounded-xl bg-surface-elevated border border-yellow-500/20 flex items-center gap-2"
                    >
                      <Award className="w-4 h-4 text-yellow-400" />
                      <div className="text-xs font-extrabold text-white">
                        {val.rating.toFixed(1)}{" "}
                        <span className="text-[10px] uppercase text-yellow-300">{src}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pt-2 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => onSaveToLibrary(convertWorkToUnified(selectedDossier))}
                    className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl text-xs font-bold bg-brand-red text-white hover:bg-brand-redHover cursor-pointer"
                  >
                    <Bookmark className="w-4 h-4" />
                    Adicionar à Biblioteca
                  </button>
                  {selectedDossier.imdb_id && (
                    <button
                      type="button"
                      onClick={() => {
                        const u = convertWorkToUnified(selectedDossier);
                        setSelectedDossier(null);
                        onOpenTorrents(u);
                      }}
                      className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl text-xs font-bold bg-surface-elevated text-slate-100 hover:text-white border border-white/15 cursor-pointer"
                    >
                      <Download className="w-4 h-4 text-emerald-400" />
                      Abrir Fontes de Mídia
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
