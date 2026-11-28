import {
  CustomShortcutConfig,
  ForeignTitlesMode,
  MediaBadgeAction,
  ProviderBadgeAction,
  SmartListConfig,
  SmartListSort,
  UserExplorePreferences,
} from "../types";

export const EXPLORE_PREFS_STORAGE_KEY = "tv_pirata_explore_prefs_v1";

export const DEFAULT_SMART_LISTS_V2: SmartListConfig[] = [
  { id: "trending_now", title: "Em Alta Agora (2024–2026)", category: "trending_now", enabled: true, order: 0, limit: 100, sort_by: "balanced", only_with_media: false },
  { id: "p2p_fresh", title: "Recém-Chegados com Mídia (P2P)", category: "p2p_fresh", enabled: true, order: 1, limit: 100, sort_by: "p2p_recent", only_with_media: false },
  { id: "acclaimed_movies", title: "Filmes Aclamados (≥ 7.8)", category: "acclaimed_movies", enabled: true, order: 2, limit: 100, sort_by: "rating", only_with_media: false },
  { id: "running_series", title: "Séries Imperdíveis em Exibição", category: "running_series", enabled: true, order: 3, limit: 100, sort_by: "popularity", only_with_media: false },
  { id: "scifi_fantasy_thriller", title: "Sci-Fi, Fantasia & Suspense", category: "scifi_fantasy_thriller", enabled: true, order: 4, limit: 100, sort_by: "balanced", only_with_media: false },
  { id: "crime_mystery", title: "Crime, Investigação & Mistério", category: "crime_mystery", enabled: true, order: 5, limit: 100, sort_by: "balanced", only_with_media: false },
  { id: "anime_animation_docs", title: "Animes, Animações & Docs", category: "anime_animation_docs", enabled: true, order: 6, limit: 100, sort_by: "rating", only_with_media: false },
  { id: "because_you_watched", title: "Porque Você Assiste / Curtiu", category: "because_you_watched", enabled: true, order: 7, limit: 100, sort_by: "balanced", only_with_media: false },
  { id: "on_your_radar", title: "No Seu Radar (Seus Gêneros)", category: "on_your_radar", enabled: true, order: 8, limit: 100, sort_by: "balanced", only_with_media: false },
  { id: "hidden_gems_for_you", title: "Joias Ocultas para Você", category: "hidden_gems_for_you", enabled: true, order: 9, limit: 100, sort_by: "rating", only_with_media: false },
  { id: "horror_supernatural", title: "Terror & Sobrenatural", category: "horror_supernatural", enabled: false, order: 10, limit: 100, sort_by: "balanced", only_with_media: false },
  { id: "action_adventure", title: "Ação & Aventura", category: "action_adventure", enabled: false, order: 11, limit: 100, sort_by: "popularity", only_with_media: false },
  { id: "miniseries_fast", title: "Minisséries Para Maratonar", category: "miniseries_fast", enabled: false, order: 12, limit: 100, sort_by: "rating", only_with_media: false },
  { id: "classics_masterpieces", title: "Clássicos Essenciais (≥ 8.4)", category: "classics_masterpieces", enabled: false, order: 13, limit: 100, sort_by: "rating", only_with_media: false },
  { id: "releases_2026", title: "Lançamentos & Destaques 2026", category: "releases_2026", enabled: false, order: 14, limit: 100, sort_by: "newest", only_with_media: false },
  { id: "comedy_sitcoms", title: "Comédias & Sitcoms", category: "comedy_sitcoms", enabled: false, order: 15, limit: 100, sort_by: "balanced", only_with_media: false },
];

export const DEFAULT_EXPLORE_PREFERENCES: UserExplorePreferences = {
  schema_version: 2,
  badge_provider_action: "filter_provider",
  badge_media_action: "open_sources_modal",
  auto_apply_filters: false,
  show_all_genres: false,
  filter_panel_expanded: false,
  discovery_variance_pct: 45,
  hero_auto_rotate: true,
  hero_interval_sec: 12,
  impression_ttl_hours: 48,
  foreign_titles_mode: "off",
  parental_control_enabled: false,
  smart_lists: DEFAULT_SMART_LISTS_V2,
  hidden_builtin_shortcuts: [],
  custom_shortcuts: [],
};

const VALID_PROVIDER_ACTIONS: ProviderBadgeAction[] = [
  "filter_provider",
  "open_details",
  "open_provider_info",
];

const VALID_MEDIA_ACTIONS: MediaBadgeAction[] = [
  "open_sources_modal",
  "filter_has_media",
  "open_details",
];

const VALID_SORTS: SmartListSort[] = ["balanced", "rating", "popularity", "newest", "p2p_recent"];
const VALID_FOREIGN_MODES: ForeignTitlesMode[] = ["off", "lite", "all"];

export function sanitizePreferences(raw: unknown): UserExplorePreferences {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_EXPLORE_PREFERENCES };
  }
  const obj = raw as Record<string, unknown>;
  const providerAction = VALID_PROVIDER_ACTIONS.includes(
    obj.badge_provider_action as ProviderBadgeAction
  )
    ? (obj.badge_provider_action as ProviderBadgeAction)
    : DEFAULT_EXPLORE_PREFERENCES.badge_provider_action;

  const mediaAction = VALID_MEDIA_ACTIONS.includes(
    obj.badge_media_action as MediaBadgeAction
  )
    ? (obj.badge_media_action as MediaBadgeAction)
    : DEFAULT_EXPLORE_PREFERENCES.badge_media_action;

  const clampInt = (val: unknown, min: number, max: number, fallback: number): number =>
    typeof val === "number" && Number.isFinite(val)
      ? Math.max(min, Math.min(max, Math.round(val)))
      : fallback;

  const rawLists = Array.isArray(obj.smart_lists) ? obj.smart_lists : [];
  const smartLists: SmartListConfig[] =
    rawLists.length > 0
      ? rawLists
        .filter((it): it is Record<string, unknown> => Boolean(it && typeof it === "object"))
        .map((it, idx) => ({
          id: String(it.id || `list_${idx}`),
          title: String(it.title || "Lista"),
          category: String(it.category || it.id || "trending_now"),
          enabled: typeof it.enabled === "boolean" ? it.enabled : true,
          order: typeof it.order === "number" ? it.order : idx,
          limit: clampInt(it.limit, 20, 100, 100),
          sort_by: VALID_SORTS.includes(it.sort_by as SmartListSort)
            ? (it.sort_by as SmartListSort)
            : "balanced",
          only_with_media: typeof it.only_with_media === "boolean" ? it.only_with_media : false,
          variance_override:
            typeof it.variance_override === "number"
              ? clampInt(it.variance_override, 0, 100, 45)
              : null,
        }))
      : DEFAULT_SMART_LISTS_V2;

  const customShortcuts: CustomShortcutConfig[] = Array.isArray(obj.custom_shortcuts)
    ? obj.custom_shortcuts
      .filter((sc): sc is Record<string, unknown> => Boolean(sc && typeof sc === "object"))
      .map((sc, idx) => ({
        id: String(sc.id || `custom_${idx}`),
        label: String(sc.label || "Atalho"),
        filters:
          sc.filters && typeof sc.filters === "object"
            ? (sc.filters as Record<string, unknown>)
            : {},
        pinned: typeof sc.pinned === "boolean" ? sc.pinned : true,
      }))
    : [];

  return {
    schema_version: 2,
    badge_provider_action: providerAction,
    badge_media_action: mediaAction,
    auto_apply_filters:
      typeof obj.auto_apply_filters === "boolean"
        ? obj.auto_apply_filters
        : DEFAULT_EXPLORE_PREFERENCES.auto_apply_filters,
    show_all_genres:
      typeof obj.show_all_genres === "boolean"
        ? obj.show_all_genres
        : DEFAULT_EXPLORE_PREFERENCES.show_all_genres,
    filter_panel_expanded:
      typeof obj.filter_panel_expanded === "boolean"
        ? obj.filter_panel_expanded
        : DEFAULT_EXPLORE_PREFERENCES.filter_panel_expanded,
    discovery_variance_pct: clampInt(
      obj.discovery_variance_pct,
      0,
      100,
      DEFAULT_EXPLORE_PREFERENCES.discovery_variance_pct
    ),
    hero_auto_rotate:
      typeof obj.hero_auto_rotate === "boolean"
        ? obj.hero_auto_rotate
        : DEFAULT_EXPLORE_PREFERENCES.hero_auto_rotate,
    hero_interval_sec: clampInt(
      obj.hero_interval_sec,
      5,
      60,
      DEFAULT_EXPLORE_PREFERENCES.hero_interval_sec
    ),
    impression_ttl_hours: clampInt(
      obj.impression_ttl_hours,
      12,
      168,
      DEFAULT_EXPLORE_PREFERENCES.impression_ttl_hours
    ),
    foreign_titles_mode: VALID_FOREIGN_MODES.includes(
      obj.foreign_titles_mode as ForeignTitlesMode
    )
      ? (obj.foreign_titles_mode as ForeignTitlesMode)
      : DEFAULT_EXPLORE_PREFERENCES.foreign_titles_mode,
    parental_control_enabled:
      typeof obj.parental_control_enabled === "boolean"
        ? obj.parental_control_enabled
        : DEFAULT_EXPLORE_PREFERENCES.parental_control_enabled,
    smart_lists: smartLists,
    hidden_builtin_shortcuts: Array.isArray(obj.hidden_builtin_shortcuts)
      ? obj.hidden_builtin_shortcuts.map(String)
      : [],
    custom_shortcuts: customShortcuts,
  };
}

export function loadPreferencesLocal(): UserExplorePreferences {
  try {
    const raw = window.localStorage.getItem(EXPLORE_PREFS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_EXPLORE_PREFERENCES };
    return sanitizePreferences(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_EXPLORE_PREFERENCES };
  }
}

export function savePreferencesLocal(prefs: UserExplorePreferences): void {
  try {
    window.localStorage.setItem(EXPLORE_PREFS_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Ignore storage quota or restricted mode failures
  }
}
