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
  TagRecord,
  TorrentRelease,
  UnifiedShow,
  UnreadNotificationCount,
} from "../types";

const BASE_URL = "/api";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
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
        sort_by?: string;
        page?: number;
        page_size?: number;
      } = {}
    ) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          query.append(k, String(v));
        }
      });
      return request<ExploreWorksResponse>(`/explore/works?${query.toString()}`);
    },
    getWorkDossier: (workId: number) =>
      request<MediaWorkDossier>(`/explore/works/${workId}`),
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
  },

  discovery: {
    getTrending: () => request<UnifiedShow[]>("/discovery/trending"),
    search: (q: string) => request<UnifiedShow[]>(`/discovery/search?q=${encodeURIComponent(q)}`),
    getShowDetails: (id: number, provider?: string, imdbId?: string) => {
      const query = new URLSearchParams();
      if (provider) query.append("provider", provider);
      if (imdbId) query.append("imdb_id", imdbId);
      const qStr = query.toString();
      return request<UnifiedShow>(`/discovery/shows/${id}${qStr ? `?${qStr}` : ""}`);
    },
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
