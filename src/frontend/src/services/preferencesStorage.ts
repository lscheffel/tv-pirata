import {
  MediaBadgeAction,
  ProviderBadgeAction,
  UserExplorePreferences,
} from "../types";

export const EXPLORE_PREFS_STORAGE_KEY = "tv_pirata_explore_prefs_v1";

export const DEFAULT_EXPLORE_PREFERENCES: UserExplorePreferences = {
  schema_version: 1,
  badge_provider_action: "filter_provider",
  badge_media_action: "open_sources_modal",
  auto_apply_filters: false,
  show_all_genres: false,
  filter_panel_expanded: false,
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

  return {
    schema_version: 1,
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
