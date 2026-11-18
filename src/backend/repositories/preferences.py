"""Persistence repository for user explore and interaction preferences."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

PREFERENCES_SYNC_KEY = "user_explore_preferences_v1"

ProviderBadgeAction = Literal["filter_provider", "open_details", "open_provider_info"]
MediaBadgeAction = Literal["open_sources_modal", "filter_has_media", "open_details"]


class UserExplorePreferences(BaseModel):
    """Validated user preferences persisted in mainstream.db sync_state."""

    schema_version: Literal[1] = 1
    badge_provider_action: ProviderBadgeAction = "filter_provider"
    badge_media_action: MediaBadgeAction = "open_sources_modal"
    auto_apply_filters: bool = False
    show_all_genres: bool = False
    filter_panel_expanded: bool = False


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
        """Load stored preferences or return canonical defaults safely."""
        try:
            cls._ensure_sync_state_table(session)
            row = session.exec(
                text("SELECT value FROM sync_state WHERE key = :key"),
                params={"key": PREFERENCES_SYNC_KEY},
            ).first()
            if row and row[0]:
                raw = json.loads(row[0])
                return UserExplorePreferences.model_validate(raw)
        except Exception:
            pass
        return UserExplorePreferences()

    @classmethod
    def save_preferences(
        cls, session: Session, prefs: UserExplorePreferences
    ) -> UserExplorePreferences:
        """Persist validated preferences to mainstream.db sync_state."""
        cls._ensure_sync_state_table(session)
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
