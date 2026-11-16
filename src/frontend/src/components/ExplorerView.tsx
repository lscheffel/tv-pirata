import React, { useState, useEffect, useCallback } from "react";
import {
  Compass,
  Filter,
  Users,
  Calendar,
  Star,
  Clock,
  Tv,
  Sparkles,
  Database,
  X,
  Bookmark,
  Download,
  Award,
  Globe,
  GitMerge,
} from "lucide-react";
import {
  CalendarEventItem,
  DiscoveryFacets,
  MediaWorkDossier,
  MediaWorkSummary,
  PersonDossier,
  PersonSummary,
  SharedCollaborationResponse,
  UnifiedShow,
} from "../types";
import { api } from "../services/api";
import { useToast } from "../context/ToastContext";
import { EztvBadge } from "./EztvBadge";
import { ProviderBadge, StatusBadge } from "./ShowBadges";

interface ExplorerViewProps {
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary: (show: UnifiedShow) => void;
  savedShowIds: Set<number>;
}

const WORK_TYPE_LABELS: Record<string, string> = {
  movie: "Filme",
  tv_show: "Série de TV",
  mini_series: "Minissérie",
  documentary: "Documentário",
  animation: "Animação",
  special: "Especial",
};

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

export const ExplorerView: React.FC<ExplorerViewProps> = ({
  onOpenTorrents,
  onSaveToLibrary,
  savedShowIds,
}) => {
  const { showToast } = useToast();
  const [subMode, setSubMode] = useState<"filters" | "people" | "calendar">("filters");

  // --- Advanced Filter State ---
  const [queryText, setQueryText] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [genresAny, setGenresAny] = useState<string[]>([]);
  const [genresAll, setGenresAll] = useState<string[]>([]);
  const [genresNot, setGenresNot] = useState<string[]>([]);
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [yearFrom, setYearFrom] = useState<string>("");
  const [yearTo, setYearTo] = useState<string>("");
  const [minRating, setMinRating] = useState<number>(0);
  const [minRuntime, setMinRuntime] = useState<string>("");
  const [personFilter, setPersonFilter] = useState<string>("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [excludeWatched, setExcludeWatched] = useState<boolean>(false);
  const [onlyWithP2P, setOnlyWithP2P] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<string>("rating");

  // --- Results & Facets State ---
  const [works, setWorks] = useState<MediaWorkSummary[]>([]);
  const [totalWorks, setTotalWorks] = useState<number>(0);
  const [facets, setFacets] = useState<DiscoveryFacets | null>(null);
  const [loadingWorks, setLoadingWorks] = useState<boolean>(true);
  const [selectedDossier, setSelectedDossier] = useState<MediaWorkDossier | null>(null);

  // --- People & Relationship Discovery State ---
  const [peopleList, setPeopleList] = useState<PersonSummary[]>([]);
  const [selectedPerson, setSelectedPerson] = useState<PersonDossier | null>(null);
  const [collabA, setCollabA] = useState<string>("Denis Villeneuve");
  const [collabB, setCollabB] = useState<string>("Rebecca Ferguson");
  const [collabResult, setCollabResult] = useState<SharedCollaborationResponse | null>(null);

  // --- Calendar State ---
  const [calendarEvents, setCalendarEvents] = useState<CalendarEventItem[]>([]);
  const [calendarConfidenceFilter, setCalendarConfidenceFilter] = useState<string>("");

  const executeExploreQuery = useCallback(() => {
    setLoadingWorks(true);
    api.explore
      .getWorks({
        q: queryText.trim() || undefined,
        work_types: selectedTypes.length > 0 ? selectedTypes.join(",") : undefined,
        genres_any: genresAny.length > 0 ? genresAny.join(",") : undefined,
        genres_all: genresAll.length > 0 ? genresAll.join(",") : undefined,
        genres_not: genresNot.length > 0 ? genresNot.join(",") : undefined,
        streaming_providers:
          selectedProviders.length > 0 ? selectedProviders.join(",") : undefined,
        year_from: yearFrom ? parseInt(yearFrom, 10) : undefined,
        year_to: yearTo ? parseInt(yearTo, 10) : undefined,
        min_rating: minRating > 0 ? minRating : undefined,
        min_runtime: minRuntime ? parseInt(minRuntime, 10) : undefined,
        person_query: personFilter.trim() || undefined,
        role_type: roleFilter || undefined,
        exclude_watched: excludeWatched || undefined,
        only_with_p2p: onlyWithP2P || undefined,
        sort_by: sortBy,
        page_size: 48,
      })
      .then((res) => {
        setWorks(res.items);
        setTotalWorks(res.total);
        setFacets(res.facets);
      })
      .catch((err) => {
        console.error("Erro ao consultar motor de descoberta:", err);
        showToast("Erro ao consultar catálogo unificado", "error");
      })
      .finally(() => setLoadingWorks(false));
  }, [
    queryText,
    selectedTypes,
    genresAny,
    genresAll,
    genresNot,
    selectedProviders,
    yearFrom,
    yearTo,
    minRating,
    minRuntime,
    personFilter,
    roleFilter,
    excludeWatched,
    onlyWithP2P,
    sortBy,
    showToast,
  ]);

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
        .catch((err) => console.error("Erro ao carregar pessoas:", err));

      api.explore
        .getCollaborations(collabA, collabB)
        .then(setCollabResult)
        .catch(() => {});
    } else if (subMode === "calendar") {
      api.explore
        .getCalendar({
          confidence_level: calendarConfidenceFilter || undefined,
        })
        .then(setCalendarEvents)
        .catch((err) => console.error("Erro ao carregar calendário:", err));
    }
  }, [subMode, calendarConfidenceFilter]);

  const handleOpenDossier = async (workId: number) => {
    try {
      const dossier = await api.explore.getWorkDossier(workId);
      setSelectedDossier(dossier);
    } catch {
      showToast("Erro ao abrir dossiê canônico da obra", "error");
    }
  };

  const handleToggleType = (typeKey: string) => {
    setSelectedTypes((prev) =>
      prev.includes(typeKey) ? prev.filter((t) => t !== typeKey) : [...prev, typeKey]
    );
  };

  // Cycle Genre State: None -> OR (any) -> AND (all) -> NOT (exclude) -> None
  const handleCycleGenre = (genreName: string) => {
    if (genresAny.includes(genreName)) {
      setGenresAny((prev) => prev.filter((g) => g !== genreName));
      setGenresAll((prev) => [...prev, genreName]);
    } else if (genresAll.includes(genreName)) {
      setGenresAll((prev) => prev.filter((g) => g !== genreName));
      setGenresNot((prev) => [...prev, genreName]);
    } else if (genresNot.includes(genreName)) {
      setGenresNot((prev) => prev.filter((g) => g !== genreName));
    } else {
      setGenresAny((prev) => [...prev, genreName]);
    }
  };

  const handleToggleProvider = (prov: string) => {
    setSelectedProviders((prev) =>
      prev.includes(prov) ? prev.filter((p) => p !== prov) : [...prev, prov]
    );
  };

  const handleResetFilters = () => {
    setQueryText("");
    setSelectedTypes([]);
    setGenresAny([]);
    setGenresAll([]);
    setGenresNot([]);
    setSelectedProviders([]);
    setYearFrom("");
    setYearTo("");
    setMinRating(0);
    setMinRuntime("");
    setPersonFilter("");
    setRoleFilter("");
    setExcludeWatched(false);
    setOnlyWithP2P(false);
    setSortBy("rating");
  };

  const applyPreset = (presetId: string) => {
    handleResetFilters();
    if (presetId === "scifi_thriller") {
      setSelectedTypes(["movie"]);
      setGenresAny(["Ficção Científica", "Suspense"]);
      setYearFrom("2014");
      setYearTo("2026");
      setMinRating(7.5);
      setMinRuntime("100");
    } else if (presetId === "villeneuve") {
      setPersonFilter("Denis Villeneuve");
      setRoleFilter("director");
    } else if (presetId === "nolan") {
      setPersonFilter("Christopher Nolan");
      setRoleFilter("director");
    } else if (presetId === "crime_series") {
      setSelectedTypes(["tv_show", "mini_series"]);
      setGenresAny(["Crime & Investigação"]);
      setMinRating(8.0);
    } else if (presetId === "upcoming_2026") {
      setYearFrom("2026");
      setSortBy("popularity");
    }
  };

  const convertWorkToUnified = (w: MediaWorkSummary): UnifiedShow => ({
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
    source_provider: w.rating_source || "federated-catalog",
    seasons: [],
  });

  const handleJumpToPerson = async (personName: string) => {
    setSelectedDossier(null);
    setSubMode("people");
    const list = await api.explore.getPeople(personName);
    if (list.length > 0) {
      const dossier = await api.explore.getPersonDossier(list[0].id);
      setSelectedPerson(dossier);
    } else {
      setSubMode("filters");
      setPersonFilter(personName);
    }
  };

  const handleRunCollaborationSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!collabA.trim() || !collabB.trim()) return;
    try {
      const res = await api.explore.getCollaborations(collabA.trim(), collabB.trim());
      setCollabResult(res);
    } catch {
      showToast("Erro ao buscar colaborações compartilhadas", "error");
    }
  };

  const availableGenres = [
    "Ficção Científica",
    "Suspense",
    "Drama",
    "Crime & Investigação",
    "Mistério",
    "Aventura",
    "Ação",
    "História",
    "Documentário",
    "Animação",
    "Fantasia",
    "Comédia",
    "Biografia",
    "Guerra & Política",
  ];

  const availableProviders = [
    "Netflix",
    "Max",
    "Prime Video",
    "Apple TV+",
    "Disney+",
    "MUBI",
    "Globoplay",
    "Paramount+",
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16 space-y-8">
      {/* Header & Perspective Switcher */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-white/10 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <Compass className="w-8 h-8 text-brand-red" />
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Audiovisual Discovery Engine
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-brand-red/20 text-brand-red border border-brand-red/30">
              CAMADA 1 • FEDERADO
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Exploração profunda multi-formato (Filmes, Séries, Minisséries, Documentários) com
            resolução de identidade, procedência e filtros relacionais
          </p>
        </div>

        {/* Sub-Mode Tabs */}
        <div className="flex items-center gap-2 bg-surface-elevated p-1.5 rounded-2xl border border-white/10 self-start">
          <button
            onClick={() => setSubMode("filters")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              subMode === "filters"
                ? "bg-brand-red text-white shadow-cinema-glow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            Motor de Filtros ({totalWorks})
          </button>
          <button
            onClick={() => setSubMode("people")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              subMode === "people"
                ? "bg-brand-red text-white shadow-cinema-glow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            Pessoas & Relações
          </button>
          <button
            onClick={() => setSubMode("calendar")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              subMode === "calendar"
                ? "bg-brand-red text-white shadow-cinema-glow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Calendar className="w-3.5 h-3.5" />
            Agenda & Estreias
          </button>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* SUB-MODE 1: ADVANCED FILTERING ENGINE & DYNAMIC FACETS                */}
      {/* ===================================================================== */}
      {subMode === "filters" && (
        <div className="space-y-6">
          {/* Quick Analytical Presets Bar */}
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
            <span className="text-xs font-bold text-slate-400 shrink-0 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-brand-red" />
              Consultas Analíticas:
            </span>
            <button
              onClick={() => applyPreset("scifi_thriller")}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-elevated hover:bg-white/10 text-slate-200 border border-white/10 whitespace-nowrap transition-colors"
            >
              Filmes Sci-Fi/Suspense (2014–2026, Nota ≥ 7.5, &gt;100m)
            </button>
            <button
              onClick={() => applyPreset("villeneuve")}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-elevated hover:bg-white/10 text-slate-200 border border-white/10 whitespace-nowrap transition-colors"
            >
              Direção: Denis Villeneuve
            </button>
            <button
              onClick={() => applyPreset("nolan")}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-elevated hover:bg-white/10 text-slate-200 border border-white/10 whitespace-nowrap transition-colors"
            >
              Direção: Christopher Nolan
            </button>
            <button
              onClick={() => applyPreset("crime_series")}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-elevated hover:bg-white/10 text-slate-200 border border-white/10 whitespace-nowrap transition-colors"
            >
              Séries de Investigação Criminal (Nota ≥ 8.0)
            </button>
            <button
              onClick={() => applyPreset("upcoming_2026")}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-elevated hover:bg-white/10 text-slate-200 border border-white/10 whitespace-nowrap transition-colors"
            >
              Estreias & Anúncios 2026
            </button>
            <button
              onClick={handleResetFilters}
              className="px-3 py-1.5 rounded-xl text-xs font-bold text-brand-red hover:bg-brand-red/10 whitespace-nowrap transition-colors"
            >
              Limpar Filtros
            </button>
          </div>

          {/* Multi-Dimensional Filter Control Box */}
          <div className="p-5 rounded-2xl bg-surface-elevated/90 border border-white/10 shadow-2xl space-y-5">
            {/* Row 1: Text Search, Person Filter, Role, Sort */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                  Pesquisa Contextual Livre
                </label>
                <input
                  type="text"
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder="Título, franquia, tema, estúdio..."
                  className="w-full bg-canvas border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-red"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                  Pessoa (Ator, Diretor, Criador)
                </label>
                <input
                  type="text"
                  value={personFilter}
                  onChange={(e) => setPersonFilter(e.target.value)}
                  placeholder="Ex: Denis Villeneuve, Cillian Murphy..."
                  className="w-full bg-canvas border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-red"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                  Função na Obra
                </label>
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="w-full bg-canvas border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-red"
                >
                  <option value="">Qualquer função (Elenco ou Equipe)</option>
                  <option value="director">Diretor(a)</option>
                  <option value="creator">Criador(a) / Showrunner</option>
                  <option value="actor">Ator / Atriz</option>
                  <option value="writer">Roteirista</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                  Ordenar Resultados Por
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="w-full bg-canvas border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-red"
                >
                  <option value="rating">Maior Avaliação Canônica</option>
                  <option value="popularity">Maior Popularidade / Tendência</option>
                  <option value="year_desc">Lançamento Mais Recente</option>
                  <option value="year_asc">Lançamento Mais Antigo</option>
                  <option value="runtime">Maior Duração (Minutos)</option>
                  <option value="title">Ordem Alfabética (A-Z)</option>
                </select>
              </div>
            </div>

            {/* Row 2: Format Pills + Quantitative Filters (Years, Rating, Runtime, Checkboxes) */}
            <div className="flex flex-wrap items-end justify-between gap-4 pt-2 border-t border-white/5">
              <div className="space-y-1.5">
                <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Formato Audiovisual
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(WORK_TYPE_LABELS).map(([key, label]) => {
                    const active = selectedTypes.includes(key);
                    const facetCount =
                      facets?.work_types.find((f) => f.key === key)?.count ?? 0;
                    return (
                      <button
                        key={key}
                        onClick={() => handleToggleType(key)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 border ${
                          active
                            ? "bg-brand-red text-white border-brand-red shadow-cinema-glow"
                            : "bg-canvas text-slate-300 border-white/10 hover:border-white/25"
                        }`}
                      >
                        <span>{label}</span>
                        <span className="text-[10px] opacity-75">({facetCount})</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
                    Ano Inicial
                  </label>
                  <input
                    type="number"
                    placeholder="1970"
                    value={yearFrom}
                    onChange={(e) => setYearFrom(e.target.value)}
                    className="w-20 bg-canvas border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
                    Ano Final
                  </label>
                  <input
                    type="number"
                    placeholder="2026"
                    value={yearTo}
                    onChange={(e) => setYearTo(e.target.value)}
                    className="w-20 bg-canvas border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
                    Nota Mín: {minRating > 0 ? minRating.toFixed(1) : "Todas"}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="9"
                    step="0.5"
                    value={minRating}
                    onChange={(e) => setMinRating(parseFloat(e.target.value))}
                    className="w-28 accent-brand-red cursor-pointer"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold uppercase text-slate-400 mb-1">
                    Duração Mín (min)
                  </label>
                  <input
                    type="number"
                    placeholder="Ex: 100"
                    value={minRuntime}
                    onChange={(e) => setMinRuntime(e.target.value)}
                    className="w-24 bg-canvas border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
              </div>
            </div>

            {/* Row 3: Boolean Genre Matrix (OR / AND / NOT) */}
            <div className="pt-2 border-t border-white/5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Gêneros Combináveis (Clique 1x = <span className="text-brand-red">OR</span> • 2x ={" "}
                  <span className="text-emerald-400">AND</span> • 3x ={" "}
                  <span className="text-rose-400 line-through">NOT</span>)
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {availableGenres.map((g) => {
                  const isOr = genresAny.includes(g);
                  const isAnd = genresAll.includes(g);
                  const isNot = genresNot.includes(g);
                  const count = facets?.genres.find((fg) => fg.key === g)?.count ?? 0;

                  let btnStyle =
                    "bg-canvas text-slate-300 border-white/10 hover:border-white/25";
                  let prefix = "";
                  if (isOr) {
                    btnStyle = "bg-brand-red/20 text-brand-red border-brand-red font-extrabold";
                    prefix = "OR: ";
                  } else if (isAnd) {
                    btnStyle =
                      "bg-emerald-500/20 text-emerald-300 border-emerald-500 font-extrabold";
                    prefix = "AND: ";
                  } else if (isNot) {
                    btnStyle =
                      "bg-rose-950/60 text-rose-400 border-rose-500/40 line-through opacity-80";
                    prefix = "NOT: ";
                  }

                  return (
                    <button
                      key={g}
                      onClick={() => handleCycleGenre(g)}
                      className={`px-2.5 py-1 rounded-lg text-xs border transition-all flex items-center gap-1 ${btnStyle}`}
                    >
                      <span>
                        {prefix}
                        {g}
                      </span>
                      <span className="text-[10px] opacity-70">({count})</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Row 4: Streaming Platforms & Ecosystem Toggles */}
            <div className="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <span className="block text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Disponibilidade em Serviços de Streaming
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {availableProviders.map((prov) => {
                    const active = selectedProviders.includes(prov);
                    const count =
                      facets?.streaming_providers.find((fp) => fp.key === prov)?.count ?? 0;
                    return (
                      <button
                        key={prov}
                        onClick={() => handleToggleProvider(prov)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition-all flex items-center gap-1 ${
                          active
                            ? "bg-white text-black border-white shadow-md"
                            : "bg-canvas text-slate-300 border-white/10 hover:border-white/25"
                        }`}
                      >
                        <Tv className="w-3 h-3" />
                        <span>{prov}</span>
                        <span className="text-[10px] opacity-70">({count})</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center gap-4 shrink-0">
                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={excludeWatched}
                    onChange={(e) => setExcludeWatched(e.target.checked)}
                    className="rounded accent-brand-red"
                  />
                  <span>Ocultar já assistidos</span>
                </label>

                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={onlyWithP2P}
                    onChange={(e) => setOnlyWithP2P(e.target.checked)}
                    className="rounded accent-brand-red"
                  />
                  <span>Com Seeds P2P</span>
                </label>
              </div>
            </div>
          </div>

          {/* Works Grid */}
          {loadingWorks ? (
            <div className="py-20 text-center text-slate-500 animate-pulse">
              Executando consulta multidimensional no catálogo federado...
            </div>
          ) : works.length === 0 ? (
            <div className="py-20 text-center rounded-2xl border border-dashed border-white/10 bg-surface/40 p-8 space-y-3">
              <Compass className="w-12 h-12 mx-auto text-slate-600" />
              <h3 className="text-lg font-bold text-slate-300">
                Nenhuma obra corresponde à combinação de filtros
              </h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Experimente relaxar restrições booleanas (AND/NOT) ou limpar os filtros ativos.
              </p>
              <button
                onClick={handleResetFilters}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-brand-red text-white"
              >
                Restaurar Todos os Filtros
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-5">
              {works.map((w) => {
                const unified = convertWorkToUnified(w);
                const isSaved =
                  savedShowIds.has(unified.id) ||
                  (w.tmdb_id ? savedShowIds.has(w.tmdb_id) : false);

                return (
                  <div
                    key={w.id}
                    onClick={() => handleOpenDossier(w.id)}
                    className="group relative flex flex-col rounded-xl overflow-hidden bg-surface border border-white/5 hover:border-brand-red/50 transition-all hover:scale-[1.02] shadow-xl cursor-pointer"
                  >
                    {/* Poster */}
                    <div className="relative aspect-[2/3] w-full bg-surface-elevated overflow-hidden">
                      {w.poster_url ? (
                        <img
                          src={w.poster_url}
                          alt={w.title}
                          loading="lazy"
                          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                        />
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center bg-gradient-to-br from-surface-elevated to-canvas">
                          <span className="text-xs font-extrabold text-white">{w.title}</span>
                          <span className="text-[10px] text-slate-400 mt-1">
                            {w.release_year || w.status}
                          </span>
                        </div>
                      )}

                      {/* Format Badge */}
                      <div className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-[10px] font-extrabold uppercase tracking-wider text-white border border-white/15">
                        {WORK_TYPE_LABELS[w.work_type] || w.work_type}
                      </div>

                      {/* Rating Badge with Source Provenance */}
                      {w.canonical_rating > 0 && (
                        <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-yellow-400 text-xs font-bold border border-yellow-500/20">
                          <Star className="w-3 h-3 fill-yellow-400" />
                          <span>{w.canonical_rating.toFixed(1)}</span>
                          <span className="text-[9px] uppercase text-slate-300 ml-0.5">
                            {w.rating_source}
                          </span>
                        </div>
                      )}

                      {/* Permanent Status & Provider Badges + EZTV Badge */}
                      {(w.status || w.streaming_providers.length > 0 || w.network_or_studio || w.eztv_available) && (
                        <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between gap-1">
                          <div className="flex flex-wrap gap-1">
                            <StatusBadge status={w.status} compact />
                            {(w.streaming_providers.length > 0
                              ? w.streaming_providers.slice(0, 1)
                              : w.network_or_studio
                                ? [w.network_or_studio]
                                : []
                            ).map((sp) => (
                              <ProviderBadge key={sp} provider={sp} compact />
                            ))}
                          </div>
                          {w.eztv_available && (
                            <div className="ml-auto shrink-0">
                              <EztvBadge compact />
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Metadata Footer */}
                    <div className="p-3 flex-1 flex flex-col justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-bold text-white line-clamp-1 group-hover:text-brand-red transition-colors">
                          {w.title}
                        </h3>
                        <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                          {w.release_year && <span>{w.release_year}</span>}
                          {w.runtime_minutes && <span>• {w.runtime_minutes}m</span>}
                          {w.origin_country && <span>• {w.origin_country}</span>}
                        </div>
                        {w.directors.length > 0 && (
                          <p className="text-[11px] text-slate-300 mt-1 line-clamp-1">
                            Dir: <span className="font-semibold">{w.directors.join(", ")}</span>
                          </p>
                        )}
                      </div>

                      <div className="flex flex-wrap gap-1 pt-1 border-t border-white/5">
                        {w.genres.slice(0, 2).map((g) => (
                          <span
                            key={g}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-surface-elevated text-slate-300"
                          >
                            {g}
                          </span>
                        ))}
                        {isSaved && (
                          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                            Na Lista
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ===================================================================== */}
      {/* SUB-MODE 2: RELATIONSHIP DISCOVERY (PEOPLE & COLLABORATIONS)          */}
      {/* ===================================================================== */}
      {subMode === "people" && (
        <div className="space-y-8">
          {/* Shared Collaborations Finder */}
          <div className="p-5 rounded-2xl bg-surface-elevated border border-white/10 shadow-xl space-y-4">
            <div className="flex items-center gap-2">
              <GitMerge className="w-5 h-5 text-brand-red" />
              <h2 className="text-base font-bold text-white">
                Descoberta Relacional: Obras em que Trabalharam Juntos
              </h2>
            </div>
            <form
              onSubmit={handleRunCollaborationSearch}
              className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3"
            >
              <div className="flex-1">
                <label className="block text-[11px] font-bold uppercase text-slate-400 mb-1">
                  Profissional A (Ator, Diretor, Criador)
                </label>
                <input
                  type="text"
                  value={collabA}
                  onChange={(e) => setCollabA(e.target.value)}
                  className="w-full bg-canvas border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                />
              </div>
              <div className="flex-1">
                <label className="block text-[11px] font-bold uppercase text-slate-400 mb-1">
                  Profissional B (Ator, Diretor, Criador)
                </label>
                <input
                  type="text"
                  value={collabB}
                  onChange={(e) => setCollabB(e.target.value)}
                  className="w-full bg-canvas border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                />
              </div>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl text-xs font-bold bg-brand-red text-white hover:bg-red-700 transition-colors"
              >
                Cruzar Filmografias
              </button>
            </form>

            {collabResult && (
              <div className="pt-3 border-t border-white/10">
                <p className="text-xs text-slate-300 mb-3">
                  Interseção entre <strong className="text-white">{collabResult.person_a}</strong> e{" "}
                  <strong className="text-white">{collabResult.person_b}</strong>:{" "}
                  <span className="text-brand-red font-bold">
                    {collabResult.shared_works.length} obra(s) compartilhada(s)
                  </span>
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {collabResult.shared_works.map((sw) => (
                    <div
                      key={sw.id}
                      onClick={() => handleOpenDossier(sw.id)}
                      className="p-3 rounded-xl bg-canvas border border-white/10 hover:border-brand-red flex items-center justify-between cursor-pointer transition-all"
                    >
                      <div>
                        <h4 className="text-xs font-bold text-white">{sw.title}</h4>
                        <p className="text-[11px] text-slate-400">
                          {sw.release_year} • {WORK_TYPE_LABELS[sw.work_type] || sw.work_type}
                        </p>
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          {sw.person_a_role} + {sw.person_b_role}
                        </p>
                      </div>
                      {sw.canonical_rating > 0 && (
                        <span className="text-xs font-bold text-yellow-400 flex items-center gap-1">
                          <Star className="w-3 h-3 fill-yellow-400" />
                          {sw.canonical_rating.toFixed(1)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* People Directory & Active Person Dossier */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="space-y-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                Diretores, Criadores & Elenco Indexados ({peopleList.length})
              </h3>
              <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                {peopleList.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => api.explore.getPersonDossier(p.id).then(setSelectedPerson)}
                    className={`w-full text-left p-3 rounded-xl border transition-all flex items-center justify-between ${
                      selectedPerson?.id === p.id
                        ? "bg-brand-red/15 border-brand-red text-white"
                        : "bg-surface border-white/5 hover:border-white/20 text-slate-200"
                    }`}
                  >
                    <div>
                      <div className="text-sm font-bold">{p.name}</div>
                      <div className="text-[11px] text-slate-400">
                        {p.known_for_department} • {p.works_count} obras
                      </div>
                    </div>
                    <div className="text-xs font-bold text-yellow-400 flex items-center gap-1">
                      <Star className="w-3 h-3 fill-yellow-400" />
                      {p.average_rating.toFixed(1)}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Person Filmography & Frequent Collaborators */}
            <div className="lg:col-span-2">
              {selectedPerson ? (
                <div className="p-6 rounded-2xl bg-surface border border-white/10 space-y-6">
                  <div className="flex items-center justify-between border-b border-white/10 pb-4">
                    <div>
                      <h2 className="text-2xl font-extrabold text-white">
                        {selectedPerson.name}
                      </h2>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Departamento: {selectedPerson.known_for_department}{" "}
                        {selectedPerson.country ? `• País: ${selectedPerson.country}` : ""}
                      </p>
                    </div>
                  </div>

                  {/* Frequent Collaborators */}
                  {selectedPerson.frequent_collaborators.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2.5">
                        Colaboradores Recorrentes
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedPerson.frequent_collaborators.map((fc) => (
                          <button
                            key={fc.person_id}
                            onClick={() =>
                              api.explore.getPersonDossier(fc.person_id).then(setSelectedPerson)
                            }
                            className="px-3 py-1.5 rounded-xl bg-surface-elevated border border-white/10 hover:border-brand-red text-xs text-slate-200 flex items-center gap-2 transition-colors"
                          >
                            <span className="font-bold text-white">{fc.name}</span>
                            <span className="px-1.5 py-0.5 rounded bg-brand-red/20 text-brand-red text-[10px] font-extrabold">
                              {fc.shared_works_count}x
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Filmography */}
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                      Filmografia no Catálogo ({selectedPerson.filmography.length})
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {selectedPerson.filmography.map((f) => (
                        <div
                          key={f.work_id}
                          onClick={() => handleOpenDossier(f.work_id)}
                          className="p-3 rounded-xl bg-surface-elevated border border-white/5 hover:border-brand-red/50 flex items-center justify-between cursor-pointer transition-all"
                        >
                          <div>
                            <div className="text-sm font-bold text-white">{f.title}</div>
                            <div className="text-[11px] text-slate-400">
                              {f.release_year || f.status} •{" "}
                              {WORK_TYPE_LABELS[f.work_type] || f.work_type}
                            </div>
                            <div className="text-[11px] text-brand-red font-semibold mt-0.5">
                              {f.roles.join(", ")}
                              {f.character_name ? ` como ${f.character_name}` : ""}
                            </div>
                          </div>
                          {f.canonical_rating > 0 && (
                            <div className="text-xs font-bold text-yellow-400 flex items-center gap-1">
                              <Star className="w-3.5 h-3.5 fill-yellow-400" />
                              {f.canonical_rating.toFixed(1)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* SUB-MODE 3: RELEASE DISCOVERY & UNIFIED CALENDAR                      */}
      {/* ===================================================================== */}
      {subMode === "calendar" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Calendar className="w-5 h-5 text-brand-red" />
                Agenda Unificada de Estreias, Temporadas & Produções Anunciadas
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Distinção explícita entre datas confirmadas, estimadas e produções anunciadas
              </p>
            </div>

            <div className="flex items-center gap-2">
              {["", "confirmed", "estimated", "announced"].map((lvl) => (
                <button
                  key={lvl || "all"}
                  onClick={() => setCalendarConfidenceFilter(lvl)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ${
                    calendarConfidenceFilter === lvl
                      ? "bg-brand-red text-white border-brand-red"
                      : "bg-surface-elevated text-slate-300 border-white/10"
                  }`}
                >
                  {lvl === ""
                    ? "Todos os Eventos"
                    : CONFIDENCE_BADGES[lvl]?.label || lvl}
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
                <div
                  key={ev.id}
                  onClick={() => ev.work_id && handleOpenDossier(ev.work_id)}
                  className="p-4 rounded-2xl bg-surface border border-white/10 hover:border-brand-red/50 flex items-start justify-between gap-4 cursor-pointer transition-all"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-md bg-brand-red/20 text-brand-red text-xs font-black">
                        {ev.event_date}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${badge.color}`}
                      >
                        {badge.label}
                      </span>
                      {ev.platform_or_network && (
                        <span className="px-2 py-0.5 rounded-md bg-surface-elevated text-cyan-300 text-[10px] font-bold">
                          {ev.platform_or_network}
                        </span>
                      )}
                    </div>
                    <h3 className="text-base font-bold text-white">{ev.event_title}</h3>
                    <p className="text-xs text-slate-400">
                      Obra: <strong className="text-slate-200">{ev.work_title}</strong> • Território:{" "}
                      {ev.territory}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* CANONICAL WORK DOSSIER MODAL (PROVENANCE, CREDITS, SIMILARITY)        */}
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
              onClick={() => setSelectedDossier(null)}
              className="absolute top-4 right-4 p-2 rounded-full bg-black/60 text-slate-300 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Header Info */}
            <div className="flex flex-col sm:flex-row gap-6">
              {selectedDossier.poster_url && (
                <img
                  src={selectedDossier.poster_url}
                  alt={selectedDossier.title}
                  className="w-36 sm:w-44 aspect-[2/3] object-cover rounded-xl border border-white/10 shrink-0"
                />
              )}
              <div className="space-y-3 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-md bg-brand-red text-white text-xs font-black uppercase">
                    {WORK_TYPE_LABELS[selectedDossier.work_type] || selectedDossier.work_type}
                  </span>
                  <StatusBadge status={selectedDossier.status} />
                  {(selectedDossier.streaming_providers?.[0] || selectedDossier.network_or_studio) && (
                    <ProviderBadge
                      provider={
                        selectedDossier.streaming_providers?.[0] || selectedDossier.network_or_studio
                      }
                    />
                  )}
                  {selectedDossier.collection_name && (
                    <span className="px-2.5 py-0.5 rounded-md bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-bold">
                      Franquia: {selectedDossier.collection_name}
                    </span>
                  )}
                  {selectedDossier.eztv_available && <EztvBadge />}
                </div>

                <h2 className="text-2xl sm:text-3xl font-extrabold text-white">
                  {selectedDossier.title}
                </h2>
                {selectedDossier.original_title &&
                  selectedDossier.original_title !== selectedDossier.title && (
                    <p className="text-xs text-slate-400">
                      Título Original: <strong>{selectedDossier.original_title}</strong>
                    </p>
                  )}

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
                  {selectedDossier.network_or_studio && (
                    <span className="text-slate-400">• {selectedDossier.network_or_studio}</span>
                  )}
                </div>

                <p className="text-sm text-slate-200 leading-relaxed">
                  {selectedDossier.overview}
                </p>

                {/* Multi-Source Ratings Breakdown (No indiscriminate mixing) */}
                <div className="pt-2 flex flex-wrap items-center gap-3">
                  {Object.entries(selectedDossier.ratings_breakdown || {}).map(([src, val]) => (
                    <div
                      key={src}
                      className="px-3 py-1.5 rounded-xl bg-surface-elevated border border-yellow-500/20 flex items-center gap-2"
                    >
                      <Award className="w-4 h-4 text-yellow-400" />
                      <div>
                        <div className="text-xs font-extrabold text-white">
                          {val.rating.toFixed(1)}{" "}
                          <span className="text-[10px] uppercase text-yellow-400">{src}</span>
                        </div>
                        {val.votes > 0 && (
                          <div className="text-[10px] text-slate-400">
                            {val.votes.toLocaleString()} votos
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Action Buttons (Layer 2 Integration) */}
                <div className="pt-2 flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => onSaveToLibrary(convertWorkToUnified(selectedDossier))}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-brand-red text-white hover:bg-red-700 transition-colors"
                  >
                    <Bookmark className="w-4 h-4" />
                    Adicionar à Minha Lista
                  </button>
                  {selectedDossier.imdb_id && (
                    <button
                      onClick={() => {
                        const u = convertWorkToUnified(selectedDossier);
                        setSelectedDossier(null);
                        onOpenTorrents(u);
                      }}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-surface-elevated text-slate-200 hover:text-white border border-white/10 transition-colors"
                    >
                      <Download className="w-4 h-4 text-brand-red" />
                      Consultar Releases P2P
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Streaming Availability */}
            {selectedDossier.availabilities.length > 0 && (
              <div className="p-4 rounded-xl bg-surface-elevated border border-white/10 space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Tv className="w-3.5 h-3.5 text-cyan-400" />
                  Onde Assistir (Disponibilidade por Plataforma e Território)
                </h4>
                <div className="flex flex-wrap gap-2">
                  {selectedDossier.availabilities.map((av, idx) => (
                    <div
                      key={idx}
                      className="px-3 py-1.5 rounded-lg bg-canvas border border-cyan-500/30 text-xs flex items-center gap-2"
                    >
                      <span className="font-bold text-white">{av.provider_name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 uppercase">
                        {av.territory} • {av.monetization_type}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Cast, Direction & Crew (Clickable for Filmography) */}
            {selectedDossier.credits.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Elenco, Direção & Equipe Criativa (Clique para explorar filmografia)
                </h4>
                <div className="flex flex-wrap gap-2">
                  {selectedDossier.credits.map((cr, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleJumpToPerson(cr.name)}
                      className="px-3 py-1.5 rounded-xl bg-surface-elevated hover:bg-brand-red/20 border border-white/10 hover:border-brand-red text-left transition-all"
                    >
                      <div className="text-xs font-bold text-white">{cr.name}</div>
                      <div className="text-[10px] text-slate-400">
                        {cr.role_type.toUpperCase()}
                        {cr.character_name ? ` • ${cr.character_name}` : ""}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Explicit Relations (Sequels, Prequels, Remakes, Spinoffs) */}
            {selectedDossier.explicit_relations.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Relações Canônicas entre Obras (Sequências, Prequelas, Remakes, Spin-offs)
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {selectedDossier.explicit_relations.map((rel) => (
                    <div
                      key={rel.work_id}
                      onClick={() => handleOpenDossier(rel.work_id)}
                      className="p-3 rounded-xl bg-surface-elevated border border-white/10 hover:border-brand-red cursor-pointer flex items-center justify-between"
                    >
                      <div>
                        <span className="text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-brand-red/20 text-brand-red">
                          {rel.relation_type}
                        </span>
                        <div className="text-xs font-bold text-white mt-1">
                          {rel.title} ({rel.release_year})
                        </div>
                        {rel.notes && (
                          <div className="text-[10px] text-slate-400">{rel.notes}</div>
                        )}
                      </div>
                      <Star className="w-4 h-4 text-yellow-400" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Objective Similarity Engine */}
            {selectedDossier.similar_works.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Obras Similares (Motor de Similaridade Multicritério)
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {selectedDossier.similar_works.map((sim) => (
                    <div
                      key={sim.id}
                      onClick={() => handleOpenDossier(sim.id)}
                      className="p-3 rounded-xl bg-surface-elevated border border-white/5 hover:border-brand-red/50 cursor-pointer flex flex-col justify-between gap-2"
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white line-clamp-1">
                            {sim.title}
                          </span>
                          <span className="text-[10px] font-black px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                            {sim.similarity_score}% afim
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          {sim.release_year} • {WORK_TYPE_LABELS[sim.work_type] || sim.work_type}
                        </div>
                      </div>
                      <div className="space-y-0.5">
                        {sim.similarity_reasons.map((r, i) => (
                          <div key={i} className="text-[10px] text-slate-300 truncate">
                            • {r}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Identity Resolution & Data Provenance Audit Panel */}
            <div className="p-4 rounded-xl bg-canvas border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-brand-red" />
                  Resolução de Identidade & Rastreabilidade de Procedência
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedDossier.external_identifiers.map((ext, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-surface-elevated text-[10px] font-mono text-slate-300 border border-white/10"
                    >
                      {ext.provider}: {ext.external_id} ({ext.confidence})
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {selectedDossier.provenance.slice(0, 6).map((p, i) => (
                  <div
                    key={i}
                    className="p-2 rounded-lg bg-surface-elevated/60 border border-white/5 text-[10px]"
                  >
                    <div className="font-bold text-slate-300 uppercase">
                      {p.field_name} • <span className="text-brand-red">{p.source_provider}</span>
                    </div>
                    <div className="text-slate-400 truncate">{p.field_value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
