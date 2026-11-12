export interface UnifiedEpisode {
  id?: number;
  episode_number: number;
  season_number: number;
  title: string;
  overview: string;
  air_date?: string;
  rating?: number;
  is_watched?: boolean;
  is_available?: boolean;
}

export interface UnifiedSeason {
  id?: number;
  season_number: number;
  name: string;
  overview: string;
  poster_url?: string;
  episode_count: number;
  episodes: UnifiedEpisode[];
}

export interface UnifiedShow {
  id: number;
  tmdb_id?: number;
  tvmaze_id?: number;
  imdb_id?: string;
  title: string;
  original_title?: string;
  overview: string;
  poster_url?: string;
  backdrop_url?: string;
  rating: number;
  genres: string[];
  first_air_date?: string;
  status?: string;
  source_provider: string;
  seasons: UnifiedSeason[];
}

export interface TorrentRelease {
  id: number;
  hash: string;
  filename: string;
  title: string;
  season: number;
  episode: number;
  magnet_url: string;
  torrent_url?: string | null;
  seeds: number;
  peers: number;
  size_bytes: number;
  quality: string;
}

export interface TagRecord {
  id: number;
  name: string;
  color: string;
}

export interface CollectionRecord {
  id: number;
  name: string;
  description: string;
  filter_criteria: string;
  created_at: string;
}

export interface ShowRecord {
  id: number;
  tmdb_id: number;
  tvmaze_id?: number | null;
  imdb_id?: string | null;
  title: string;
  original_title?: string | null;
  overview: string;
  poster_url?: string | null;
  backdrop_url?: string | null;
  rating: number;
  genres: string;
  first_air_date?: string | null;
  status?: string | null;
  user_status: "plan_to_watch" | "watching" | "completed" | "abandoned" | "paused";
  created_at: string;
  updated_at: string;
  tags?: TagRecord[];
}

export interface ShowProgress {
  show_id: number;
  total_episodes: number;
  watched_episodes: number;
  progress_percentage: number;
}

export interface CatalogShow {
  imdb_id: string;
  title: string;
  original_title?: string | null;
  overview: string;
  poster_url?: string | null;
  backdrop_url?: string | null;
  rating: number;
  genres: string;
  first_air_date?: string | null;
  status?: string | null;
  total_torrents: number;
  max_seeds: number;
  latest_season: number;
  latest_episode: number;
  latest_release_date?: string | null;
  is_enriched: boolean;
}

export interface CatalogStats {
  total_shows: number;
  total_releases: number;
  max_seeds_in_catalog: number;
  latest_release_date?: string | null;
}

export interface CatalogPaginatedResponse {
  items: CatalogShow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CatalogSection {
  id: string;
  title: string;
  icon: string;
  items: CatalogShow[];
}

export interface CatalogGenreCount {
  genre: string;
  count: number;
}

export interface ReleaseNotification {
  id: number;
  show_id: number;
  imdb_id: string;
  show_title: string;
  season: number;
  episode: number;
  release_title: string;
  quality: string;
  seeds: number;
  magnet_url: string;
  is_read: boolean;
  is_dismissed: boolean;
  created_at: string;
}

export interface UnreadNotificationCount {
  unread_count: number;
}

export interface SchedulerTelemetry {
  status: string;
  is_running: boolean;
  enabled: boolean;
  interval_seconds: number;
  last_run_at: string | null;
  next_run_eta_seconds: number | null;
  last_releases_found: number;
  last_notifications_created: number;
}

