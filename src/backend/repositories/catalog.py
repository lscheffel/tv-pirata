"""Catalog repository for query operations and stats."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, col, func, or_, select

from src.backend.models.db import CatalogRelease, CatalogShow


class CatalogRepository:
    """Repository managing local EZTV catalog queries and statistics."""

    @staticmethod
    def list_shows(
        session: Session,
        search: Optional[str] = None,
        genre: Optional[str] = None,
        min_seeds: int = 0,
        sort_by: str = "seeds",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CatalogShow], int]:
        """Query catalog shows with filtering, sorting, and pagination."""
        query = select(CatalogShow)

        if min_seeds > 0:
            query = query.where(CatalogShow.max_seeds >= min_seeds)

        if search:
            search_pattern = f"%{search.strip().lower()}%"
            query = query.where(
                col(CatalogShow.title).ilike(search_pattern)
                | col(CatalogShow.imdb_id).ilike(search_pattern)
            )

        if genre:
            raw_tokens = [t.strip().lower() for t in genre.split(",") if t.strip()]
            genre_clauses = []
            for t in raw_tokens:
                terms = [t]
                if t in ("sci-fi", "scifi", "ficcao", "ficção", "science-fiction"):
                    terms.extend(["science-fiction", "sci-fi", "fantasy", "space"])
                elif t in ("acao", "ação", "action"):
                    terms.extend(["action", "adventure"])
                elif t in ("crime", "policial"):
                    terms.extend(["crime", "mystery", "legal"])
                elif t in ("comedia", "comédia", "comedy"):
                    terms.extend(["comedy"])
                elif t in ("animacao", "animação", "animation"):
                    terms.extend(["animation", "anime"])
                elif t in ("documentario", "documentário", "documentary"):
                    terms.extend(["documentary", "history", "nature"])
                elif t in ("suspense", "thriller"):
                    terms.extend(["thriller", "mystery"])

                for term in terms:
                    genre_clauses.append(col(CatalogShow.genres).ilike(f"%{term}%"))

            if genre_clauses:
                query = query.where(or_(*genre_clauses))

        # Count total matching shows
        count_query = select(func.count()).select_from(query.subquery())
        total_count = session.exec(count_query).one()

        # Sorting
        if sort_by == "seeds":
            query = query.order_by(col(CatalogShow.max_seeds).desc())
        elif sort_by == "date":
            query = query.order_by(col(CatalogShow.latest_release_date).desc())
        elif sort_by == "torrents":
            query = query.order_by(col(CatalogShow.total_torrents).desc())
        elif sort_by == "rating":
            query = query.order_by(col(CatalogShow.rating).desc())
        else:
            query = query.order_by(col(CatalogShow.max_seeds).desc())

        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        shows = session.exec(query).all()
        return list(shows), total_count

    @staticmethod
    def get_genres_with_counts(session: Session) -> list[dict]:
        """Aggregate genre counts across all catalog shows."""
        shows = session.exec(select(CatalogShow.genres).where(CatalogShow.genres != "")).all()
        counts: dict[str, int] = {}
        for g_str in shows:
            if not g_str:
                continue
            for part in g_str.split(","):
                clean = part.strip()
                if clean:
                    counts[clean] = counts.get(clean, 0) + 1
        sorted_genres = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"genre": k, "count": v} for k, v in sorted_genres]

    @staticmethod
    def get_curated_sections(session: Session) -> list[dict]:
        """Produce rich organized sections for streaming dashboard discovery."""
        sections: list[dict] = []

        # 1. Em Alta no P2P (Mais Semeados)
        top_seeds, _ = CatalogRepository.list_shows(
            session, min_seeds=5, sort_by="seeds", page_size=20
        )
        if top_seeds:
            sections.append(
                {
                    "id": "top_p2p",
                    "title": "Em Alta na Rede P2P (Mais Semeados)",
                    "icon": "Flame",
                    "items": top_seeds,
                }
            )

        # 2. Lançamentos Recentes
        recent, _ = CatalogRepository.list_shows(session, sort_by="date", page_size=20)
        if recent:
            sections.append(
                {
                    "id": "recent_releases",
                    "title": "Novos Episódios e Lançamentos",
                    "icon": "Clock",
                    "items": recent,
                }
            )

        # 3. Ficção Científica & Fantasia
        scifi, _ = CatalogRepository.list_shows(
            session, genre="sci-fi,fantasy", sort_by="seeds", page_size=20
        )
        if scifi:
            sections.append(
                {
                    "id": "scifi_fantasy",
                    "title": "Ficção Científica & Fantasia",
                    "icon": "Zap",
                    "items": scifi,
                }
            )

        # 4. Ação & Aventura
        action, _ = CatalogRepository.list_shows(
            session, genre="action,adventure", sort_by="seeds", page_size=20
        )
        if action:
            sections.append(
                {
                    "id": "action_adventure",
                    "title": "Ação & Aventura",
                    "icon": "Film",
                    "items": action,
                }
            )

        # 5. Crime & Mistério
        crime, _ = CatalogRepository.list_shows(
            session, genre="crime,mystery", sort_by="seeds", page_size=20
        )
        if crime:
            sections.append(
                {
                    "id": "crime_mystery",
                    "title": "Crime, Investigação & Mistério",
                    "icon": "Shield",
                    "items": crime,
                }
            )

        # 6. Comédias & Sitcoms
        comedy, _ = CatalogRepository.list_shows(
            session, genre="comedy", sort_by="seeds", page_size=20
        )
        if comedy:
            sections.append(
                {
                    "id": "comedy",
                    "title": "Comédias & Sitcoms",
                    "icon": "Smile",
                    "items": comedy,
                }
            )

        # 7. Documentários & Natureza
        docs, _ = CatalogRepository.list_shows(
            session, genre="nature,history,documentary", sort_by="seeds", page_size=20
        )
        if docs:
            sections.append(
                {
                    "id": "documentaries",
                    "title": "Documentários, História & Natureza",
                    "icon": "Compass",
                    "items": docs,
                }
            )

        return sections

    @staticmethod
    def normalize_imdb_id(imdb_id: str) -> str:
        """Normalize IMDB ID into canonical 'tt1234567' format."""
        clean = imdb_id.strip().lower()
        if clean.startswith("tt"):
            digits = clean[2:]
        else:
            digits = clean
        if digits.isdigit():
            return f"tt{digits.zfill(7)}"
        return clean

    @staticmethod
    def get_show(session: Session, imdb_id: str) -> Optional[CatalogShow]:
        """Get show by IMDB ID."""
        clean_id = CatalogRepository.normalize_imdb_id(imdb_id)
        return session.get(CatalogShow, clean_id)

    @staticmethod
    def get_show_releases(session: Session, imdb_id: str) -> list[CatalogRelease]:
        """Get all releases for a show ordered by season, episode and seeds."""
        clean_id = CatalogRepository.normalize_imdb_id(imdb_id)

        query = (
            select(CatalogRelease)
            .where(CatalogRelease.imdb_id == clean_id)
            .order_by(
                col(CatalogRelease.season).desc(),
                col(CatalogRelease.episode).desc(),
                col(CatalogRelease.seeds).desc(),
            )
        )
        return list(session.exec(query).all())

    @staticmethod
    def get_stats(session: Session) -> dict:
        """Get catalog aggregate statistics."""
        total_shows = session.exec(select(func.count(CatalogShow.imdb_id))).one()
        total_releases = session.exec(select(func.count(CatalogRelease.id))).one()
        max_seeds = session.exec(select(func.max(CatalogShow.max_seeds))).one() or 0
        latest_date = session.exec(select(func.max(CatalogShow.latest_release_date))).one()

        return {
            "total_shows": total_shows,
            "total_releases": total_releases,
            "max_seeds_in_catalog": max_seeds,
            "latest_release_date": latest_date,
        }
