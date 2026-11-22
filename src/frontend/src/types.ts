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
  network?: string | null;
  streaming_providers?: string[];
  eztv_available?: boolean;
  eztv_show_id?: number | null;
  has_media?: boolean;
  media_sources?: string[];
  sources_count?: number;
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

export interface CatalogEpisode {
  id: number;
  show_id: number;
  season: number;
  episode: number;
  title?: string | null;
  airdate?: string | null;
  runtime?: number | null;
  rating?: number | null;
  summary?: string | null;
  source: string;
}

export interface CatalogShow {
  eztv_show_id?: number;
  imdb_id: string;
  slug?: string | null;
  title: string;
  original_title?: string | null;
  overview: string;
  poster_url?: string | null;
  backdrop_url?: string | null;
  rating: number;
  genres: string;
  first_air_date?: string | null;
  status?: string | null;
  network?: string | null;
  streaming_providers?: string[];
  air_day_time?: string | null;
  tvmaze_id?: number | null;
  episodes_count?: number;
  total_torrents: number;
  max_seeds: number;
  latest_season: number;
  latest_episode: number;
  latest_release_date?: string | null;
  is_enriched: boolean;
}

export interface CatalogStats {
  total_shows: number;
  total_episodes?: number;
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

// --- ADR-008: Layer 1 Audiovisual Discovery Core Types ---

export interface RatingSourceEntry {
  rating: number;
  votes: number;
}

export interface MediaWorkSummary {
  id: number;
  work_type: "movie" | "tv_show" | "mini_series" | "documentary" | "animation" | "special" | string;
  title: string;
  original_title?: string | null;
  overview: string;
  tagline?: string | null;
  release_date?: string | null;
  release_year?: number | null;
  runtime_minutes?: number | null;
  status: string;
  origin_country: string;
  original_language: string;
  poster_url?: string | null;
  backdrop_url?: string | null;
  canonical_rating: number;
  rating_source: string;
  ratings_breakdown: Record<string, RatingSourceEntry>;
  popularity_score: number;
  vote_count: number;
  seasons_count: number;
  episodes_count: number;
  network_or_studio?: string | null;
  collection_name?: string | null;
  genres: string[];
  directors: string[];
  top_cast: string[];
  streaming_providers: string[];
  imdb_id?: string | null;
  tmdb_id?: number | null;
  tvmaze_id?: number | null;
  wikidata_id?: string | null;
  user_library_status?: string | null;
  p2p_max_seeds: number;
  eztv_available?: boolean;
  eztv_show_id?: number | null;
  has_media?: boolean;
  media_sources?: string[];
  sources_count?: number;
}

export interface FacetBucket {
  key: string;
  count: number;
}

export interface DiscoveryFacets {
  work_types: FacetBucket[];
  data_sources?: FacetBucket[];
  genres: FacetBucket[];
  streaming_providers: FacetBucket[];
  decades: FacetBucket[];
  statuses: FacetBucket[];
  countries: FacetBucket[];
}

export interface ExploreWorksResponse {
  items: MediaWorkSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  facets: DiscoveryFacets;
}

export interface ExternalIdEntry {
  provider: string;
  external_id: string;
  confidence: string;
}

export interface DataProvenanceEntry {
  source_provider: string;
  external_id: string;
  field_name: string;
  field_value: string;
  selection_reason: string;
  fetched_at: string;
}

export interface WorkCreditEntry {
  person_id: number;
  name: string;
  role_type: string;
  character_name?: string | null;
  department: string;
  country?: string | null;
}

export interface StreamingAvailabilityEntry {
  provider_name: string;
  territory: string;
  monetization_type: string;
  source_provider: string;
}

export interface ExplicitRelationEntry {
  work_id: number;
  title: string;
  work_type: string;
  release_year?: number | null;
  poster_url?: string | null;
  canonical_rating: number;
  relation_type: string;
  notes?: string | null;
}

export interface SimilarWorkEntry {
  id: number;
  title: string;
  original_title?: string | null;
  work_type: string;
  release_year?: number | null;
  poster_url?: string | null;
  canonical_rating: number;
  genres: string[];
  similarity_score: number;
  similarity_reasons: string[];
}

export interface CalendarEventItem {
  id: number;
  work_id?: number;
  work_title?: string;
  work_type?: string;
  poster_url?: string | null;
  genres?: string[];
  event_type: string;
  event_date: string;
  confidence_level: "confirmed" | "estimated" | "announced" | string;
  territory: string;
  platform_or_network?: string | null;
  season_number?: number | null;
  episode_number?: number | null;
  event_title: string;
  source_provider?: string;
}

export interface MediaWorkDossier extends MediaWorkSummary {
  external_identifiers: ExternalIdEntry[];
  provenance: DataProvenanceEntry[];
  credits: WorkCreditEntry[];
  availabilities: StreamingAvailabilityEntry[];
  explicit_relations: ExplicitRelationEntry[];
  similar_works: SimilarWorkEntry[];
  calendar_events: CalendarEventItem[];
}

export interface PersonSummary {
  id: number;
  name: string;
  known_for_department: string;
  country?: string | null;
  roles: string[];
  works_count: number;
  average_rating: number;
  notable_works: string[];
}

export interface PersonFilmographyItem {
  work_id: number;
  title: string;
  original_title?: string | null;
  work_type: string;
  release_year?: number | null;
  canonical_rating: number;
  poster_url?: string | null;
  status: string;
  roles: string[];
  character_name?: string | null;
  genres: string[];
}

export interface FrequentCollaboratorItem {
  person_id: number;
  name: string;
  department: string;
  shared_works_count: number;
  shared_titles: string[];
}

export interface PersonDossier {
  id: number;
  name: string;
  known_for_department: string;
  country?: string | null;
  filmography: PersonFilmographyItem[];
  frequent_collaborators: FrequentCollaboratorItem[];
}

export interface SharedCollaborationResponse {
  person_a: string;
  person_b: string;
  shared_works: {
    id: number;
    title: string;
    work_type: string;
    release_year?: number | null;
    canonical_rating: number;
    poster_url?: string | null;
    person_a_role: string;
    person_b_role: string;
  }[];
}

// --- ADR-012: Multi-Source Catalog & Interactive Preferences ---

export type ProviderBadgeAction = "filter_provider" | "open_details" | "open_provider_info";
export type MediaBadgeAction = "open_sources_modal" | "filter_has_media" | "open_details";

export interface UserExplorePreferences {
  schema_version: 1;
  badge_provider_action: ProviderBadgeAction;
  badge_media_action: MediaBadgeAction;
  auto_apply_filters: boolean;
  show_all_genres: boolean;
  filter_panel_expanded: boolean;
}

export interface ExternalSourceSummary {
  source_key: string;
  display_name: string;
  adapter_key?: string;
  source_kind?: "torrent_mirrorable" | "unique_web_source" | string;
  kind: string;
  media_types: string[];
  base_url?: string | null;
  config?: Record<string, any>;
  priority?: number;
  enabled: boolean;
  status: "ready" | "syncing" | "degraded" | "cooldown" | "challenge_required" | "idle" | string;
  cooldown_until?: string | null;
  last_sync_at?: string | null;
  last_error?: string | null;
  total_titles: number;
  total_releases: number;
  supports_sync?: boolean;
  supports_search?: boolean;
}

export interface SourceAdapterMetadata {
  adapter_key: string;
  display_name: string;
  description: string;
  default_source_kind: "torrent_mirrorable" | "unique_web_source" | string;
  default_media_types: string[];
  supports_sync: boolean;
  supports_search: boolean;
  secret_fields: string[];
  config_schema: Record<string, any>;
}

export interface SourceDiagnosticInfo {
  source_key: string;
  source_name: string;
  adapter_key: string;
  source_kind: "torrent_mirrorable" | "unique_web_source" | string;
  status: "ok" | "challenge_required" | "cooldown" | "timeout" | "error" | string;
  message?: string | null;
  challenge_url?: string | null;
  from_cache: boolean;
  cached_at?: string | null;
  latency_ms?: number;
}

export interface SourcesSummaryResponse {
  sources: ExternalSourceSummary[];
  totals: {
    total_sources: number;
    active_sources: number;
    total_titles: number;
    total_releases: number;
  };
}

export interface SourceReleaseItem {
  id: number | string;
  source_key: string;
  source_name: string;
  release_type: "magnet" | "torrent" | "link" | string;
  hash: string;
  filename: string;
  title: string;
  season: number;
  episode: number;
  quality: string;
  seeds: number;
  peers: number;
  size_bytes: number;
  magnet_url: string;
  torrent_url?: string | null;
  external_url?: string | null;
  matched_by?: string;
  match_confidence?: number;
}

export interface SourceReleasesResponse {
  imdb_id: string;
  total: number;
  available_sources: string[];
  by_source: Record<string, SourceReleaseItem[]>;
  items: SourceReleaseItem[];
  approx_matches?: SourceReleaseItem[];
  source_diagnostics?: Record<string, SourceDiagnosticInfo>;
}

export interface SourceCatalogItem {
  id: string;
  source_key: string;
  source_name: string;
  media_sources?: string[];
  qualities?: string[];
  release_type: string;
  eztv_show_id?: number;
  tvmaze_id?: number | null;
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
  network?: string | null;
  streaming_providers?: string[];
  episodes_count?: number;
  total_torrents: number;
  max_seeds: number;
  latest_season: number;
  latest_episode: number;
  latest_release_date?: string | null;
  is_enriched: boolean;
}

export type SyncRecipeMode = "incremental" | "baseline" | "library" | "prune";

export interface YifyMovieEnrichment {
  status: string;
  endpoint?: string;
  imdb_id: string;
  movie_id?: number | null;
  details?: {
    title?: string;
    year?: number;
    rating?: number;
    runtime?: number;
    download_count?: number;
    like_count?: number;
    mpa_rating?: string;
    yt_trailer_code?: string;
    rt_critics_score?: number | null;
    rt_audience_score?: number | null;
    cast?: { name: string; character_name?: string }[];
  } | null;
  suggestions: {
    movie_id?: number;
    imdb_id?: string | null;
    work_imdb_id?: string | null;
    title: string;
    title_ptbr?: string;
    year?: number;
    rating: number;
    poster_url?: string | null;
    qualities?: string[];
  }[];
  parental_guides: {
    type: string;
    parental_guide_text: string;
  }[];
}

export interface SourcesCatalogResponse {
  items: SourceCatalogItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  available_sources: ExternalSourceSummary[];
}

export interface PillarSourceCursor {
  source_key: string;
  mode: "BOOTSTRAP" | "DELTA";
  next_page: number;
  total_pages: number;
  recent_exhausted: boolean;
  catalog_sweep_offset: number;
  titles_indexed: number;
  releases_indexed: number;
  bootstrap_completed: boolean;
  last_run_at?: string | null;
  last_error?: string | null;
  sweep_pct?: number;
  sweep_total?: number;
  eta_seconds?: number | null;
  rate_per_minute?: number;
  consecutive_zero_recent_pages?: number;
}

export interface WaterfallProvenanceCounts {
  imdb: number;
  tmdb: number;
  tvmaze: number;
  eztv: number;
  yify: number;
  open_sources: number;
  self_healed_eztv: number;
  self_healed_mainstream: number;
}

export interface CanonicalCoverageSnapshot {
  total_shows: number;
  with_poster: number;
  with_synopsis: number;
  with_synopsis_ptbr: number;
  missing_posters: number;
  missing_synopsis: number;
  pending_details?: number;
  posters_pct: number;
  synopsis_pct: number;
  synopsis_ptbr_pct: number;
  eztv_shows: number;
  eztv_missing_meta: number;
  total_episodes?: number;
  with_tmdb_id?: number;
  tmdb_pct?: number;
  series_total?: number;
  series_with_tvmaze_id?: number;
  tvmaze_pct?: number;
  tmdb_configured?: boolean;
  imdb_last_sync_at?: string | null;
}

export interface HydrationActivityEvent {
  timestamp: string;
  stage: string;
  target: string;
  outcome: "ok" | "partial" | "skipped" | "error";
  message: string;
}

export interface HydrationPipelineStatus {
  schema_version: 1;
  state: "IDLE" | "RUNNING" | "PAUSED" | "COMPLETED" | "ERROR";
  scope: "all" | "sources" | "metadata";
  overall_mode: "BOOTSTRAP" | "DELTA";
  imdb_backbone_mode: "BOOTSTRAP" | "DELTA";
  eztv_mode: "BOOTSTRAP" | "DELTA";
  steps_executed: number;
  metadata_batches_executed?: number;
  last_step_summary?: string | null;
  last_error?: string | null;
  updated_at?: string | null;
  is_worker_active: boolean;
  current_stage?: string | null;
  current_target?: string | null;
  started_at?: string | null;
  elapsed_seconds?: number;
  total_elapsed_seconds?: number;
  items_processed_in_run?: number;
  rate_per_minute?: number;
  eta_seconds?: number | null;
  sources_eta_seconds?: number | null;
  metadata_eta_seconds?: number | null;
  sidecar_eta_seconds?: number | null;
  ema_rates?: Record<string, number>;
  target_provider?: string | null;
  metadata_mode?: "pending" | "missing_synopsis_ptbr";
  focus_cursor_imdb?: string | null;
  recent_events?: HydrationActivityEvent[];
  coverage: CanonicalCoverageSnapshot;
  sources: Record<string, PillarSourceCursor>;
  provenance: WaterfallProvenanceCounts;
}

export interface IMDbSyncJobStatus {
  state: "IDLE" | "RUNNING" | "COMPLETED" | "ERROR";
  stage:
    | "idle"
    | "downloading"
    | "importing_works"
    | "importing_episodes"
    | "rebuilding_fts"
    | "completed"
    | "error";
  progress_pct: number;
  include_episodes: boolean;
  works_processed: number;
  episodes_processed: number;
  last_sync_at?: string | null;
  last_error?: string | null;
  message?: string | null;
}

