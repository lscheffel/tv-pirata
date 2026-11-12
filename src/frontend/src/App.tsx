import { useState, useEffect, useMemo, useCallback } from "react";
import {
  Flame,
  Sparkles,
  Film,
  Zap,
  Clock,
  Shield,
  Smile,
  Compass,
  Layers,
} from "lucide-react";
import { CatalogSection, CatalogShow, UnifiedShow } from "./types";
import { api } from "./services/api";
import { Navbar } from "./components/Navbar";
import { HeroBanner } from "./components/HeroBanner";
import { ShowCarousel } from "./components/ShowCarousel";
import { ShowCard } from "./components/ShowCard";
import { ShowDetailModal } from "./components/ShowDetailModal";
import { TorrentModal } from "./components/TorrentModal";
import { LibraryView } from "./components/LibraryView";
import { CollectionsView } from "./components/CollectionsView";
import { CatalogView } from "./components/CatalogView";
import { useToast } from "./context/ToastContext";

export function App() {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<"discover" | "catalog" | "library" | "collections">("discover");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<UnifiedShow[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const [trendingShows, setTrendingShows] = useState<UnifiedShow[]>([]);
  const [curatedSections, setCuratedSections] = useState<CatalogSection[]>([]);
  const [loadingTrending, setLoadingTrending] = useState(true);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>("ALL");

  const [selectedDetailShow, setSelectedDetailShow] = useState<UnifiedShow | null>(null);
  const [selectedTorrentShow, setSelectedTorrentShow] = useState<UnifiedShow | null>(null);

  const [savedShowIds, setSavedShowIds] = useState<Set<number>>(new Set());
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState<number>(0);

  const refreshUnreadNotifications = useCallback(() => {
    api.notifications
      .getCount()
      .then((res) => setUnreadNotificationsCount(res.unread_count))
      .catch((err) => console.error("Erro ao carregar contagem de notificações:", err));
  }, []);

  const catalogToUnified = useCallback((cat: CatalogShow): UnifiedShow => {
    const numericPart = parseInt(cat.imdb_id.replace(/\D/g, ""), 10) || 1;
    return {
      id: numericPart,
      imdb_id: cat.imdb_id,
      title: cat.title,
      original_title: cat.original_title || undefined,
      overview: cat.overview,
      poster_url: cat.poster_url || undefined,
      backdrop_url: cat.backdrop_url || undefined,
      rating: cat.rating,
      genres: cat.genres ? cat.genres.split(",").map((g: string) => g.trim()) : [],
      first_air_date: cat.first_air_date || undefined,
      status: cat.status || undefined,
      source_provider: "eztv-catalog",
      seasons: [],
    };
  }, []);

  // Load trending, curated sections and saved shows
  const loadInitialData = useCallback(() => {
    setLoadingTrending(true);

    // 1. Trending shows
    api.discovery
      .getTrending()
      .then((data) => {
        setTrendingShows(data);
      })
      .catch((err) => {
        console.error("Erro ao carregar trending:", err);
      });

    // 2. Curated sections from local catalog
    api.catalog
      .getSections()
      .then((sections) => {
        setCuratedSections(sections);
      })
      .catch((err) => {
        console.error("Erro ao carregar seções temáticas do catálogo:", err);
      })
      .finally(() => setLoadingTrending(false));

    // 3. User saved library shows
    api.library
      .getShows()
      .then((records) => {
        const ids = new Set<number>();
        records.forEach((r) => {
          ids.add(r.tmdb_id);
          ids.add(r.id);
        });
        setSavedShowIds(ids);
      })
      .catch((err) => console.error("Erro ao carregar biblioteca salva:", err));

    // 4. Unread notifications
    refreshUnreadNotifications();
  }, [refreshUnreadNotifications]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timeout = setTimeout(() => {
      api.discovery
        .search(searchQuery.trim())
        .then((data) => setSearchResults(data))
        .catch((err) => {
          console.error("Erro na busca:", err);
          showToast("Erro ao realizar pesquisa", "error");
        })
        .finally(() => setIsSearching(false));
    }, 350);

    return () => clearTimeout(timeout);
  }, [searchQuery, showToast]);

  // Save to Library Action
  const handleSaveToLibrary = async (show: UnifiedShow) => {
    try {
      await api.library.saveShow(show);
      setSavedShowIds((prev) => {
        const next = new Set(prev);
        next.add(show.id);
        if (show.tmdb_id) next.add(show.tmdb_id);
        return next;
      });
      showToast(`"${show.title}" adicionada à sua biblioteca!`, "success");
    } catch {
      showToast("Série já cadastrada ou erro ao salvar", "info");
    }
  };

  // Section icon mapping
  const renderSectionIcon = (iconName: string) => {
    switch (iconName) {
      case "Flame":
        return <Flame className="w-6 h-6 text-orange-500 fill-orange-500/20" />;
      case "Clock":
        return <Clock className="w-6 h-6 text-cyan-400" />;
      case "Zap":
        return <Zap className="w-6 h-6 text-yellow-400 fill-yellow-400/20" />;
      case "Film":
        return <Film className="w-6 h-6 text-red-500" />;
      case "Shield":
        return <Shield className="w-6 h-6 text-indigo-400" />;
      case "Smile":
        return <Smile className="w-6 h-6 text-emerald-400" />;
      case "Compass":
        return <Compass className="w-6 h-6 text-teal-400" />;
      default:
        return <Sparkles className="w-6 h-6 text-purple-400" />;
    }
  };

  const heroShow = useMemo(() => {
    // 1. Trending show with backdrop
    const trendingWithBackdrop =
      trendingShows.find((s) => s.backdrop_url && s.rating >= 7.0) ||
      trendingShows.find((s) => s.backdrop_url);
    if (trendingWithBackdrop) return trendingWithBackdrop;

    // 2. Curated section show with backdrop
    for (const sec of curatedSections) {
      const match =
        sec.items.find((c) => c.backdrop_url && c.rating >= 7.0) ||
        sec.items.find((c) => c.backdrop_url);
      if (match) return catalogToUnified(match);
    }

    if (trendingShows.length > 0) return trendingShows[0];
    if (curatedSections.length > 0 && curatedSections[0].items.length > 0) {
      return catalogToUnified(curatedSections[0].items[0]);
    }
    return null;
  }, [trendingShows, curatedSections, catalogToUnified]);

  const displayedSections = useMemo(() => {
    if (activeCategoryFilter === "ALL") return curatedSections;
    return curatedSections.filter((s) => s.id === activeCategoryFilter);
  }, [curatedSections, activeCategoryFilter]);

  return (
    <div className="min-h-screen bg-canvas text-slate-100 flex flex-col font-sans">
      {/* Fixed Navbar */}
      <Navbar
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          setSearchQuery("");
        }}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        unreadCount={unreadNotificationsCount}
      />

      {/* Main Container */}
      <main className="flex-1 pb-20">
        {/* Search Results Overlay (If user is typing a search) */}
        {searchQuery.trim().length >= 2 ? (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                <Film className="w-6 h-6 text-brand-red" />
                Resultados para &quot;{searchQuery}&quot;
              </h2>
              <span className="text-sm text-slate-400">
                {isSearching ? "Buscando..." : `${searchResults.length} títulos encontrados`}
              </span>
            </div>

            {isSearching ? (
              <div className="py-20 text-center text-slate-500 animate-pulse">
                Consultando provedores de descoberta...
              </div>
            ) : searchResults.length === 0 ? (
              <div className="py-20 text-center text-slate-400">
                Nenhum título encontrado para o termo pesquisado.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 sm:gap-6">
                {searchResults.map((show) => (
                  <ShowCard
                    key={`${show.source_provider}-${show.id}`}
                    show={show}
                    onOpenDetails={setSelectedDetailShow}
                    onOpenTorrents={setSelectedTorrentShow}
                    onSaveToLibrary={handleSaveToLibrary}
                    isSaved={savedShowIds.has(show.id) || (show.tmdb_id ? savedShowIds.has(show.tmdb_id) : false)}
                  />
                ))}
              </div>
            )}
          </div>
        ) : activeTab === "discover" ? (
          /* Streaming Discovery Tab */
          <div>
            {/* Hero Banner */}
            <HeroBanner
              show={heroShow}
              onOpenDetails={setSelectedDetailShow}
              onOpenTorrents={setSelectedTorrentShow}
              onSaveToLibrary={handleSaveToLibrary}
              isSaved={heroShow ? savedShowIds.has(heroShow.id) || (heroShow.tmdb_id ? savedShowIds.has(heroShow.tmdb_id) : false) : false}
            />

            {/* Quick Category Filter Pills */}
            {curatedSections.length > 0 && (
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-6 sm:-mt-8 relative z-30 mb-8">
                <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-2.5 px-3 bg-surface-elevated/80 backdrop-blur-md rounded-2xl border border-white/10 shadow-xl">
                  <button
                    onClick={() => setActiveCategoryFilter("ALL")}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                      activeCategoryFilter === "ALL"
                        ? "bg-brand-red text-white shadow-cinema-glow"
                        : "text-slate-400 hover:text-white hover:bg-white/5"
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    Todos os Gêneros ({curatedSections.length})
                  </button>
                  {curatedSections.map((sec) => (
                    <button
                      key={sec.id}
                      onClick={() => setActiveCategoryFilter(sec.id)}
                      className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                        activeCategoryFilter === sec.id
                          ? "bg-white text-black shadow-md font-extrabold"
                          : "text-slate-400 hover:text-white hover:bg-white/5"
                      }`}
                    >
                      {sec.title}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Carousels Section */}
            <div className="max-w-7xl mx-auto space-y-8 relative z-20">
              {loadingTrending ? (
                <div className="py-16 text-center text-slate-500 animate-pulse">
                  Carregando catálogo e carrosséis temáticos...
                </div>
              ) : (
                <>
                  {/* Trending Online / Provider Shows */}
                  {activeCategoryFilter === "ALL" && trendingShows.length > 0 && (
                    <ShowCarousel
                      title="Em Alta no Momento"
                      icon={<Flame className="w-6 h-6 text-brand-red" />}
                      shows={trendingShows}
                      onOpenDetails={setSelectedDetailShow}
                      onOpenTorrents={setSelectedTorrentShow}
                      onSaveToLibrary={handleSaveToLibrary}
                      savedShowIds={savedShowIds}
                    />
                  )}

                  {/* Curated Catalog Sections */}
                  {displayedSections.map((sec) => (
                    <ShowCarousel
                      key={sec.id}
                      title={sec.title}
                      icon={renderSectionIcon(sec.icon)}
                      shows={sec.items.map(catalogToUnified)}
                      onOpenDetails={setSelectedDetailShow}
                      onOpenTorrents={setSelectedTorrentShow}
                      onSaveToLibrary={handleSaveToLibrary}
                      savedShowIds={savedShowIds}
                    />
                  ))}
                </>
              )}
            </div>
          </div>
        ) : activeTab === "catalog" ? (
          /* Real EZTV Physical Catalog Tab */
          <CatalogView
            onOpenDetails={setSelectedDetailShow}
            onOpenTorrents={setSelectedTorrentShow}
            onSaveToLibrary={handleSaveToLibrary}
            savedShowIds={savedShowIds}
          />
        ) : activeTab === "library" ? (
          /* Personal Library Tab */
          <LibraryView
            onOpenDetails={setSelectedDetailShow}
            onOpenTorrents={setSelectedTorrentShow}
            onNotificationsChange={refreshUnreadNotifications}
          />
        ) : (
          /* Collections & Tags Tab */
          <CollectionsView onOpenDetails={setSelectedDetailShow} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 text-center text-xs text-slate-500">
        <p>TV Pirata 🏴‍☠️ — Central Doméstica de Séries para Homelab & Streaming Local</p>
        <p className="mt-1">Desenvolvido com FastAPI, React 19, Tailwind CSS e SQLite</p>
      </footer>

      {/* Show Details Modal */}
      {selectedDetailShow && (
        <ShowDetailModal
          show={selectedDetailShow}
          onClose={() => setSelectedDetailShow(null)}
          onOpenTorrents={(s) => {
            setSelectedDetailShow(null);
            setSelectedTorrentShow(s);
          }}
          onSaveToLibrary={handleSaveToLibrary}
          isSaved={
            savedShowIds.has(selectedDetailShow.id) ||
            (selectedDetailShow.tmdb_id ? savedShowIds.has(selectedDetailShow.tmdb_id) : false)
          }
        />
      )}

      {/* Torrent Releases Modal */}
      {selectedTorrentShow && (
        <TorrentModal
          show={selectedTorrentShow}
          onClose={() => setSelectedTorrentShow(null)}
        />
      )}
    </div>
  );
}

