"""Entity Resolution and Data Provenance service for the Audiovisual Discovery Core (ADR-008)."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from src.backend.models.catalog_domain import (
    DataProvenance,
    ExternalIdentifier,
    GenreRecord,
    MediaWork,
    PersonRecord,
    ReleaseCalendarEvent,
    StreamingAvailability,
    WorkCredit,
    WorkGenreLink,
    WorkRelation,
)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class EntityResolutionService:
    """Resolves multi-source audiovisual records into canonical MediaWork entities.

    Enforces confidence-tiered matching, prevents destructive merges of remakes or
    homonyms, and preserves field-level data provenance across providers.
    """

    GENRE_NORMALIZATION_MAP: dict[str, tuple[str, str]] = {
        "sci-fi": ("sci-fi", "Ficção Científica"),
        "science fiction": ("sci-fi", "Ficção Científica"),
        "science-fiction": ("sci-fi", "Ficção Científica"),
        "ficcao cientifica": ("sci-fi", "Ficção Científica"),
        "ficção científica": ("sci-fi", "Ficção Científica"),
        "sci-fi & fantasy": ("sci-fi", "Ficção Científica"),
        "fantasy": ("fantasy", "Fantasia"),
        "fantasia": ("fantasy", "Fantasia"),
        "drama": ("drama", "Drama"),
        "thriller": ("thriller", "Suspense"),
        "suspense": ("thriller", "Suspense"),
        "crime": ("crime", "Crime & Investigação"),
        "policial": ("crime", "Crime & Investigação"),
        "mystery": ("mystery", "Mistério"),
        "misterio": ("mystery", "Mistério"),
        "mistério": ("mystery", "Mistério"),
        "action": ("action", "Ação"),
        "acao": ("action", "Ação"),
        "ação": ("action", "Ação"),
        "action & adventure": ("action", "Ação"),
        "adventure": ("adventure", "Aventura"),
        "aventura": ("adventure", "Aventura"),
        "comedy": ("comedy", "Comédia"),
        "comedia": ("comedy", "Comédia"),
        "comédia": ("comedy", "Comédia"),
        "documentary": ("documentary", "Documentário"),
        "documentario": ("documentary", "Documentário"),
        "documentário": ("documentary", "Documentário"),
        "animation": ("animation", "Animação"),
        "animacao": ("animation", "Animação"),
        "animação": ("animation", "Animação"),
        "horror": ("horror", "Terror"),
        "terror": ("horror", "Terror"),
        "history": ("history", "História"),
        "historia": ("history", "História"),
        "história": ("history", "História"),
        "war": ("war", "Guerra & Política"),
        "war & politics": ("war", "Guerra & Política"),
        "biography": ("biography", "Biografia"),
        "biografia": ("biography", "Biografia"),
        "romance": ("romance", "Romance"),
        "family": ("family", "Família"),
        "music": ("music", "Música"),
    }

    @staticmethod
    def normalize_title_key(title: str) -> str:
        """Normalize a title for comparison by stripping accents, punctuation, and case."""
        if not title:
            return ""
        nfkd = unicodedata.normalize("NFKD", title.strip().lower())
        ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
        cleaned = re.sub(r"[^a-z0-9\s]", " ", ascii_str)
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def normalize_imdb_id(raw_id: Optional[str]) -> Optional[str]:
        """Normalize an IMDb identifier to 'ttXXXXXXX' format."""
        if not raw_id:
            return None
        clean = str(raw_id).strip().lower()
        if not clean or clean == "0":
            return None
        digits = clean[2:] if clean.startswith("tt") else clean
        if not digits.isdigit():
            return None
        return f"tt{digits.zfill(7)}"

    @classmethod
    def resolve_and_upsert_work(
        cls,
        session: Session,
        payload: dict[str, Any],
        source_provider: str = "tmdb",
    ) -> tuple[MediaWork, str]:
        """Resolve an incoming metadata payload into a canonical MediaWork.

        Returns a tuple of (MediaWork, match_confidence) where match_confidence is
        one of 'deterministic', 'high', or 'created_new'.
        """
        work_type = payload.get("work_type", "movie")
        title = (payload.get("title") or "").strip()
        original_title = (payload.get("original_title") or title).strip()
        release_date = payload.get("release_date")
        release_year = payload.get("release_year")
        if not release_year and release_date and len(str(release_date)) >= 4:
            try:
                release_year = int(str(release_date)[:4])
            except ValueError:
                release_year = None

        imdb_id = cls.normalize_imdb_id(payload.get("imdb_id"))
        tmdb_id = payload.get("tmdb_id")
        tvmaze_id = payload.get("tvmaze_id")
        wikidata_id = payload.get("wikidata_id")

        matched_work: Optional[MediaWork] = None
        match_confidence = "created_new"

        # ------------------------------------------------------------------
        # TIER 1: Deterministic External Identifier Resolution
        # ------------------------------------------------------------------
        if imdb_id:
            matched_work = session.exec(
                select(MediaWork).where(MediaWork.imdb_id == imdb_id)
            ).first()
            if not matched_work:
                ext = session.exec(
                    select(ExternalIdentifier).where(
                        ExternalIdentifier.provider == "imdb",
                        ExternalIdentifier.external_id == imdb_id,
                    )
                ).first()
                if ext:
                    matched_work = session.get(MediaWork, ext.work_id)
            if matched_work:
                match_confidence = "deterministic"

        if not matched_work and tmdb_id:
            provider_key = f"tmdb_{work_type}"
            ext = session.exec(
                select(ExternalIdentifier).where(
                    ExternalIdentifier.provider == provider_key,
                    ExternalIdentifier.external_id == str(tmdb_id),
                )
            ).first()
            if ext:
                matched_work = session.get(MediaWork, ext.work_id)
            else:
                matched_work = session.exec(
                    select(MediaWork).where(
                        MediaWork.tmdb_id == int(tmdb_id),
                        MediaWork.work_type == work_type,
                    )
                ).first()
            if matched_work:
                match_confidence = "deterministic"

        if not matched_work and tvmaze_id:
            matched_work = session.exec(
                select(MediaWork).where(MediaWork.tvmaze_id == int(tvmaze_id))
            ).first()
            if matched_work:
                match_confidence = "deterministic"

        if not matched_work and wikidata_id:
            matched_work = session.exec(
                select(MediaWork).where(MediaWork.wikidata_id == str(wikidata_id))
            ).first()
            if matched_work:
                match_confidence = "deterministic"

        # ------------------------------------------------------------------
        # TIER 2: High-Confidence Composite Match (Anti-Collision Protected)
        # ------------------------------------------------------------------
        homonym_or_remake_candidates: list[MediaWork] = []
        if not matched_work and title:
            norm_target = cls.normalize_title_key(title)
            norm_orig = cls.normalize_title_key(original_title)
            candidates = session.exec(
                select(MediaWork).where(MediaWork.work_type == work_type)
            ).all()

            for cand in candidates:
                cand_norm = cls.normalize_title_key(cand.title)
                cand_orig = cls.normalize_title_key(cand.original_title or "")
                title_matches = norm_target in (cand_norm, cand_orig) or (
                    norm_orig and norm_orig in (cand_norm, cand_orig)
                )
                if not title_matches:
                    continue

                # Check for explicit external ID conflict (different IMDb IDs = distinct works!)
                if imdb_id and cand.imdb_id and imdb_id != cand.imdb_id:
                    homonym_or_remake_candidates.append(cand)
                    continue

                # Check release year alignment
                if release_year and cand.release_year:
                    year_diff = abs(int(release_year) - int(cand.release_year))
                    tolerance = 0 if work_type == "movie" else 1
                    if year_diff <= tolerance:
                        matched_work = cand
                        match_confidence = "high"
                        break
                    else:
                        homonym_or_remake_candidates.append(cand)
                elif not release_year and not cand.release_year:
                    matched_work = cand
                    match_confidence = "high"
                    break

        # ------------------------------------------------------------------
        # Upsert Canonical MediaWork
        # ------------------------------------------------------------------
        now = utc_now()
        incoming_rating = float(payload.get("rating") or payload.get("canonical_rating") or 0.0)
        incoming_votes = int(payload.get("vote_count") or 0)
        rating_provider = payload.get("rating_source") or source_provider

        if not matched_work:
            breakdown = {}
            if incoming_rating > 0:
                breakdown[rating_provider] = {
                    "rating": round(incoming_rating, 1),
                    "votes": incoming_votes,
                }
            if payload.get("ratings_breakdown") and isinstance(payload["ratings_breakdown"], dict):
                breakdown.update(payload["ratings_breakdown"])

            matched_work = MediaWork(
                work_type=work_type,
                title=title or "Sem Título",
                original_title=original_title or title,
                overview=payload.get("overview") or "",
                tagline=payload.get("tagline"),
                release_date=release_date,
                end_date=payload.get("end_date"),
                release_year=release_year,
                runtime_minutes=payload.get("runtime_minutes"),
                status=payload.get("status") or "Released",
                origin_country=payload.get("origin_country") or "US",
                original_language=payload.get("original_language") or "en",
                poster_url=payload.get("poster_url"),
                backdrop_url=payload.get("backdrop_url"),
                canonical_rating=round(incoming_rating, 1),
                rating_source=rating_provider,
                ratings_breakdown=json.dumps(breakdown),
                popularity_score=float(payload.get("popularity_score") or incoming_rating * 10),
                vote_count=incoming_votes,
                seasons_count=int(payload.get("seasons_count") or 0),
                episodes_count=int(payload.get("episodes_count") or 0),
                network_or_studio=payload.get("network_or_studio"),
                collection_name=payload.get("collection_name"),
                imdb_id=imdb_id,
                tmdb_id=int(tmdb_id) if tmdb_id else None,
                tvmaze_id=int(tvmaze_id) if tvmaze_id else None,
                wikidata_id=wikidata_id,
                created_at=now,
                updated_at=now,
            )
            session.add(matched_work)
            session.flush()
        else:
            # Non-destructive enrichment: fill missing fields or upgrade completeness
            if imdb_id and not matched_work.imdb_id:
                matched_work.imdb_id = imdb_id
            if tmdb_id and not matched_work.tmdb_id:
                matched_work.tmdb_id = int(tmdb_id)
            if tvmaze_id and not matched_work.tvmaze_id:
                matched_work.tvmaze_id = int(tvmaze_id)
            if wikidata_id and not matched_work.wikidata_id:
                matched_work.wikidata_id = str(wikidata_id)

            if payload.get("overview") and (
                not matched_work.overview
                or len(str(payload["overview"])) > len(matched_work.overview)
            ):
                matched_work.overview = str(payload["overview"])

            if payload.get("poster_url") and not matched_work.poster_url:
                matched_work.poster_url = payload["poster_url"]
            if payload.get("backdrop_url") and not matched_work.backdrop_url:
                matched_work.backdrop_url = payload["backdrop_url"]
            if payload.get("runtime_minutes") and not matched_work.runtime_minutes:
                matched_work.runtime_minutes = int(payload["runtime_minutes"])
            if release_date and not matched_work.release_date:
                matched_work.release_date = release_date
            if release_year and not matched_work.release_year:
                matched_work.release_year = int(release_year)
            if payload.get("network_or_studio") and not matched_work.network_or_studio:
                matched_work.network_or_studio = payload["network_or_studio"]
            if payload.get("collection_name") and not matched_work.collection_name:
                matched_work.collection_name = payload["collection_name"]
            if (
                payload.get("seasons_count")
                and int(payload["seasons_count"]) > matched_work.seasons_count
            ):
                matched_work.seasons_count = int(payload["seasons_count"])
            if (
                payload.get("episodes_count")
                and int(payload["episodes_count"]) > matched_work.episodes_count
            ):
                matched_work.episodes_count = int(payload["episodes_count"])

            # Preserve per-source rating in ratings_breakdown without overwriting
            try:
                breakdown = json.loads(matched_work.ratings_breakdown or "{}")
            except Exception:
                breakdown = {}

            if incoming_rating > 0:
                breakdown[rating_provider] = {
                    "rating": round(incoming_rating, 1),
                    "votes": incoming_votes,
                }
            if payload.get("ratings_breakdown") and isinstance(payload["ratings_breakdown"], dict):
                breakdown.update(payload["ratings_breakdown"])

            matched_work.ratings_breakdown = json.dumps(breakdown)

            # Documented canonical rating priority: IMDb > TMDB > TVMaze > fallback
            if "imdb" in breakdown and breakdown["imdb"].get("rating", 0) > 0:
                matched_work.canonical_rating = float(breakdown["imdb"]["rating"])
                matched_work.rating_source = "imdb"
            elif incoming_rating > 0 and matched_work.canonical_rating == 0.0:
                matched_work.canonical_rating = round(incoming_rating, 1)
                matched_work.rating_source = rating_provider

            matched_work.updated_at = now
            session.add(matched_work)
            session.flush()

        # ------------------------------------------------------------------
        # Register External Identifiers
        # ------------------------------------------------------------------
        assert matched_work.id is not None
        ext_Confidence = "deterministic" if match_confidence != "high" else "high"
        if imdb_id:
            cls._register_external_id(session, matched_work.id, "imdb", imdb_id, ext_Confidence)
        if tmdb_id:
            cls._register_external_id(
                session, matched_work.id, f"tmdb_{work_type}", str(tmdb_id), ext_Confidence
            )
        if tvmaze_id:
            cls._register_external_id(
                session, matched_work.id, "tvmaze", str(tvmaze_id), ext_Confidence
            )
        if wikidata_id:
            cls._register_external_id(
                session, matched_work.id, "wikidata", str(wikidata_id), ext_Confidence
            )

        # ------------------------------------------------------------------
        # Record Field-Level Data Provenance
        # ------------------------------------------------------------------
        ext_ref = imdb_id or str(tmdb_id or tvmaze_id or wikidata_id or matched_work.id)
        tracked_fields = {
            "title": title,
            "original_title": original_title,
            "release_date": release_date,
            "rating": str(incoming_rating) if incoming_rating > 0 else None,
            "runtime_minutes": str(payload["runtime_minutes"])
            if payload.get("runtime_minutes")
            else None,
            "status": payload.get("status"),
        }
        for fname, fval in tracked_fields.items():
            if fval:
                cls._record_provenance(
                    session=session,
                    work_id=matched_work.id,
                    source_provider=source_provider,
                    external_id=ext_ref,
                    field_name=fname,
                    field_value=str(fval),
                    selection_reason="canonical_priority"
                    if match_confidence == "created_new"
                    else "corroborated_federation",
                )

        # ------------------------------------------------------------------
        # Link Genres
        # ------------------------------------------------------------------
        raw_genres = payload.get("genres") or []
        if isinstance(raw_genres, str):
            raw_genres = [g.strip() for g in raw_genres.split(",") if g.strip()]
        cls._sync_genres(session, matched_work, raw_genres)

        # ------------------------------------------------------------------
        # Link Credits (Directors, Creators, Writers, Cast)
        # ------------------------------------------------------------------
        for credit_item in payload.get("credits", []):
            cls._upsert_credit(session, matched_work.id, credit_item)

        # ------------------------------------------------------------------
        # Link Streaming Availability
        # ------------------------------------------------------------------
        for avail_item in payload.get("availabilities", []):
            cls._upsert_availability(session, matched_work.id, avail_item, source_provider)

        # ------------------------------------------------------------------
        # Link Release Calendar Events
        # ------------------------------------------------------------------
        for cal_item in payload.get("calendar_events", []):
            cls._upsert_calendar_event(session, matched_work.id, cal_item, source_provider)

        # ------------------------------------------------------------------
        # Automatically link Remake / Homonym Relations if detected
        # ------------------------------------------------------------------
        for prior_cand in homonym_or_remake_candidates:
            if prior_cand.id and prior_cand.id != matched_work.id:
                rel_type = (
                    "remake"
                    if prior_cand.release_year
                    and matched_work.release_year
                    and prior_cand.release_year != matched_work.release_year
                    else "related"
                )
                cls.link_related_works(
                    session,
                    source_work_id=matched_work.id,
                    target_work_id=prior_cand.id,
                    relation_type=rel_type,
                    notes=(
                        f"Distinguished by year "
                        f"({matched_work.release_year} vs {prior_cand.release_year})"
                    ),
                )

        session.flush()
        return matched_work, match_confidence

    @classmethod
    def _register_external_id(
        cls,
        session: Session,
        work_id: int,
        provider: str,
        external_id: str,
        confidence: str = "deterministic",
    ) -> None:
        existing = session.exec(
            select(ExternalIdentifier).where(
                ExternalIdentifier.provider == provider,
                ExternalIdentifier.external_id == external_id,
            )
        ).first()
        if not existing:
            session.add(
                ExternalIdentifier(
                    work_id=work_id,
                    provider=provider,
                    external_id=external_id,
                    confidence=confidence,
                )
            )

    @classmethod
    def _record_provenance(
        cls,
        session: Session,
        work_id: int,
        source_provider: str,
        external_id: str,
        field_name: str,
        field_value: str,
        selection_reason: str,
    ) -> None:
        existing = session.exec(
            select(DataProvenance).where(
                DataProvenance.work_id == work_id,
                DataProvenance.source_provider == source_provider,
                DataProvenance.field_name == field_name,
            )
        ).first()
        if existing:
            existing.field_value = field_value
            existing.fetched_at = utc_now()
            session.add(existing)
        else:
            session.add(
                DataProvenance(
                    work_id=work_id,
                    source_provider=source_provider,
                    external_id=external_id,
                    field_name=field_name,
                    field_value=field_value,
                    selection_reason=selection_reason,
                )
            )

    @classmethod
    def _sync_genres(cls, session: Session, work: MediaWork, raw_genres: list[str]) -> None:
        assert work.id is not None
        canonical_names: list[str] = []
        for g in raw_genres:
            key = g.strip().lower()
            if not key:
                continue
            slug, display_name = cls.GENRE_NORMALIZATION_MAP.get(
                key, (re.sub(r"[^a-z0-9]+", "-", key).strip("-"), g.strip())
            )
            if not slug:
                continue

            genre_rec = session.exec(select(GenreRecord).where(GenreRecord.slug == slug)).first()
            if not genre_rec:
                genre_rec = GenreRecord(slug=slug, name=display_name)
                session.add(genre_rec)
                session.flush()

            assert genre_rec.id is not None
            link = session.exec(
                select(WorkGenreLink).where(
                    WorkGenreLink.work_id == work.id,
                    WorkGenreLink.genre_id == genre_rec.id,
                )
            ).first()
            if not link:
                session.add(WorkGenreLink(work_id=work.id, genre_id=genre_rec.id))

            if display_name not in canonical_names:
                canonical_names.append(display_name)

        if canonical_names:
            existing_names = [x.strip() for x in (work.genres_csv or "").split(",") if x.strip()]
            merged = list(dict.fromkeys(existing_names + canonical_names))
            work.genres_csv = ", ".join(merged)
            session.add(work)

    @classmethod
    def _upsert_credit(cls, session: Session, work_id: int, credit_data: dict[str, Any]) -> None:
        name = (credit_data.get("name") or "").strip()
        if not name:
            return
        role_type = credit_data.get("role_type", "actor")
        department = (
            "Directing"
            if role_type == "director"
            else ("Writing" if role_type in ("writer", "creator") else "Acting")
        )

        person = session.exec(select(PersonRecord).where(PersonRecord.name == name)).first()
        if not person:
            person = PersonRecord(
                name=name,
                imdb_id=credit_data.get("imdb_id"),
                tmdb_id=credit_data.get("tmdb_id"),
                tvmaze_id=credit_data.get("tvmaze_id"),
                known_for_department=credit_data.get("department") or department,
                profile_url=credit_data.get("profile_url"),
                biography=credit_data.get("biography") or "",
                birth_year=credit_data.get("birth_year"),
                country=credit_data.get("country"),
            )
            session.add(person)
            session.flush()

        assert person.id is not None
        existing_credit = session.exec(
            select(WorkCredit).where(
                WorkCredit.work_id == work_id,
                WorkCredit.person_id == person.id,
                WorkCredit.role_type == role_type,
            )
        ).first()
        if not existing_credit:
            session.add(
                WorkCredit(
                    work_id=work_id,
                    person_id=person.id,
                    role_type=role_type,
                    character_name=credit_data.get("character_name"),
                    billing_order=int(credit_data.get("billing_order") or 0),
                )
            )

    @classmethod
    def _upsert_availability(
        cls,
        session: Session,
        work_id: int,
        avail_data: dict[str, Any],
        default_source: str,
    ) -> None:
        provider_name = (avail_data.get("provider_name") or "").strip()
        if not provider_name:
            return
        territory = avail_data.get("territory") or "BR"
        monetization = avail_data.get("monetization_type") or "flatrate"

        existing = session.exec(
            select(StreamingAvailability).where(
                StreamingAvailability.work_id == work_id,
                StreamingAvailability.provider_name == provider_name,
                StreamingAvailability.territory == territory,
            )
        ).first()
        if existing:
            existing.monetization_type = monetization
            existing.updated_at = utc_now()
            session.add(existing)
        else:
            session.add(
                StreamingAvailability(
                    work_id=work_id,
                    provider_name=provider_name,
                    territory=territory,
                    monetization_type=monetization,
                    link_url=avail_data.get("link_url"),
                    source_provider=avail_data.get("source_provider") or default_source,
                )
            )

    @classmethod
    def _upsert_calendar_event(
        cls,
        session: Session,
        work_id: int,
        cal_data: dict[str, Any],
        default_source: str,
    ) -> None:
        event_date = (cal_data.get("event_date") or "").strip()
        event_type = cal_data.get("event_type") or "streaming_premiere"
        if not event_date:
            return

        existing = session.exec(
            select(ReleaseCalendarEvent).where(
                ReleaseCalendarEvent.work_id == work_id,
                ReleaseCalendarEvent.event_type == event_type,
                ReleaseCalendarEvent.event_date == event_date,
            )
        ).first()
        if not existing:
            session.add(
                ReleaseCalendarEvent(
                    work_id=work_id,
                    event_type=event_type,
                    event_date=event_date,
                    confidence_level=cal_data.get("confidence_level") or "confirmed",
                    territory=cal_data.get("territory") or "GLOBAL",
                    platform_or_network=cal_data.get("platform_or_network"),
                    season_number=cal_data.get("season_number"),
                    episode_number=cal_data.get("episode_number"),
                    event_title=cal_data.get("event_title") or "",
                    source_provider=cal_data.get("source_provider") or default_source,
                )
            )

    @classmethod
    def link_related_works(
        cls,
        session: Session,
        source_work_id: int,
        target_work_id: int,
        relation_type: str,
        notes: Optional[str] = None,
    ) -> None:
        """Create an explicit directed relationship between two MediaWork entities."""
        if source_work_id == target_work_id:
            return
        existing = session.exec(
            select(WorkRelation).where(
                WorkRelation.source_work_id == source_work_id,
                WorkRelation.target_work_id == target_work_id,
                WorkRelation.relation_type == relation_type,
            )
        ).first()
        if not existing:
            session.add(
                WorkRelation(
                    source_work_id=source_work_id,
                    target_work_id=target_work_id,
                    relation_type=relation_type,
                    notes=notes,
                )
            )
