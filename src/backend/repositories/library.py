"""Library and Watchlist repository managing transactional database operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, col, select

from src.backend.models.db import (
    CollectionRecord,
    EpisodeRecord,
    EpisodeWatchRecord,
    LocalMediaRecord,
    SeasonRecord,
    ShowRecord,
    TagRecord,
)
from src.backend.models.unified import UnifiedShow


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class LibraryRepository:
    """Manages transactional persistence for shows, watches, media and collections."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_from_unified(
        self,
        unified: UnifiedShow,
        user_status: str = "plan_to_watch",
    ) -> ShowRecord:
        """Atomically import or update a UnifiedShow into the relational database."""
        statement = select(ShowRecord).where(ShowRecord.tmdb_id == unified.id)
        show = self.session.exec(statement).first()

        genres_str = ", ".join(unified.genres) if unified.genres else ""

        if not show:
            now = utc_now()
            # Create new show entry
            show = ShowRecord(
                tmdb_id=unified.id,
                tvmaze_id=unified.tvmaze_id,
                imdb_id=unified.imdb_id,
                title=unified.title,
                original_title=unified.original_title,
                overview=unified.overview,
                poster_url=unified.poster_url,
                backdrop_url=unified.backdrop_url,
                rating=unified.rating,
                genres=genres_str,
                first_air_date=unified.first_air_date,
                status=unified.status,
                user_status=user_status,
                created_at=now,
                updated_at=now,
            )
            self.session.add(show)
            self.session.flush()

            # Create seasons and episodes
            for s in unified.seasons:
                season = SeasonRecord(
                    show_id=show.id,
                    season_number=s.season_number,
                    name=s.name or f"Temporada {s.season_number}",
                    overview=s.overview,
                    poster_url=s.poster_url,
                    episode_count=s.episode_count or len(s.episodes),
                )
                self.session.add(season)
                self.session.flush()

                # If full episode list is provided
                if s.episodes:
                    for ep in s.episodes:
                        episode = EpisodeRecord(
                            season_id=season.id,
                            episode_number=ep.episode_number,
                            title=ep.title,
                            overview=ep.overview,
                            air_date=ep.air_date,
                            rating=ep.rating,
                        )
                        self.session.add(episode)
                        self.session.flush()

                        watch = EpisodeWatchRecord(
                            episode_id=episode.id,
                            is_watched=False,
                        )
                        self.session.add(watch)
                else:
                    # Generate stub episodes for tracking based on episode_count
                    for ep_num in range(1, (s.episode_count or 0) + 1):
                        episode = EpisodeRecord(
                            season_id=season.id,
                            episode_number=ep_num,
                            title=f"Episódio {ep_num}",
                        )
                        self.session.add(episode)
                        self.session.flush()

                        watch = EpisodeWatchRecord(
                            episode_id=episode.id,
                            is_watched=False,
                        )
                        self.session.add(watch)
        else:
            # Update mutable metadata preserving user state
            show.overview = unified.overview
            show.rating = unified.rating
            show.poster_url = unified.poster_url or show.poster_url
            show.backdrop_url = unified.backdrop_url or show.backdrop_url
            show.status = unified.status or show.status
            show.updated_at = utc_now()
            self.session.add(show)

        self.session.flush()
        return show

    def get_show_by_id(self, show_id: int) -> Optional[ShowRecord]:
        """Fetch show by internal database ID."""
        return self.session.get(ShowRecord, show_id)

    def get_show_by_tmdb_id(self, tmdb_id: int) -> Optional[ShowRecord]:
        """Fetch show by TMDB ID."""
        return self.session.exec(select(ShowRecord).where(ShowRecord.tmdb_id == tmdb_id)).first()

    def list_shows(self, user_status: Optional[str] = None) -> list[ShowRecord]:
        """List shows in user library, optionally filtered by status."""
        query = select(ShowRecord)
        if user_status:
            query = query.where(ShowRecord.user_status == user_status)
        query = query.order_by(col(ShowRecord.title).asc())
        return list(self.session.exec(query).all())

    def update_show_status(self, show_id: int, new_status: str) -> Optional[ShowRecord]:
        """Update user categorization status (e.g. watching, completed)."""
        show = self.get_show_by_id(show_id)
        if show:
            show.user_status = new_status
            show.updated_at = utc_now()
            self.session.add(show)
            self.session.flush()
        return show

    def delete_show(self, show_id: int) -> bool:
        """Remove show from personal library."""
        show = self.get_show_by_id(show_id)
        if not show:
            return False
        self.session.delete(show)
        self.session.flush()
        return True

    def toggle_episode_watch(
        self,
        episode_id: int,
        force_state: Optional[bool] = None,
    ) -> EpisodeWatchRecord:
        """Toggle or set watched status for an episode."""
        watch = self.session.exec(
            select(EpisodeWatchRecord).where(EpisodeWatchRecord.episode_id == episode_id)
        ).first()

        if not watch:
            watch = EpisodeWatchRecord(episode_id=episode_id)
            self.session.add(watch)

        if force_state is not None:
            watch.is_watched = force_state
        else:
            watch.is_watched = not watch.is_watched

        watch.watched_at = utc_now() if watch.is_watched else None
        self.session.add(watch)
        self.session.flush()
        return watch

    def watch_all_in_season(self, season_id: int, is_watched: bool = True) -> int:
        """Mark all episodes in a season as watched or unwatched."""
        episodes = self.session.exec(
            select(EpisodeRecord).where(EpisodeRecord.season_id == season_id)
        ).all()

        count = 0
        now = utc_now() if is_watched else None
        for ep in episodes:
            watch = self.session.exec(
                select(EpisodeWatchRecord).where(EpisodeWatchRecord.episode_id == ep.id)
            ).first()
            if not watch:
                watch = EpisodeWatchRecord(episode_id=ep.id)
                self.session.add(watch)
            watch.is_watched = is_watched
            watch.watched_at = now
            self.session.add(watch)
            count += 1

        self.session.flush()
        return count

    def get_show_progress(self, show_id: int) -> dict:
        """Calculate total and watched episode counts for a show."""
        seasons = self.session.exec(
            select(SeasonRecord).where(SeasonRecord.show_id == show_id)
        ).all()

        total_episodes = 0
        watched_episodes = 0

        for season in seasons:
            # Exclude specials (season 0) from default progress calculation
            if season.season_number == 0:
                continue

            episodes = self.session.exec(
                select(EpisodeRecord).where(EpisodeRecord.season_id == season.id)
            ).all()

            for ep in episodes:
                total_episodes += 1
                watch = self.session.exec(
                    select(EpisodeWatchRecord).where(EpisodeWatchRecord.episode_id == ep.id)
                ).first()
                if watch and watch.is_watched:
                    watched_episodes += 1

        progress_pct = (
            round((watched_episodes / total_episodes) * 100, 1) if total_episodes > 0 else 0.0
        )

        return {
            "show_id": show_id,
            "total_episodes": total_episodes,
            "watched_episodes": watched_episodes,
            "progress_pct": progress_pct,
            "is_completed": (total_episodes > 0 and watched_episodes == total_episodes),
        }

    def set_local_media(
        self,
        episode_id: int,
        relative_path: str,
        is_available: bool = True,
    ) -> LocalMediaRecord:
        """Record or update physical SMB media availability for an episode."""
        media = self.session.exec(
            select(LocalMediaRecord).where(LocalMediaRecord.episode_id == episode_id)
        ).first()

        now = utc_now()
        if not media:
            media = LocalMediaRecord(
                episode_id=episode_id,
                relative_path=relative_path,
                is_available=is_available,
                last_seen_at=now,
            )
        else:
            media.relative_path = relative_path
            media.is_available = is_available
            media.last_seen_at = now

        self.session.add(media)
        self.session.flush()
        return media

    def create_tag(self, name: str, color: str = "#e50914") -> TagRecord:
        """Create a user classification tag."""
        tag = TagRecord(name=name.strip(), color=color)
        self.session.add(tag)
        self.session.flush()
        return tag

    def list_tags(self) -> list[TagRecord]:
        """List all available tags."""
        return list(self.session.exec(select(TagRecord).order_by(TagRecord.name)).all())

    def create_collection(
        self,
        name: str,
        description: str = "",
        filter_criteria: Optional[dict] = None,
    ) -> CollectionRecord:
        """Create a smart collection with JSON filter criteria."""
        criteria_json = json.dumps(filter_criteria or {})
        collection = CollectionRecord(
            name=name.strip(),
            description=description,
            filter_criteria=criteria_json,
            created_at=utc_now(),
        )
        self.session.add(collection)
        self.session.flush()
        return collection

    def list_collections(self) -> list[CollectionRecord]:
        """List all smart collections."""
        return list(
            self.session.exec(select(CollectionRecord).order_by(CollectionRecord.name)).all()
        )

    def query_smart_collection(self, collection_id: int) -> list[ShowRecord]:
        """Execute dynamic filter query for a smart collection."""
        collection = self.session.get(CollectionRecord, collection_id)
        if not collection:
            return []

        try:
            filters = json.loads(collection.filter_criteria)
        except Exception:
            filters = {}

        query = select(ShowRecord)

        if "user_status" in filters:
            query = query.where(ShowRecord.user_status == filters["user_status"])

        if "min_rating" in filters:
            query = query.where(ShowRecord.rating >= float(filters["min_rating"]))

        if "genre" in filters:
            query = query.where(col(ShowRecord.genres).contains(filters["genre"]))

        return list(self.session.exec(query).all())
