import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Database,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Magnet,
} from "lucide-react";
import {
  ExternalSourceSummary,
  SourceCatalogItem,
  UnifiedShow,
} from "../types";
import { api, isAbortError, RequestAbortChannel } from "../services/api";
import { useToast } from "../context/ToastContext";
import { ShowCard } from "./ShowCard";

interface SourcesViewProps {
  onOpenDetails: (show: UnifiedShow) => void;
  onOpenTorrents: (show: UnifiedShow) => void;
  onSaveToLibrary?: (show: UnifiedShow) => void;
  onFilterProviderInExplore?: (provider: string) => void;
  savedShowIds?: Set<number>;
}

export const SourcesView: React.FC<SourcesViewProps> = ({
  onOpenDetails,
  onOpenTorrents,
  onSaveToLibrary,
  onFilterProviderInExplore,
  savedShowIds = new Set(),
}) => {
  const { showToast } = useToast();
  const abortChannelRef = useRef<RequestAbortChannel>(new RequestAbortChannel());

  const [sources, setSources] = useState<ExternalSourceSummary[]>([]);
  const [totals, setTotals] = useState<{
    total_sources: number;
    active_sources: number;
    total_titles: number;
    total_releases: number;
  } | null>(null);
  const [items, setItems] = useState<SourceCatalogItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isRefetching, setIsRefetching] = useState(false);
  const [syncingSource, setSyncingSource] = useState<string | null>(null);

  const [selectedSource, setSelectedSource] = useState<string>("all");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sortBy, setSortBy] = useState("seeds");
  const [minSeeds, setMinSeeds] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    const ch = abortChannelRef.current;
    return () => ch.abort();
  }, []);

  const loadSummary = useCallback(() => {
    api.sources
      .getSummary()
      .then((res) => {
        setSources(res.sources);
        setTotals(res.totals);
      })
      .catch((err) => console.error("Erro ao carregar resumo das fontes:", err));
  }, []);

  const loadCatalog = useCallback(() => {
    const signal = abortChannelRef.current.nextSignal();
    setIsRefetching(true);
    api.sources
      .getCatalog(
        {
          source: selectedSource,
          search: debouncedSearch || undefined,
          min_seeds: minSeeds,
          sort_by: sortBy,
          page,
          page_size: 24,
        },
        { signal }
      )
      .then((res) => {
        setItems(res.items);
        setTotalItems(res.total);
        setTotalPages(res.total_pages || 1);
        if (res.available_sources?.length) {
          setSources(res.available_sources);
        }
      })
      .catch((err) => {
        if (isAbortError(err)) return;
        console.error("Erro ao consultar Fontes de Dados:", err);
        showToast("Erro ao carregar catálogo multi-fonte", "error");
      })
      .finally(() => {
        if (!signal.aborted) {
          setLoading(false);
          setIsRefetching(false);
        }
      });
  }, [selectedSource, debouncedSearch, minSeeds, sortBy, page, showToast]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const handleSyncSource = async (sourceKey: string) => {
    setSyncingSource(sourceKey);
    const label = sourceKey === "all" ? "todas as fontes" : sourceKey.toUpperCase();
    showToast(`Sincronizando ${label} em sources.db...`, "info");
    try {
      await api.sources.sync(sourceKey, 5, true);
      showToast(`Sincronização de ${label} concluída!`, "success");
      loadSummary();
      loadCatalog();
    } catch {
      showToast(`Erro ao sincronizar ${label}`, "error");
    } finally {
      setSyncingSource(null);
    }
  };

  const toUnified = useMemo(
    () =>
      (item: SourceCatalogItem): UnifiedShow => {
        const numId =
          item.eztv_show_id ||
          parseInt(String(item.imdb_id || "").replace(/\D/g, ""), 10) ||
          1;
        return {
          id: numId,
          imdb_id: item.imdb_id || undefined,
          tvmaze_id: item.tvmaze_id || undefined,
          title: item.title,
          original_title: item.original_title || undefined,
          overview: item.overview || "",
          poster_url: item.poster_url || undefined,
          backdrop_url: item.backdrop_url || undefined,
          rating: Number(item.rating || 0),
          genres: item.genres
            ? item.genres
                .split(",")
                .map((g) => g.trim())
                .filter(Boolean)
            : [],
          first_air_date: item.first_air_date || undefined,
          status: item.status || undefined,
          network: item.network || undefined,
          streaming_providers:
            item.streaming_providers && item.streaming_providers.length > 0
              ? item.streaming_providers
              : item.network
                ? [item.network]
                : [],
          eztv_available: item.source_key === "eztv",
          has_media: true,
          media_sources: [item.source_key],
          sources_count: 1,
          source_provider: item.source_key,
          seasons: [],
        };
      },
    []
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 lg:pt-24 pb-16 space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <Database className="w-7 h-7 text-emerald-400" />
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Fontes de Dados
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              MULTI-INDEXADOR • sources.db
            </span>
          </div>
          <p className="text-sm text-slate-300">
            Catálogos externos isolados na Camada 2 (EZTV, YIFY / YTS, 1337x e provedores de links/magnets)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={syncingSource !== null}
            onClick={() => handleSyncSource(selectedSource === "all" ? "eztv" : selectedSource)}
            className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold shadow-lg transition-all cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${syncingSource ? "animate-spin" : ""}`} />
            {syncingSource
              ? "Sincronizando..."
              : selectedSource === "all"
                ? "Sincronizar EZTV"
                : `Sincronizar ${selectedSource.toUpperCase()}`}
          </button>
          <button
            type="button"
            disabled={syncingSource !== null}
            onClick={() => handleSyncSource("all")}
            className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/15 text-slate-200 text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
          >
            <Layers className="w-4 h-4 text-cyan-400" />
            Sincronizar Todas
          </button>
        </div>
      </div>

      {/* Source Provider Cards / Quick Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <button
          type="button"
          onClick={() => {
            setSelectedSource("all");
            setPage(1);
          }}
          className={`text-left p-4 rounded-2xl border transition-all cursor-pointer ${
            selectedSource === "all"
              ? "bg-emerald-950/50 border-emerald-400/70 ring-1 ring-emerald-400/40"
              : "bg-surface-elevated border-white/10 hover:border-white/25"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-black uppercase tracking-wider text-emerald-300">
              Todas as Fontes
            </span>
            <Magnet className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-black text-white mt-2">
            {(totals?.total_titles ?? totalItems).toLocaleString("pt-BR")}
          </p>
          <p className="text-xs text-slate-300 mt-0.5">
            {totals?.active_sources ?? sources.length} indexadores •{" "}
            {(totals?.total_releases ?? 0).toLocaleString("pt-BR")} releases
          </p>
        </button>

        {sources.map((src) => {
          const isSelected = selectedSource === src.source_key;
          const isOk = src.status !== "degraded";
          return (
            <button
              type="button"
              key={src.source_key}
              onClick={() => {
                setSelectedSource(src.source_key);
                setPage(1);
              }}
              className={`text-left p-4 rounded-2xl border transition-all cursor-pointer ${
                isSelected
                  ? "bg-emerald-950/50 border-emerald-400/70 ring-1 ring-emerald-400/40"
                  : "bg-surface-elevated border-white/10 hover:border-white/25"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-black uppercase tracking-wider text-white">
                  {src.display_name}
                </span>
                {isOk ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                )}
              </div>
              <p className="text-2xl font-black text-white mt-2">
                {src.total_titles.toLocaleString("pt-BR")}
              </p>
              <p className="text-xs text-slate-300 mt-0.5">
                {src.total_releases.toLocaleString("pt-BR")} releases • {src.media_types.join(", ")}
              </p>
            </button>
          );
        })}
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3 p-4 rounded-2xl bg-surface-elevated border border-white/10">
        <div className="relative flex-1">
          <label htmlFor="sources-search-input" className="sr-only">
            Buscar nas Fontes de Dados
          </label>
          <Search className="w-4 h-4 text-slate-300 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            id="sources-search-input"
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Filtrar por título ou IMDb ID..."
            className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl pl-9 pr-3 text-sm text-white placeholder-slate-400"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Ordenar Fontes de Dados"
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value);
              setPage(1);
            }}
            className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
          >
            <option value="seeds">Mais Seeds Ativos</option>
            <option value="torrents">Mais Releases</option>
            <option value="rating">Maior Nota</option>
            <option value="name">Ordem Alfabética</option>
          </select>

          <select
            aria-label="Mínimo de seeds"
            value={minSeeds}
            onChange={(e) => {
              setMinSeeds(Number(e.target.value));
              setPage(1);
            }}
            className="min-h-[44px] bg-canvas border border-white/15 rounded-xl px-3 text-xs font-semibold text-white"
          >
            <option value={0}>Qualquer seed</option>
            <option value={5}>Min. 5 seeds</option>
            <option value={25}>Min. 25 seeds</option>
            <option value={100}>Min. 100 seeds</option>
          </select>
        </div>
      </div>

      {/* Non-destructive linear progress bar */}
      {isRefetching && (
        <div className="w-full h-1 bg-surface-elevated overflow-hidden rounded-full" aria-hidden="true">
          <div className="h-full w-1/3 bg-emerald-400 animate-pulse rounded-full" />
        </div>
      )}

      {/* Results Grid */}
      <div aria-busy={isRefetching}>
        {loading && items.length === 0 ? (
          <div className="py-16 text-center text-slate-300 animate-pulse">
            Carregando catálogos em Fontes de Dados...
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center rounded-2xl border border-dashed border-white/15 bg-surface/50 space-y-2">
            <Database className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-base font-bold text-white">
              Nenhum release encontrado nesta fonte
            </p>
            <p className="text-xs text-slate-300">
              Experimente sincronizar a fonte selecionada ou alternar para &quot;Todas as Fontes&quot;.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-5">
            {items.map((item) => {
              const unified = toUnified(item);
              const isSaved = savedShowIds.has(unified.id);
              return (
                <ShowCard
                  key={`${item.source_key}-${item.id}`}
                  show={unified}
                  fluidWidth
                  workTypeLabel={item.source_name || item.source_key.toUpperCase()}
                  extraStatusLabel={`▲ ${item.max_seeds} • ${item.total_torrents} rel`}
                  onOpenDetails={onOpenDetails}
                  onOpenTorrents={onOpenTorrents}
                  onSaveToLibrary={onSaveToLibrary}
                  onFilterProvider={onFilterProviderInExplore}
                  isSaved={isSaved}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-4">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="min-h-[44px] px-4 rounded-xl bg-surface-elevated border border-white/15 text-xs font-bold text-white disabled:opacity-40 cursor-pointer"
          >
            Anterior
          </button>
          <span className="text-xs font-bold text-slate-300">
            Página {page} de {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="min-h-[44px] px-4 rounded-xl bg-surface-elevated border border-white/15 text-xs font-bold text-white disabled:opacity-40 cursor-pointer"
          >
            Próxima
          </button>
        </div>
      )}
    </div>
  );
};
