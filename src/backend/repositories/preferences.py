"""Persistence repository for user explore, feed and interaction preferences (v1 -> v2)."""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlmodel import Session

from src.backend.core.content_filters import ForeignTitlesMode, MoodFilterMode

PREFERENCES_SYNC_KEY = "user_explore_preferences_v1"

ProviderBadgeAction = Literal["filter_provider", "open_details", "open_provider_info"]
MediaBadgeAction = Literal["open_sources_modal", "filter_has_media", "open_details"]
SmartListSort = Literal["balanced", "rating", "popularity", "newest", "p2p_recent"]


class SmartListConfig(BaseModel):
    """Configuration for a single curated smart list on the Discover showcase."""

    id: str
    title: str
    category: str
    enabled: bool = True
    order: int = 0
    limit: int = Field(default=100, ge=20, le=100)
    sort_by: SmartListSort = "balanced"
    only_with_media: bool = False
    variance_override: Optional[int] = Field(default=None, ge=0, le=100)


class CustomShortcutConfig(BaseModel):
    """User-pinned FilterSnapshot shortcut displayed on the Discover quick-intent bar."""

    id: str
    label: str
    filters: dict[str, Any] = Field(default_factory=dict)
    pinned: bool = True


AVAILABLE_SMART_LIST_CATALOG: list[dict[str, Any]] = [
    {
        "id": "trending_now",
        "title": "Em Alta Agora (2024–2026)",
        "category": "trending_now",
        "sort_by": "balanced",
    },
    {
        "id": "p2p_fresh",
        "title": "Recém-Chegados com Mídia (P2P)",
        "category": "p2p_fresh",
        "sort_by": "p2p_recent",
    },
    {
        "id": "acclaimed_movies",
        "title": "Filmes Aclamados (≥ 7.8)",
        "category": "acclaimed_movies",
        "sort_by": "rating",
    },
    {
        "id": "running_series",
        "title": "Séries Imperdíveis em Exibição",
        "category": "running_series",
        "sort_by": "popularity",
    },
    {
        "id": "scifi_fantasy_thriller",
        "title": "Sci-Fi, Fantasia & Suspense",
        "category": "scifi_fantasy_thriller",
        "sort_by": "balanced",
    },
    {
        "id": "crime_mystery",
        "title": "Crime, Investigação & Mistério",
        "category": "crime_mystery",
        "sort_by": "balanced",
    },
    {
        "id": "anime_animation_docs",
        "title": "Animes, Animações & Docs",
        "category": "anime_animation_docs",
        "sort_by": "rating",
    },
    {
        "id": "because_you_watched",
        "title": "Porque Você Assiste / Curtiu",
        "category": "because_you_watched",
        "sort_by": "balanced",
    },
    {
        "id": "on_your_radar",
        "title": "No Seu Radar (Seus Gêneros)",
        "category": "on_your_radar",
        "sort_by": "balanced",
    },
    {
        "id": "hidden_gems_for_you",
        "title": "Joias Ocultas para Você",
        "category": "hidden_gems_for_you",
        "sort_by": "rating",
    },
    # Extra optional categories selectable in Settings
    {
        "id": "horror_supernatural",
        "title": "Terror & Sobrenatural",
        "category": "horror_supernatural",
        "sort_by": "balanced",
    },
    {
        "id": "action_adventure",
        "title": "Ação & Aventura",
        "category": "action_adventure",
        "sort_by": "popularity",
    },
    {
        "id": "miniseries_fast",
        "title": "Minisséries Para Maratonar",
        "category": "miniseries_fast",
        "sort_by": "rating",
    },
    {
        "id": "classics_masterpieces",
        "title": "Clássicos Essenciais (≥ 8.4)",
        "category": "classics_masterpieces",
        "sort_by": "rating",
    },
    {
        "id": "releases_2026",
        "title": "Lançamentos & Destaques 2026",
        "category": "releases_2026",
        "sort_by": "newest",
    },
    {
        "id": "comedy_sitcoms",
        "title": "Comédias & Sitcoms",
        "category": "comedy_sitcoms",
        "sort_by": "balanced",
    },
]


def default_smart_lists_v2() -> list[SmartListConfig]:
    """Return the default 10 active Smart Lists (7 General + 3 Personalized)."""
    return [
        SmartListConfig(
            id=item["id"],
            title=item["title"],
            category=item["category"],
            enabled=(idx < 10),
            order=idx,
            limit=100,
            sort_by=item["sort_by"],
            only_with_media=False,
        )
        for idx, item in enumerate(AVAILABLE_SMART_LIST_CATALOG)
    ]


class UserExplorePreferences(BaseModel):
    """Validated user preferences persisted in mainstream.db sync_state (v1 -> v2)."""

    schema_version: Literal[1, 2] = 2
    badge_provider_action: ProviderBadgeAction = "filter_provider"
    badge_media_action: MediaBadgeAction = "open_sources_modal"
    auto_apply_filters: bool = False
    show_all_genres: bool = False
    filter_panel_expanded: bool = False
    discovery_variance_pct: int = Field(default=45, ge=0, le=100)
    hero_auto_rotate: bool = True
    hero_interval_sec: int = Field(default=12, ge=5, le=60)
    impression_ttl_hours: int = Field(default=48, ge=12, le=168)
    foreign_titles_mode: ForeignTitlesMode = "off"
    parental_control_enabled: bool = True
    mood_mode: MoodFilterMode = "all"
    smart_lists: list[SmartListConfig] = Field(default_factory=default_smart_lists_v2)
    hidden_builtin_shortcuts: list[str] = Field(default_factory=list)
    custom_shortcuts: list[CustomShortcutConfig] = Field(default_factory=list)


class ExplorePreferencesRepository:
    """Reads and stores UserExplorePreferences inside data/mainstream.db sync_state."""

    @staticmethod
    def _ensure_sync_state_table(session: Session) -> None:
        session.exec(
            text(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    @classmethod
    def get_preferences(cls, session: Session) -> UserExplorePreferences:
        """Load stored preferences or return canonical defaults safely (migrating v1 -> v2)."""
        try:
            cls._ensure_sync_state_table(session)
            row = session.exec(
                text("SELECT value FROM sync_state WHERE key = :key"),
                params={"key": PREFERENCES_SYNC_KEY},
            ).first()
            if row and row[0]:
                raw = json.loads(row[0])
                prefs = UserExplorePreferences.model_validate(raw)
                if not prefs.smart_lists:
                    prefs.smart_lists = default_smart_lists_v2()
                return prefs
        except Exception:
            pass
        return UserExplorePreferences()

    @classmethod
    def save_preferences(
        cls, session: Session, prefs: UserExplorePreferences
    ) -> UserExplorePreferences:
        """Persist validated preferences to mainstream.db sync_state."""
        cls._ensure_sync_state_table(session)
        if not prefs.smart_lists:
            prefs.smart_lists = default_smart_lists_v2()
        prefs.schema_version = 2
        payload = prefs.model_dump_json()
        session.exec(
            text(
                """
                INSERT INTO sync_state (key, value, updated_at)
                VALUES (:key, :val, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            params={"key": PREFERENCES_SYNC_KEY, "val": payload},
        )
        session.commit()
        return prefs
