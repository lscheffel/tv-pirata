import { useCallback, useEffect, useMemo, useState } from "react";
import { CatalogSection, CatalogShow, FilterSnapshot, UnifiedShow } from "./types";
import { api } from "./services/api";
import { PreferencesProvider } from "./context/PreferencesContext";
import { useToast } from "./context/ToastContext";
import { AppTabId, Navbar } from "./components/Navbar";
import { DiscoverView } from "./components/DiscoverView";
import { CatalogView, INITIAL_FILTERS } from "./components/CatalogView";
import { SourcesView } from "./components/SourcesView";
import { LibraryView } from "./components/LibraryView";
import { CollectionsView } from "./components/CollectionsView";
import { StatusConfigView } from "./components/StatusConfigView";
import { ShowDetailModal } from "./components/ShowDetailModal";
import { TorrentModal } from "./components/TorrentModal";

function AppShell() {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<AppTabId>("discover");
  const [searchQuery, setSearchQuery] = useState("");
  const [catalogFilters, setCatalogFilters] = useState<FilterSnapshot>(INITIAL_FILTERS);
  const [systemHealth, setSystemHealth] = useState<"healthy" | "syncing" | "degraded">("healthy");
  const [refreshSignal, setRefreshSignal] = useState<number>(0);

  const [trendingShows, setTrendingShows] = useState<UnifiedShow[]>([]);
  const [curatedSections, setCuratedSections] = useState<CatalogSection[]>([]);
  const [_loadingDiscovery, setLoadingDiscovery] = useState(true);

  const [selectedDetailShow, setSelectedDetailShow] = useState<UnifiedShow | null>(null);
  const [selectedTorrentShow, setSelectedTorrentShow] = useState<UnifiedShow | null>(null);

  const [savedShowIds, setSavedShowIds] = useState<Set<number>>(new Set());
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState<number>(0);

  const refreshUnreadNotifications = useCallback(() => {
    api.notifications
      .getCount()
      .then((res) => setUnreadNotificationsCount(res.unread_count))
      .catch(() => {});
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
      network: cat.network || undefined,
      streaming_providers: cat.streaming_providers || (cat.network ? [cat.network] : []),
      eztv_available: true,
      has_media: true,
      media_sources: ["eztv"],
      sources_count: 1,
      source_provider: "eztv-catalog",
      seasons: [],
    };
  }, []);

  const loadInitialData = useCallback(() => {
    setLoadingDiscovery(true);

    api.discovery
      .getTrending()
      .then(setTrendingShows)
      .catch(() => {});

    api.catalog
      .getSections()
      .then(setCuratedSections)
      .catch(() => {})
      .finally(() => setLoadingDiscovery(false));

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
      .catch(() => {});

    api.sources
      .getSummary()
      .then((res) => {
        if (res.sources.some((s) => s.status === "degraded")) {
          setSystemHealth("degraded");
        }
      })
      .catch(() => {});

    refreshUnreadNotifications();
  }, [refreshUnreadNotifications]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

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

  const heroShow = useMemo(() => {
    const trendingWithBackdrop =
      trendingShows.find((s) => s.backdrop_url && s.rating >= 7.0) ||
      trendingShows.find((s) => s.backdrop_url);
    if (trendingWithBackdrop) return trendingWithBackdrop;

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

  const openCatalogWithFilters = useCallback(
    (patch: Partial<FilterSnapshot>, label?: string) => {
      setSearchQuery("");
      setCatalogFilters({ ...INITIAL_FILTERS, ...patch });
      setActiveTab("catalog");
      if (label) {
        showToast(`Catálogo filtrado: ${label}`, "info");
      }
    },
    [showToast]
  );

  return (
    <div className="min-h-screen bg-canvas text-slate-100 flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
        }}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        unreadCount={unreadNotificationsCount}
        systemHealth={systemHealth}
      />

      <main className="flex-1 pb-20">
        {activeTab === "discover" ? (
          <DiscoverView
            fallbackHero={heroShow}
            onOpenDetails={setSelectedDetailShow}
            onOpenTorrents={setSelectedTorrentShow}
            onSaveToLibrary={handleSaveToLibrary}
            onOpenCatalogWithFilters={openCatalogWithFilters}
            onNavigateTab={setActiveTab}
            savedShowIds={savedShowIds}
            refreshSignal={refreshSignal}
          />
        ) : activeTab === "catalog" ? (
          <CatalogView
            filters={catalogFilters}
            onFiltersChange={setCatalogFilters}
            globalSearchQuery={searchQuery}
            onGlobalSearchChange={setSearchQuery}
            onOpenTorrents={setSelectedTorrentShow}
            onSaveToLibrary={handleSaveToLibrary}
            onNavigateTab={setActiveTab}
            savedShowIds={savedShowIds}
            refreshSignal={refreshSignal}
          />
        ) : activeTab === "sources" ? (
          <SourcesView
            onOpenDetails={setSelectedDetailShow}
            onOpenTorrents={setSelectedTorrentShow}
            onSaveToLibrary={handleSaveToLibrary}
            savedShowIds={savedShowIds}
          />
        ) : activeTab === "library" ? (
          <LibraryView
            onOpenDetails={setSelectedDetailShow}
            onOpenTorrents={setSelectedTorrentShow}
            onNotificationsChange={refreshUnreadNotifications}
          />
        ) : activeTab === "collections" ? (
          <CollectionsView onOpenDetails={setSelectedDetailShow} />
        ) : (
          <StatusConfigView
            onHealthChange={setSystemHealth}
            onDataUpdated={() => {
              setRefreshSignal((s) => s + 1);
              loadInitialData();
            }}
          />
        )}
      </main>

      <footer className="border-t border-white/10 py-8 text-center text-xs text-slate-300">
        <p>TV Pirata 🏴‍☠️ — Ecossistema Audiovisual Multi-Fonte Dual-SSOT</p>
        <p className="mt-1 text-slate-400">
          FastAPI, React 19, Tailwind CSS e SQLite (mainstream.db + sources.db)
        </p>
      </footer>

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

      {selectedTorrentShow && (
        <TorrentModal
          show={selectedTorrentShow}
          onClose={() => setSelectedTorrentShow(null)}
          onSelectSuggestedShow={(nextShow) => setSelectedTorrentShow(nextShow)}
        />
      )}
    </div>
  );
}

export function App() {
  return (
    <PreferencesProvider>
      <AppShell />
    </PreferencesProvider>
  );
}
