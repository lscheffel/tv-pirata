import React, { useState, useEffect, useCallback } from "react";
import {
  Flame,
  Star,
  Users,
  Download,
  RefreshCw,
  Search,
  Filter,
  Film,
  Zap,
  Bookmark,
  Check,
  Layers,
  Sparkles,
} from "lucide-react";
import { CatalogGenreCount, CatalogShow, CatalogStats, UnifiedShow } from "../types";
import { api } from "../services/api";
import { useToast } from "../context/ToastContext";
import { EztvBadge } from "./EztvBadge";
import { ProviderBadge, StatusBadge } from "./ShowBadges";

interface CatalogViewProps {
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  savedShowIds?: Set<number>;
}

export const CatalogView: React.FC<CatalogViewProps> = ({
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  savedShowIds = new Set(),
}) => {
  const { showToast } = useToast();
  const [shows, setShows] = useState<CatalogShow[]>([]);
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [genres, setGenres] = useState<CatalogGenreCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isEnriching, setIsEnriching] = useState(false);

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("seeds");
  const [minSeeds, setMinSeeds] = useState(0);
  const [selectedGenre, setSelectedGenre] = useState("ALL");
  const [syncBatchPages, setSyncBatchPages] = useState(15);
  const [totalShows, setTotalShows] = useState(0);

  const loadStats = useCallback(() => {
    api.catalog
      .getStats()
      .then((data) => setStats(data))
      .catch((err) => console.error("Erro ao carregar stats do catálogo:", err));
  }, []);

  const loadGenres = useCallback(() => {
    api.catalog
      .getGenres()
      .then((data) => setGenres(data))
      .catch((err) => console.error("Erro ao carregar gêneros do catálogo:", err));
  }, []);

  const loadShows = useCallback(() => {
    setLoading(true);
    api.catalog
      .getShows({
        search: searchTerm.trim() || undefined,
        genre: selectedGenre !== "ALL" ? selectedGenre : undefined,
        sort_by: sortBy,
        min_seeds: minSeeds,
        page_size: 60,
      })
      .then((data) => {
        setShows(data.items);
        setTotalShows(data.total);
      })
      .catch((err) => {
        console.error("Erro ao carregar catálogo:", err);
        showToast("Erro ao carregar séries do catálogo", "error");
      })
      .finally(() => setLoading(false));
  }, [searchTerm, selectedGenre, sortBy, minSeeds, showToast]);

  useEffect(() => {
    loadStats();
    loadGenres();
    loadShows();
  }, [loadStats, loadGenres, loadShows]);

  const handleSync = async () => {
    setIsSyncing(true);
    showToast(`Sincronizando ${syncBatchPages} páginas da EZTV (~${syncBatchPages * 100} releases)...`, "info");
    try {
      const res = await api.catalog.sync(syncBatchPages);
      showToast(
        `Catálogo atualizado! +${res.telemetry.torrents_indexed} releases, ${res.telemetry.shows_created} novas séries.`,
        "success"
      );
      loadStats();
      loadGenres();
      loadShows();
    } catch {
      showToast("Falha ao sincronizar catálogo EZTV", "error");
    } finally {
      setIsSyncing(false);
    }
  };

  const handleEnrichPending = async () => {
    setIsEnriching(true);
    showToast("Buscando capas e metadados para séries pendentes...", "info");
    try {
      const res = await api.catalog.enrichPending(150);
      showToast(`Enriquecimento concluído! ${res.shows_enriched} séries atualizadas com capas e sinopses.`, "success");
      loadStats();
      loadGenres();
      loadShows();
    } catch {
      showToast("Falha no enriquecimento de metadados", "error");
    } finally {
      setIsEnriching(false);
    }
  };

  const convertCatalogToUnified = (cat: CatalogShow): UnifiedShow => {
    // Generate deterministic numeric id from imdb numbers for UI keys
    const numericPart = parseInt(cat.imdb_id.replace(/\D/g, ""), 10) || 1;
    return {
      id: numericPart,
      imdb_id: cat.imdb_id,
      title: cat.title,
      overview: cat.overview,
      poster_url: cat.poster_url || undefined,
      backdrop_url: cat.backdrop_url || undefined,
      rating: cat.rating,
      genres: cat.genres ? cat.genres.split(",").map((g) => g.trim()) : [],
      first_air_date: cat.first_air_date || undefined,
      status: cat.status || undefined,
      network: cat.network || undefined,
      streaming_providers: cat.streaming_providers || (cat.network ? [cat.network] : []),
      eztv_available: true,
      source_provider: "eztv-catalog",
      seasons: [],
    };
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
      {/* Title & Stats Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold text-white flex items-center gap-2">
              <Zap className="w-8 h-8 text-yellow-400 fill-yellow-400/20" />
              Catálogo Físico EZTV
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-red/20 text-brand-red border border-brand-red/30">
              P2P Garantido
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Séries indexadas diretamente da rede de distribuição com links e sementes ativas garantidas
          </p>
        </div>

        {/* Sync Button & Stats */}
        <div className="flex flex-wrap items-center gap-3">
          {stats && (
            <div className="hidden sm:flex items-center gap-2 text-xs bg-surface border border-white/10 rounded-xl px-3 py-2 text-slate-300">
              <span className="font-bold text-white">{stats.total_shows}</span> séries |
              <span className="font-bold text-cyan-400">
                {stats.total_episodes ?? stats.total_releases}
              </span>{" "}
              episódios |
              <span className="text-yellow-400 font-bold">{stats.max_seeds_in_catalog}</span> max seeds
            </div>
          )}

          <div className="flex items-center gap-1.5 bg-surface border border-white/10 rounded-xl p-1 text-xs">
            <select
              value={syncBatchPages}
              onChange={(e) => setSyncBatchPages(Number(e.target.value))}
              disabled={isSyncing}
              className="bg-transparent text-slate-300 font-bold px-2 py-1 focus:outline-none cursor-pointer"
            >
              <option value={5} className="bg-surface text-white">5 pgs (~500)</option>
              <option value={15} className="bg-surface text-white">15 pgs (~1.500)</option>
              <option value={30} className="bg-surface text-white">30 pgs (~3.000)</option>
              <option value={50} className="bg-surface text-white">50 pgs (~5.000)</option>
            </select>
            <button
              onClick={handleSync}
              disabled={isSyncing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand-red hover:bg-brand-redHover disabled:bg-slate-800 text-white font-bold transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? "animate-spin" : ""}`} />
              {isSyncing ? "Sincronizando..." : "Sincronizar"}
            </button>
          </div>

          <button
            onClick={handleEnrichPending}
            disabled={isEnriching}
            title="Buscar capas e sinopses para séries pendentes"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface border border-white/15 hover:border-white/30 text-slate-200 text-xs font-semibold transition-all"
          >
            <Sparkles className={`w-3.5 h-3.5 text-yellow-400 ${isEnriching ? "animate-spin" : ""}`} />
            {isEnriching ? "Enriquecendo..." : "Enriquecer Capas"}
          </button>
        </div>
      </div>

      {/* Control Bar: Search & Filters */}
      <div className="bg-surface rounded-2xl border border-white/5 p-4 mb-8 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Search Input */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Filtrar por título ou IMDB ID (ex: tt0944947)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-surface-elevated border border-white/10 rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:border-brand-red"
            />
          </div>

          {/* Sort By Dropdown */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400 shrink-0" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full bg-surface-elevated border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-red cursor-pointer"
            >
              <option value="seeds">Mais Semeados (Seeds)</option>
              <option value="date">Lançamentos Recentes</option>
              <option value="torrents">Mais Torrents Indexados</option>
              <option value="rating">Melhor Avaliados</option>
            </select>
          </div>

          {/* Min Seeds Filter Buttons */}
          <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
            {[0, 50, 200, 500].map((seedsVal) => (
              <button
                key={seedsVal}
                onClick={() => setMinSeeds(seedsVal)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${
                  minSeeds === seedsVal
                    ? "bg-brand-red text-white"
                    : "bg-surface-elevated text-slate-400 hover:text-white hover:bg-white/10"
                }`}
              >
                {seedsVal === 0 ? "Todas Seeds" : `+${seedsVal} seeds`}
              </button>
            ))}
          </div>
        </div>

        {/* Dynamic Genre Pills Bar */}
        {genres.length > 0 && (
          <div className="pt-3 border-t border-white/5 flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
            <button
              onClick={() => setSelectedGenre("ALL")}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                selectedGenre === "ALL"
                  ? "bg-white text-black shadow-md font-extrabold"
                  : "bg-white/5 text-slate-400 hover:text-white hover:bg-white/10"
              }`}
            >
              <Layers className="w-3 h-3" />
              Todos ({totalShows || stats?.total_shows || 0})
            </button>
            {genres.map((g) => (
              <button
                key={g.genre}
                onClick={() => setSelectedGenre(g.genre)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                  selectedGenre === g.genre
                    ? "bg-brand-red text-white shadow-cinema-glow font-bold"
                    : "bg-surface-elevated/80 border border-white/5 text-slate-400 hover:text-white hover:bg-white/10"
                }`}
              >
                {g.genre} <span className="text-[10px] opacity-70">({g.count})</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Shows Header Info */}
      <div className="flex items-center justify-between mb-4 px-1 text-xs text-slate-400">
        <span>
          Mostrando <strong className="text-white">{shows.length}</strong> de{" "}
          <strong className="text-white">{totalShows}</strong> títulos no acervo
          {selectedGenre !== "ALL" && (
            <span className="text-brand-red font-bold"> em {selectedGenre}</span>
          )}
        </span>
      </div>

      {/* Shows Grid */}
      {loading ? (
        <div className="py-20 text-center text-slate-500 animate-pulse space-y-2">
          <Flame className="w-8 h-8 mx-auto text-brand-red animate-bounce" />
          <p className="text-sm">Carregando catálogo P2P da EZTV...</p>
        </div>
      ) : shows.length === 0 ? (
        <div className="py-24 text-center rounded-2xl border border-dashed border-white/10 bg-surface/40 p-8 space-y-3">
          <Film className="w-12 h-12 mx-auto text-slate-600" />
          <h3 className="text-lg font-bold text-slate-300">Nenhum título encontrado no catálogo</h3>
          <p className="text-sm text-slate-500 max-w-sm mx-auto">
            Clique no botão &quot;Sincronizar EZTV&quot; acima para ingerir e enriquecer as releases mais recentes!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-6">
          {shows.map((show) => {
            const unified = convertCatalogToUnified(show);

            return (
              <div
                key={`${show.eztv_show_id ?? show.imdb_id}`}
                onClick={() => onOpenDetails(unified)}
                className="group relative flex flex-col rounded-xl overflow-hidden bg-surface border border-white/5 hover:border-white/15 cursor-pointer transition-all duration-300 hover:scale-[1.03] hover:z-20 shadow-xl"
              >
                {/* Poster Container */}
                <div className="relative aspect-[2/3] w-full bg-surface-elevated overflow-hidden">
                  {show.poster_url ? (
                    <img
                      src={show.poster_url}
                      alt={show.title}
                      loading="lazy"
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center p-3 text-center bg-gradient-to-br from-surface-elevated to-surface">
                      <Film className="w-8 h-8 text-slate-600 mb-1" />
                      <span className="text-xs text-slate-400 font-bold line-clamp-2">{show.title}</span>
                    </div>
                  )}

                  {/* Top-left: EZTV Badge + Seeds Pill */}
                  <div className="absolute top-2 left-2 flex items-center gap-1.5 z-10">
                    <EztvBadge compact />
                    {show.max_seeds > 0 && (
                      <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-emerald-400 text-[10px] font-extrabold border border-emerald-500/30">
                        <Users className="w-2.5 h-2.5 text-emerald-400" />
                        {show.max_seeds}
                      </div>
                    )}
                  </div>

                  {/* Rating Badge */}
                  {show.rating > 0 && (
                    <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-md bg-black/80 backdrop-blur-md text-yellow-400 text-xs font-bold border border-yellow-500/20">
                      <Star className="w-3 h-3 fill-yellow-400" />
                      {show.rating.toFixed(1)}
                    </div>
                  )}

                  <div className="absolute inset-0 bg-gradient-to-t from-canvas via-transparent to-transparent opacity-80 group-hover:opacity-90 transition-opacity" />

                  {/* Bottom overlay with permanent badges and torrent action */}
                  <div className="absolute inset-x-0 bottom-0 p-3">
                    {(show.status || show.network || (show.streaming_providers && show.streaming_providers.length > 0)) && (
                      <div className="flex flex-wrap items-center gap-1 mb-1.5">
                        <StatusBadge status={show.status} compact />
                        <ProviderBadge
                          provider={show.streaming_providers?.[0] || show.network}
                          compact
                        />
                      </div>
                    )}
                    <h3 className="text-sm font-bold text-white line-clamp-1 group-hover:text-cyan-300 transition-colors">
                      {show.title}
                    </h3>
                    <div className="flex items-center justify-between mt-1 text-[11px] text-slate-400">
                      <span className="font-semibold text-slate-300">
                        {show.episodes_count && show.episodes_count > 0
                          ? `${show.episodes_count} eps`
                          : `${show.total_torrents} ${show.total_torrents === 1 ? "release" : "releases"}`}
                      </span>
                      {show.latest_season > 0 && (
                        <span className="font-mono text-cyan-300">
                          S{show.latest_season.toString().padStart(2, "0")}E
                          {show.latest_episode.toString().padStart(2, "0")}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Card Action footer */}
                <div className="p-2 bg-surface-elevated/40 border-t border-white/5 flex items-center justify-between gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenTorrents(unified);
                    }}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-brand-red/20 text-brand-red hover:bg-brand-red hover:text-white transition-all text-xs font-bold"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Magnets ({show.total_torrents})
                  </button>

                  {onSaveToLibrary && (
                    <button
                      title={savedShowIds.has(unified.id) ? "Salva na Biblioteca" : "Adicionar à Minha Lista"}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSaveToLibrary(unified);
                      }}
                      className={`p-1.5 rounded-lg border transition-colors ${
                        savedShowIds.has(unified.id)
                          ? "bg-emerald-900/80 border-emerald-500 text-emerald-300"
                          : "bg-surface-elevated border-white/20 text-slate-300 hover:text-white"
                      }`}
                    >
                      {savedShowIds.has(unified.id) ? (
                        <Check className="w-3.5 h-3.5" />
                      ) : (
                        <Bookmark className="w-3.5 h-3.5" />
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
