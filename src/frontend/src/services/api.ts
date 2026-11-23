import {
  CalendarEventItem,
  CatalogEpisode,
  CatalogGenreCount,
  CatalogPaginatedResponse,
  CatalogSection,
  CatalogShow,
  CatalogStats,
  CollectionRecord,
  ExploreWorksResponse,
  HydrationPipelineStatus,
  IMDbSyncJobStatus,
  MediaWorkDossier,
  PersonDossier,
  PersonSummary,
  ReleaseNotification,
  SchedulerTelemetry,
  SharedCollaborationResponse,
  ShowProgress,
  ShowRecord,
  SourceAdapterMetadata,
  SourceReleasesResponse,
  SourcesCatalogResponse,
  SourcesSummaryResponse,
  SyncRecipeMode,
  ExternalSourceSummary,
  TagRecord,
  TorrentRelease,
  UnifiedShow,
  UnreadNotificationCount,
  UserExplorePreferences,
  YifyMovieEnrichment,
} from "../types";

const BASE_URL = "/api";

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export class RequestAbortChannel {
  private controller: AbortController | null = null;

  nextSignal(): AbortSignal {
    if (this.controller) {
      this.controller.abort();
    }
    this.controller = new AbortController();
    return this.controller.signal;
  }

  abort(): void {
    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API Error [${response.status}] ${url}: ${errorText}`);
  }

  return response.json();
}

export const api = {
  explore: {
    getWorks: (
      params: {
        q?: string;
        work_types?: string;
        genres_any?: string;
        genres_all?: string;
        genres_not?: string;
        year_from?: number;
        year_to?: number;
        min_rating?: number;
        max_rating?: number;
        min_runtime?: number;
        max_runtime?: number;
        status?: string;
        streaming_providers?: string;
        territory?: string;
        country?: string;
        language?: string;
        person_query?: string;
        role_type?: string;
        min_seasons?: number;
        exclude_watched?: boolean;
        only_with_p2p?: boolean;
        data_sources?: string;
        sort_by?: string;
        page?: number;
        page_size?: number;
      } = {},
      options: { signal?: AbortSignal } = {}
    ) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          query.append(k, String(v));
        }
      });
      return request<ExploreWorksResponse>(`/explore/works?${query.toString()}`, {
        signal: options.signal,
      });
    },
    getPreferences: () => request<UserExplorePreferences>("/explore/preferences"),
    updatePreferences: (prefs: UserExplorePreferences) =>
      request<UserExplorePreferences>("/explore/preferences", {
        method: "PUT",
        body: JSON.stringify(prefs),
      }),
    getWorkDossier: (workId: number | string) =>
      request<MediaWorkDossier>(`/explore/works/${encodeURIComponent(String(workId))}`),
    getPeople: (q?: string, department?: string) => {
      const query = new URLSearchParams();
      if (q) query.append("q", q);
      if (department) query.append("department", department);
      return request<PersonSummary[]>(`/explore/people?${query.toString()}`);
    },
    getPersonDossier: (personId: number) =>
      request<PersonDossier>(`/explore/people/${personId}`),
    getCollaborations: (personA: string, personB: string) => {
      const query = new URLSearchParams({
        person_a: personA,
        person_b: personB,
      });
      return request<SharedCollaborationResponse>(
        `/explore/people/collaborations?${query.toString()}`
      );
    },
    getCalendar: (
      params: {
        work_type?: string;
        event_type?: string;
        confidence_level?: string;
        platform?: string;
      } = {}
    ) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v) query.append(k, v);
      });
      return request<CalendarEventItem[]>(`/explore/calendar?${query.toString()}`);
    },
    federate: (q?: string) => {
      const query = q ? `?q=${encodeURIComponent(q)}` : "";
      return request<{ status: string; seed_telemetry: any; live_ingested: number }>(
        `/explore/federate${query}`,
        { method: "POST" }
      );
    },
    getMainstreamStats: () =>
      request<{
        total_titles: number;
        total_episodes: number;
        hydrated_titles: number;
        eztv_badged_titles: number;
      }>("/explore/mainstream-stats"),
    updateMainstream: (mode = "delta", limit = 25) =>
      request<{
        status: string;
        mode: string;
        badges_synced: number;
        titles_hydrated: number;
        stats: {
          total_titles: number;
          total_episodes: number;
          hydrated_titles: number;
          eztv_badged_titles: number;
        };
      }>(`/explore/update-mainstream?mode=${encodeURIComponent(mode)}&limit=${limit}`, {
        method: "POST",
      }),
    hydration: {
      getStatus: () => request<HydrationPipelineStatus>("/explore/hydration/status"),
      start: (
        scope: "all" | "sources" | "metadata" = "all",
        targetProvider?: string | null,
        metadataMode: "pending" | "missing_synopsis_ptbr" = "pending",
        runMode: "novidades" | "varredura" = "novidades"
      ) => {
        const q = new URLSearchParams({
          scope,
          metadata_mode: metadataMode,
          run_mode: runMode,
        });
        if (targetProvider) q.set("target_provider", targetProvider);
        return request<HydrationPipelineStatus>(`/explore/hydration/start?${q.toString()}`, {
          method: "POST",
        });
      },
      updateConfig: (payload: {
        sweep_min_votes?: number;
        sweep_enabled_sources?: string[];
        recent_pages_per_source?: number;
      }) =>
        request<HydrationPipelineStatus>("/explore/hydration/config", {
          method: "POST",
          body: JSON.stringify(payload),
        }),
      pause: () =>
        request<HydrationPipelineStatus>("/explore/hydration/pause", { method: "POST" }),
      step: (
        scope: "all" | "sources" | "metadata" = "all",
        targetProvider?: string | null,
        metadataMode: "pending" | "missing_synopsis_ptbr" = "pending"
      ) => {
        const q = new URLSearchParams({ scope, metadata_mode: metadataMode });
        if (targetProvider) q.set("target_provider", targetProvider);
        return request<{ status: HydrationPipelineStatus; step_telemetry: Record<string, any> }>(
          `/explore/hydration/step?${q.toString()}`,
          { method: "POST" }
        );
      },
      resetCursor: (target = "all") =>
        request<HydrationPipelineStatus>(
          `/explore/hydration/reset-cursor?target=${encodeURIComponent(target)}`,
          { method: "POST" }
        ),
      skipRecent: (sourceKey: string) =>
        request<HydrationPipelineStatus>(
          `/explore/hydration/sources/${encodeURIComponent(sourceKey)}/skip-recent`,
          { method: "POST" }
        ),
    },
    imdb: {
      getStatus: () => request<IMDbSyncJobStatus>("/explore/imdb/status"),
      sync: (includeEpisodes = false) =>
        request<IMDbSyncJobStatus>(
          `/explore/imdb/sync?include_episodes=${includeEpisodes ? "true" : "false"}`,
          { method: "POST" }
        ),
      reindexFts: () =>
        request<IMDbSyncJobStatus>("/explore/imdb/reindex-fts", { method: "POST" }),
    },
  },

  discovery: {
    getTrending: () => request<UnifiedShow[]>("/discovery/trending"),
    search: (q: string, options: { signal?: AbortSignal } = {}) =>
      request<UnifiedShow[]>(`/discovery/search?q=${encodeURIComponent(q)}`, {
        signal: options.signal,
      }),
    getShowDetails: (id: number, provider?: string, imdbId?: string) => {
      const query = new URLSearchParams();
      if (provider) query.append("provider", provider);
      if (imdbId) query.append("imdb_id", imdbId);
      const qStr = query.toString();
      return request<UnifiedShow>(`/discovery/shows/${id}${qStr ? `?${qStr}` : ""}`);
    },
  },

  sources: {
    getAdapters: () =>
      request<{ adapters: SourceAdapterMetadata[]; load_errors: Record<string, string> }>(
        "/sources/adapters"
      ),
    getSummary: () => request<SourcesSummaryResponse>("/sources/summary"),
    createSource: (payload: Record<string, any>) =>
      request<ExternalSourceSummary>("/sources", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateSource: (sourceKey: string, payload: Record<string, any>) =>
      request<ExternalSourceSummary>(`/sources/${encodeURIComponent(sourceKey)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    deleteSource: (sourceKey: string) =>
      request<{ status: string; source_key: string }>(
        `/sources/${encodeURIComponent(sourceKey)}`,
        { method: "DELETE" }
      ),
    testSource: (sourceKey: string) =>
      request<{
        source_key: string;
        adapter_key: string;
        status: string;
        releases_found?: number;
        message?: string | null;
        challenge_url?: string | null;
        latency_ms: number;
      }>(`/sources/${encodeURIComponent(sourceKey)}/test`, { method: "POST" }),
    getReleases: (
      imdbId: string,
      source?: string,
      options: {
        signal?: AbortSignal;
        includeLive?: boolean;
        live?: "auto" | "cache" | "force";
        qOverride?: string;
        title?: string;
        year?: number;
      } = {}
    ) => {
      const query = new URLSearchParams({ imdb_id: imdbId });
      if (source && source !== "all") query.append("source", source);
      if (options.includeLive !== undefined) {
        query.append("include_live", String(options.includeLive));
      }
      if (options.live) query.append("live", options.live);
      if (options.qOverride) query.append("q_override", options.qOverride);
      if (options.title) query.append("title", options.title);
      if (options.year) query.append("year", String(options.year));
      return request<SourceReleasesResponse>(`/sources/releases?${query.toString()}`, {
        signal: options.signal,
      });
    },
    getCatalog: (
      params: {
        source?: string;
        search?: string;
        genre?: string;
        min_seeds?: number;
        sort_by?: string;
        page?: number;
        page_size?: number;
      } = {},
      options: { signal?: AbortSignal } = {}
    ) => {
      const query = new URLSearchParams();
      if (params.source && params.source !== "all") query.append("source", params.source);
      if (params.search) query.append("search", params.search);
      if (params.genre) query.append("genre", params.genre);
      if (params.min_seeds !== undefined) query.append("min_seeds", String(params.min_seeds));
      if (params.sort_by) query.append("sort_by", params.sort_by);
      if (params.page) query.append("page", String(params.page));
      if (params.page_size) query.append("page_size", String(params.page_size));
      return request<SourcesCatalogResponse>(`/sources/catalog?${query.toString()}`, {
        signal: options.signal,
      });
    },
    sync: (
      source = "eztv",
      pages = 5,
      enrich = true,
      opts: {
        mode?: SyncRecipeMode;
        quality?: string;
        minimum_rating?: number;
        sort_by?: string;
        min_seeds_floor?: number;
        prune_after?: boolean;
      } = {}
    ) => {
      const q = new URLSearchParams({
        source,
        pages: String(pages),
        enrich: String(enrich),
      });
      if (opts.mode) q.append("mode", opts.mode);
      if (opts.quality && opts.quality !== "All") q.append("quality", opts.quality);
      if (opts.minimum_rating && opts.minimum_rating > 0) {
        q.append("minimum_rating", String(opts.minimum_rating));
      }
      if (opts.sort_by) q.append("sort_by", opts.sort_by);
      if (opts.min_seeds_floor !== undefined) {
        q.append("min_seeds_floor", String(opts.min_seeds_floor));
      }
      if (opts.prune_after !== undefined) {
        q.append("prune_after", String(opts.prune_after));
      }
      return request<{ status: string; mode?: string; prune?: any; results: Record<string, any> }>(
        `/sources/sync?${q.toString()}`,
        { method: "POST" }
      );
    },
    prune: (source = "all", minSeedsFloor = 1) => {
      const q = new URLSearchParams({
        source,
        min_seeds_floor: String(minSeedsFloor),
        max_zero_seed_hours: "0",
      });
      return request<{ status: string; removed_releases: number }>(
        `/sources/prune?${q.toString()}`,
        { method: "POST" }
      );
    },
    liveIngest: (query: string, source = "all", limit = 20) => {
      const q = new URLSearchParams({
        q: query,
        source,
        limit: String(limit),
      });
      return request<{
        status: string;
        query: string;
        ingested_count: number;
        matched_imdb_ids: string[];
        diagnostics: Record<string, any>;
      }>(`/sources/live-ingest?${q.toString()}`, { method: "POST" });
    },
    getYifyEnrichment: (imdbId: string, options: { signal?: AbortSignal } = {}) =>
      request<YifyMovieEnrichment>(
        `/sources/yify/enrichment/${encodeURIComponent(imdbId)}`,
        { signal: options.signal }
      ),
  },

  library: {
    getShows: () => request<ShowRecord[]>("/library/shows"),
    saveShow: (show: UnifiedShow) =>
      request<ShowRecord>("/library/shows", {
        method: "POST",
        body: JSON.stringify({ show, user_status: "plan_to_watch" }),
      }),
    getShow: (id: number) => request<ShowRecord>(`/library/shows/${id}`),
    updateStatus: (id: number, status: string) =>
      request<ShowRecord>(`/library/shows/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ user_status: status }),
      }),
    deleteShow: (id: number) =>
      request<{ status: string; id: number }>(`/library/shows/${id}`, {
        method: "DELETE",
      }),
  },

  watches: {
    toggleEpisode: (episodeId: number) =>
      request<{ id: number; episode_id: number; is_watched: boolean }>(
        `/watches/episodes/${episodeId}/toggle`,
        { method: "POST" }
      ),
    watchAllSeason: (seasonId: number, watched = true) =>
      request<{ status: string; season_id: number; updated_episodes: number }>(
        `/watches/seasons/${seasonId}/watch-all`,
        {
          method: "POST",
          body: JSON.stringify({ is_watched: watched }),
        }
      ),
    getShowProgress: (showId: number) =>
      request<ShowProgress>(`/watches/shows/${showId}/progress`),
  },

  torrents: {
    getByImdb: (imdbId: string) =>
      request<TorrentRelease[]>(`/torrents/shows/${encodeURIComponent(imdbId)}`),
  },

  collections: {
    getTags: () => request<TagRecord[]>("/collections/tags"),
    createTag: (name: string, color: string) =>
      request<TagRecord>("/collections/tags", {
        method: "POST",
        body: JSON.stringify({ name, color }),
      }),
    getSmartCollections: () => request<CollectionRecord[]>("/collections/smart"),
    createSmartCollection: (name: string, description: string, filterCriteria: string) =>
      request<CollectionRecord>("/collections/smart", {
        method: "POST",
        body: JSON.stringify({ name, description, filter_criteria: filterCriteria }),
      }),
    getSmartItems: (collectionId: number) =>
      request<ShowRecord[]>(`/collections/smart/${collectionId}/items`),
  },

  catalog: {
    getShows: (params: {
      search?: string;
      genre?: string;
      min_seeds?: number;
      sort_by?: string;
      page?: number;
      page_size?: number;
    } = {}) => {
      const query = new URLSearchParams();
      if (params.search) query.append("search", params.search);
      if (params.genre) query.append("genre", params.genre);
      if (params.min_seeds !== undefined) query.append("min_seeds", params.min_seeds.toString());
      if (params.sort_by) query.append("sort_by", params.sort_by);
      if (params.page) query.append("page", params.page.toString());
      if (params.page_size) query.append("page_size", params.page_size.toString());
      return request<CatalogPaginatedResponse>(`/catalog/shows?${query.toString()}`);
    },
    getShow: (imdbId: string) =>
      request<{ show: CatalogShow; episodes: CatalogEpisode[]; releases: TorrentRelease[] }>(
        `/catalog/shows/${encodeURIComponent(imdbId)}`
      ),
    getStats: () => request<CatalogStats>("/catalog/stats"),
    getGenres: () => request<CatalogGenreCount[]>("/catalog/genres"),
    getSections: () => request<CatalogSection[]>("/catalog/sections"),
    sync: (pages = 5) =>
      request<{ status: string; telemetry: any }>(`/catalog/sync?pages=${pages}`, {
        method: "POST",
      }),
    enrichPending: (limit = 100) =>
      request<{ status: string; shows_enriched: number }>(`/catalog/enrich-pending?limit=${limit}`, {
        method: "POST",
      }),
  },

  notifications: {
    list: (unreadOnly = false) =>
      request<ReleaseNotification[]>(`/notifications?unread_only=${unreadOnly}`),
    getCount: () => request<UnreadNotificationCount>("/notifications/count"),
    markAsRead: (id: number) =>
      request<ReleaseNotification>(`/notifications/${id}/read`, { method: "PATCH" }),
    dismissAll: () =>
      request<{ status: string; dismissed_count: number }>("/notifications/dismiss-all", {
        method: "POST",
      }),
    getSchedulerStatus: () => request<SchedulerTelemetry>("/notifications/scheduler-status"),
    triggerSync: () =>
      request<{ status: string; telemetry: any }>("/notifications/trigger-sync", {
        method: "POST",
      }),
  },
};
