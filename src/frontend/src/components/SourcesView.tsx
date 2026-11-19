import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookMarked,
  CheckCircle2,
  Database,
  ExternalLink,
  Gem,
  Layers,
  Magnet,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Zap,
} from "lucide-react";
import {
  ExternalSourceSummary,
  SourceCatalogItem,
  SyncRecipeMode,
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

interface CardWaveState {
  state: "idle" | "syncing" | "done" | "skipped" | "error";
  label?: string;
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

  // Sync Command Deck & Per-Card Orbital Wave states
  const [syncMode, setSyncMode] = useState<SyncRecipeMode>("incremental");
  const [fineTuneOpen, setFineTuneOpen] = useState(false);
  const [recipeQuality, setRecipeQuality] = useState("All");
  const [recipeMinRating, setRecipeMinRating] = useState(0);
  const [recipeSortBy, setRecipeSortBy] = useState("date_added");
  const [recipePages, setRecipePages] = useState(2);

  const [waveRunning, setWaveRunning] = useState(false);
  const [cardWave, setCardWave] = useState<Record<string, CardWaveState>>({});
  const [pruning, setPruning] = useState(false);
  const [liveIngesting, setLiveIngesting] = useState(false);

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

  const applyRecipePreset = (preset: "incremental" | "baseline" | "4k" | "library") => {
    if (preset === "incremental") {
      setSyncMode("incremental");
      setRecipeQuality("All");
      setRecipeMinRating(0);
      setRecipeSortBy("date_added");
      setRecipePages(2);
    } else if (preset === "baseline") {
      setSyncMode("baseline");
      setRecipeQuality("All");
      setRecipeMinRating(0);
      setRecipeSortBy("seeds");
      setRecipePages(4);
    } else if (preset === "4k") {
      setSyncMode("baseline");
      setRecipeQuality("2160p");
      setRecipeMinRating(7);
      setRecipeSortBy("seeds");
      setRecipePages(3);
    } else {
      setSyncMode("library");
    }
  };

  // Card-by-Card Sequential Orbital Wave (2A + 8C graceful offline fast-skip)
  const runSyncWave = async (
    targetKeys: string[],
    overrideOpts?: {
      mode?: SyncRecipeMode;
      quality?: string;
      minimum_rating?: number;
      sort_by?: string;
      pages?: number;
    }
  ) => {
    const effMode = overrideOpts?.mode ?? syncMode;
    const effQual = overrideOpts?.quality ?? recipeQuality;
    const effMinRat = overrideOpts?.minimum_rating ?? recipeMinRating;
    const effSort = overrideOpts?.sort_by ?? recipeSortBy;
    const effPages = overrideOpts?.pages ?? recipePages;

    if (effMode === "library") {
      setWaveRunning(true);
      try {
        const res = await api.sources.sync(
          selectedSource === "all" ? "all" : selectedSource,
          1,
          false,
          { mode: "library" }
        );
        const resAny = res as any;
        showToast(
          `Biblioteca sincronizada: ${resAny.titles_scanned ?? 0} títulos varridos (${resAny.releases_found ?? 0} releases).`,
          "success"
        );
        loadSummary();
        loadCatalog();
      } catch {
        showToast("Erro ao sincronizar títulos da Minha Biblioteca", "error");
      } finally {
        setWaveRunning(false);
      }
      return;
    }

    setWaveRunning(true);
    let totalAdded = 0;
    let totalPruned = 0;

    for (const sk of targetKeys) {
      setCardWave((prev) => ({
        ...prev,
        [sk]: { state: "syncing", label: "Colhendo..." },
      }));

      try {
        const res = await api.sources.sync(sk, effPages, true, {
          mode: effMode,
          quality: effQual,
          minimum_rating: effMinRat,
          sort_by: effSort,
          prune_after: true,
        });
        const srcRes = res.results?.[sk] || {};
        const tel = srcRes.telemetry || {};
        const added = Number(
          tel.releases_indexed ?? tel.torrents_found ?? tel.shows_touched ?? 0
        );
        const pruned = Number(res.prune?.removed_releases ?? 0);
        totalAdded += added;
        totalPruned += pruned;

        if (srcRes.status === "skipped_offline") {
          setCardWave((prev) => ({
            ...prev,
            [sk]: { state: "skipped", label: "Sidecar :8009 Offline (Pulado)" },
          }));
        } else if (srcRes.status === "error") {
          setCardWave((prev) => ({
            ...prev,
            [sk]: { state: "error", label: "Indisponível" },
          }));
        } else {
          const deltaLabel =
            pruned > 0 ? `+${added} novos • ${pruned} podados` : `+${added} sincronizados`;
          setCardWave((prev) => ({
            ...prev,
            [sk]: { state: "done", label: deltaLabel },
          }));
        }
        loadSummary();
        loadCatalog();
      } catch {
        setCardWave((prev) => ({
          ...prev,
          [sk]: { state: "error", label: "Falha na onda" },
        }));
      }
    }

    showToast(
      `Onda concluída: +${totalAdded} itens processados${totalPruned > 0 ? ` • ${totalPruned} mortos podados` : ""}.`,
      "success"
    );
    setWaveRunning(false);
  };

  const handlePruneObsolete = async () => {
    setPruning(true);
    try {
      const res = await api.sources.prune(selectedSource, 1);
      showToast(
        `Limpeza concluída: ${res.removed_releases} releases obsoletos (0 seeds) podados.`,
        "success"
      );
      loadSummary();
      loadCatalog();
    } catch {
      showToast("Erro ao podar releases obsoletos", "error");
    } finally {
      setPruning(false);
    }
  };

  const handleLiveIngest = async () => {
    const q = searchInput.trim();
    if (q.length < 2) return;
    setLiveIngesting(true);
    try {
      const res = await api.sources.liveIngest(q, selectedSource, 20);
      if (res.ingested_count > 0) {
        showToast(
          `Ingeridos ${res.ingested_count} releases confiáveis para "${q}"!`,
          "success"
        );
      } else {
        showToast(`Busca ao vivo para "${q}" concluída (sem novos matches >= 85%).`, "info");
      }
      loadSummary();
      loadCatalog();
    } catch {
      showToast("Erro ao buscar nas APIs remotas", "error");
    } finally {
      setLiveIngesting(false);
    }
  };

  const activeSourceKeys = useMemo(
    () => sources.filter((s) => s.enabled).map((s) => s.source_key),
    [sources]
  );

  const toUnified = useMemo(
    () =>
      (item: SourceCatalogItem): UnifiedShow => {
        const numId =
          item.eztv_show_id ||
          parseInt(String(item.imdb_id || "").replace(/\D/g, ""), 10) ||
          1;
        const mSources =
          item.media_sources && item.media_sources.length > 0
            ? item.media_sources
            : [item.source_key];
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
          eztv_available: mSources.includes("eztv"),
          has_media: true,
          media_sources: mSources,
          sources_count: mSources.length,
          source_provider: item.source_key,
          seasons: [],
        };
      },
    []
  );

  const protocolPillForSource = (src: ExternalSourceSummary) => {
    if (src.source_key === "yify") return "movies-api.accel.li v2";
    if (src.source_key === "eztv") return "eztvx.to + RSS";
    if (src.source_key === "nyaasi") return "Nyaa RSS + Sidecar";
    if (src.source_key === "bitsearch") return "BitSearch DHT + Sidecar";
    if (src.source_key === "tgx") return "TheRarbg JSON + Sidecar";
    if (src.source_key === "glodls") return "APIBay JSON + Sidecar";
    if (src.adapter_key === "torrent_api_py") return "Híbrido (Direto + Sidecar)";
    return src.adapter_key || src.kind;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 lg:pt-24 pb-16 space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-white/10 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <Database className="w-7 h-7 text-emerald-400" />
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Fontes de Dados
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              ETAPA 1 PRESENÇA • ETAPA 2 JIT • sources.db
            </span>
          </div>
          <p className="text-sm text-slate-300">
            Catálogo canônico soberano (<code className="text-emerald-300">mainstream.db</code>) +
            índice semi-efêmero pluggable (<code className="text-cyan-300">EZTV</code>,{" "}
            <code className="text-cyan-300">YTS accel.li v2</code>,{" "}
            <code className="text-cyan-300">TGx</code>, <code className="text-cyan-300">Nyaa</code>,{" "}
            <code className="text-cyan-300">BitSearch</code>,{" "}
            <code className="text-cyan-300">GloDLS</code>)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={pruning || waveRunning}
            onClick={handlePruneObsolete}
            className="min-h-[44px] flex items-center gap-2 px-3.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-400/40 text-amber-200 text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
            title="Remover releases mortos (0 seeds) e recalcular presença"
          >
            <Trash2 className="w-4 h-4" />
            <span>{pruning ? "Podando..." : "Podar Obsoletos"}</span>
          </button>

          <button
            type="button"
            disabled={waveRunning}
            onClick={() =>
              runSyncWave(
                selectedSource === "all" ? activeSourceKeys : [selectedSource]
              )
            }
            className="min-h-[44px] flex items-center gap-2 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-extrabold shadow-lg transition-all cursor-pointer"
          >
            <Layers className={`w-4 h-4 ${waveRunning ? "animate-pulse" : ""}`} />
            {waveRunning
              ? "Onda em Execução..."
              : selectedSource === "all"
                ? `Disparar Onda (${activeSourceKeys.length} Ativas)`
                : `Sincronizar ${selectedSource.toUpperCase()}`}
          </button>
        </div>
      </div>

      {/* Sync Command Deck (1B + 3C + 8B — Intent Recipes & Protocol Fine-Tuning) */}
      <section
        aria-label="Sync Command Deck"
        className="rounded-2xl bg-surface-elevated border border-white/10 p-4 space-y-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-black uppercase tracking-wider text-slate-400 mr-1">
              Receitas Etapa 1:
            </span>

            <button
              type="button"
              onClick={() => {
                applyRecipePreset("incremental");
                runSyncWave(
                  selectedSource === "all" ? activeSourceKeys : [selectedSource],
                  { mode: "incremental", quality: "All", minimum_rating: 0, sort_by: "date_added", pages: 2 }
                );
              }}
              disabled={waveRunning}
              className={`min-h-[40px] px-3 rounded-xl text-xs font-bold flex items-center gap-1.5 border transition-all cursor-pointer ${
                syncMode === "incremental" && recipeQuality === "All"
                  ? "bg-emerald-500/20 border-emerald-400 text-emerald-200"
                  : "bg-canvas border-white/15 text-slate-200 hover:border-white/30"
              }`}
            >
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
              Incremental Delta (Novidades + Poda)
            </button>

            <button
              type="button"
              onClick={() => {
                applyRecipePreset("baseline");
                runSyncWave(
                  selectedSource === "all" ? activeSourceKeys : [selectedSource],
                  { mode: "baseline", quality: "All", minimum_rating: 0, sort_by: "seeds", pages: 4 }
                );
              }}
              disabled={waveRunning}
              className={`min-h-[40px] px-3 rounded-xl text-xs font-bold flex items-center gap-1.5 border transition-all cursor-pointer ${
                syncMode === "baseline" && recipeQuality === "All"
                  ? "bg-cyan-500/20 border-cyan-400 text-cyan-200"
                  : "bg-canvas border-white/15 text-slate-200 hover:border-white/30"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              Baseline Top Seeds
            </button>

            <button
              type="button"
              onClick={() => {
                applyRecipePreset("4k");
                runSyncWave(["yify"], {
                  mode: "baseline",
                  quality: "2160p",
                  minimum_rating: 7,
                  sort_by: "seeds",
                  pages: 3,
                });
              }}
              disabled={waveRunning}
              className={`min-h-[40px] px-3 rounded-xl text-xs font-bold flex items-center gap-1.5 border transition-all cursor-pointer ${
                recipeQuality === "2160p"
                  ? "bg-purple-500/20 border-purple-400 text-purple-200"
                  : "bg-canvas border-white/15 text-slate-200 hover:border-white/30"
              }`}
            >
              <Gem className="w-3.5 h-3.5 text-purple-400" />
              4K / Nota 7+ (YTS v2)
            </button>

            <button
              type="button"
              onClick={() => {
                applyRecipePreset("library");
                runSyncWave(activeSourceKeys, { mode: "library" });
              }}
              disabled={waveRunning}
              className={`min-h-[40px] px-3 rounded-xl text-xs font-bold flex items-center gap-1.5 border transition-all cursor-pointer ${
                syncMode === "library"
                  ? "bg-brand-red/20 border-brand-red text-white"
                  : "bg-canvas border-white/15 text-slate-200 hover:border-white/30"
              }`}
            >
              <BookMarked className="w-3.5 h-3.5 text-brand-red" />
              Minha Biblioteca
            </button>
          </div>

          <button
            type="button"
            aria-expanded={fineTuneOpen}
            onClick={() => setFineTuneOpen((o) => !o)}
            className="min-h-[40px] px-3 rounded-xl bg-canvas border border-white/15 hover:border-white/30 text-xs font-bold text-slate-200 flex items-center gap-1.5 cursor-pointer"
          >
            <SlidersHorizontal className="w-3.5 h-3.5 text-sky-400" />
            Ajuste Fino ({recipeQuality} • {recipePages}p)
          </button>
        </div>

        {fineTuneOpen && (
          <div className="pt-3 border-t border-white/10 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] font-bold text-slate-300 mb-1">
                Qualidade YTS (v2)
              </label>
              <select
                value={recipeQuality}
                onChange={(e) => setRecipeQuality(e.target.value)}
                className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
              >
                <option value="All">Todas as Qualidades</option>
                <option value="2160p">2160p (4K UHD)</option>
                <option value="1080p.x265">1080p x265 (HEVC)</option>
                <option value="1080p">1080p Full HD</option>
                <option value="720p">720p HD</option>
                <option value="3D">3D</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold text-slate-300 mb-1">
                Nota Mínima IMDb
              </label>
              <select
                value={recipeMinRating}
                onChange={(e) => setRecipeMinRating(Number(e.target.value))}
                className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
              >
                <option value={0}>Qualquer Nota (0+)</option>
                <option value={6}>6.0+</option>
                <option value={7}>7.0+ (Curados)</option>
                <option value={8}>8.0+ (Aclamados)</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold text-slate-300 mb-1">
                Ordenação na Origem
              </label>
              <select
                value={recipeSortBy}
                onChange={(e) => setRecipeSortBy(e.target.value)}
                className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
              >
                <option value="date_added">Mais Recentes (Delta)</option>
                <option value="seeds">Mais Seeds (Baseline)</option>
                <option value="download_count">Mais Baixados</option>
                <option value="rating">Maior Nota IMDb</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-bold text-slate-300 mb-1">
                Páginas por Fonte
              </label>
              <select
                value={recipePages}
                onChange={(e) => setRecipePages(Number(e.target.value))}
                className="w-full min-h-[38px] bg-canvas border border-white/15 rounded-lg px-2.5 text-xs text-white"
              >
                <option value={1}>1 página (Ultrarrápido)</option>
                <option value={2}>2 páginas</option>
                <option value={4}>4 páginas</option>
                <option value={8}>8 páginas (Denso)</option>
              </select>
            </div>
          </div>
        )}
      </section>

      {/* Cockpit Source Provider Cards (9D + 2A Per-Card Wave Telemetry) */}
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
            {totals?.active_sources ?? sources.length} indexadores ativos •{" "}
            {(totals?.total_releases ?? 0).toLocaleString("pt-BR")} releases
          </p>
          <p className="text-[10px] text-emerald-300/80 mt-2 font-semibold">
            Deduplicado por IMDb ID + Batch Join Camada 1
          </p>
        </button>

        {sources.map((src) => {
          const isSelected = selectedSource === src.source_key;
          const isOk = src.status !== "degraded" && src.status !== "cooldown";
          const wave = cardWave[src.source_key];
          const rssUrl = src.config?.rss_url as string | undefined;
          const statusUrl = src.config?.status_url as string | undefined;

          return (
            <div
              key={src.source_key}
              onClick={() => {
                setSelectedSource(src.source_key);
                setPage(1);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedSource(src.source_key);
                  setPage(1);
                }
              }}
              className={`relative overflow-hidden text-left p-4 rounded-2xl border transition-all cursor-pointer ${
                isSelected
                  ? "bg-emerald-950/50 border-emerald-400/70 ring-1 ring-emerald-400/40"
                  : "bg-surface-elevated border-white/10 hover:border-white/25"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    {isOk ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    )}
                    <span className="text-xs font-black uppercase tracking-wider text-white truncate">
                      {src.display_name}
                    </span>
                  </div>
                  <span className="inline-block mt-1 px-1.5 py-0.5 rounded bg-white/5 text-[10px] font-mono text-slate-300">
                    {protocolPillForSource(src)}
                  </span>
                </div>

                {/* Individual 44x44 Quick Pulse button (stopPropagation) */}
                <button
                  type="button"
                  disabled={waveRunning}
                  onClick={(e) => {
                    e.stopPropagation();
                    runSyncWave([src.source_key]);
                  }}
                  title={`Pulso rápido em ${src.display_name}`}
                  aria-label={`Sincronizar ${src.display_name}`}
                  className="min-w-[44px] min-h-[44px] -mt-2 -mr-2 rounded-xl flex items-center justify-center text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-40 transition-colors cursor-pointer"
                >
                  <RefreshCw
                    className={`w-4 h-4 ${wave?.state === "syncing" ? "animate-spin" : ""}`}
                  />
                </button>
              </div>

              <div className="mt-2 flex items-baseline justify-between gap-2">
                <p className="text-2xl font-black text-white">
                  {src.total_titles.toLocaleString("pt-BR")}
                </p>
                {wave?.label && (
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      wave.state === "done"
                        ? "bg-emerald-500/20 text-emerald-200"
                        : wave.state === "skipped"
                          ? "bg-amber-500/20 text-amber-200"
                          : wave.state === "error"
                            ? "bg-red-500/20 text-red-200"
                            : "bg-cyan-500/20 text-cyan-200"
                    }`}
                  >
                    {wave.label}
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-300 mt-0.5 truncate">
                {src.total_releases.toLocaleString("pt-BR")} releases • {src.media_types.join(", ")}
              </p>

              {(rssUrl || statusUrl) && (
                <div
                  className="flex items-center gap-2 mt-2 pt-2 border-t border-white/10 text-[10px]"
                  onClick={(e) => e.stopPropagation()}
                >
                  {statusUrl && (
                    <a
                      href={statusUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-300 hover:underline flex items-center gap-1 font-semibold"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Status Oficial
                    </a>
                  )}
                  {rssUrl && (
                    <a
                      href={rssUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-300 hover:underline flex items-center gap-1 font-semibold"
                    >
                      <ExternalLink className="w-3 h-3" />
                      Feed RSS
                    </a>
                  )}
                </div>
              )}

              {/* Orbital Progress Bar on syncing card */}
              {wave?.state === "syncing" && (
                <div
                  className="absolute inset-x-0 bottom-0 h-1 bg-emerald-500/20 overflow-hidden"
                  aria-hidden="true"
                >
                  <div className="h-full w-1/2 bg-emerald-400 animate-pulse" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Filter Toolbar + Search-to-Catalog Hydration Trigger (4D) */}
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
            placeholder="Filtrar localmente ou buscar título / ttXXXXXXX nas APIs remotas..."
            className="w-full min-h-[44px] bg-canvas border border-white/15 rounded-xl pl-9 pr-3 text-sm text-white placeholder-slate-400"
          />
        </div>

        {searchInput.trim().length >= 2 && (
          <button
            type="button"
            disabled={liveIngesting}
            onClick={handleLiveIngest}
            className="min-h-[44px] px-4 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-extrabold flex items-center justify-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50 shrink-0"
          >
            <Zap className={`w-4 h-4 ${liveIngesting ? "animate-spin" : ""}`} />
            {liveIngesting
              ? "Ingerindo..."
              : `Buscar & Ingerir "${searchInput.trim()}" ao Vivo`}
          </button>
        )}

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
        <div
          className="w-full h-1 bg-surface-elevated overflow-hidden rounded-full"
          aria-hidden="true"
        >
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
          <div className="py-16 text-center rounded-2xl border border-dashed border-white/15 bg-surface/50 space-y-3">
            <Database className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-base font-bold text-white">
              Nenhum release encontrado localmente nesta fonte
            </p>
            <p className="text-xs text-slate-300 max-w-md mx-auto">
              Use uma das Receitas Etapa 1 no Deck acima ou busque diretamente nas APIs remotas.
            </p>
            {searchInput.trim().length >= 2 && (
              <button
                type="button"
                disabled={liveIngesting}
                onClick={handleLiveIngest}
                className="min-h-[44px] px-4 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-extrabold inline-flex items-center gap-1.5 cursor-pointer"
              >
                <Zap className="w-4 h-4" />
                Buscar &quot;{searchInput.trim()}&quot; ao vivo nas Fontes Ativas
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-5">
            {items.map((item) => {
              const unified = toUnified(item);
              const isSaved = savedShowIds.has(unified.id);
              const sourcesChip =
                item.media_sources && item.media_sources.length > 0
                  ? item.media_sources.map((s) => s.toUpperCase()).join(" + ")
                  : item.source_name || item.source_key.toUpperCase();
              const qualChip =
                item.qualities && item.qualities.length > 0
                  ? ` • ${item.qualities.slice(0, 2).join("/")}`
                  : "";
              return (
                <ShowCard
                  key={`${item.imdb_id || item.source_key}-${item.id}`}
                  show={unified}
                  fluidWidth
                  workTypeLabel={sourcesChip}
                  extraStatusLabel={`▲ ${item.max_seeds}${qualChip} • ${item.total_torrents} rel`}
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
