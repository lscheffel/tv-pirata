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
  ExternalSourceSummary,
  TagRecord,
  TorrentRelease,
  UnifiedShow,
  UnreadNotificationCount,
  UserExplorePreferences,
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
    sync: (source = "eztv", pages = 5, enrich = true) =>
      request<{ status: string; results: Record<string, any> }>(
        `/sources/sync?source=${encodeURIComponent(source)}&pages=${pages}&enrich=${enrich}`,
        { method: "POST" }
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
      request<{ status: string; season_id: number; episodes_updated: number }>(
        `/watches/seasons/${seasonId}/watch-all?watched=${watched}`,
        { method: "POST" }
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
