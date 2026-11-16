"""Unit tests for EntityResolutionService and multi-format canonical domain (ADR-008)."""

import json

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.backend.models.catalog_domain import (
    DataProvenance,
    ExternalIdentifier,
    MediaWork,
    WorkRelation,
)
from src.backend.services.entity_resolution import EntityResolutionService


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_deterministic_entity_resolution_and_provenance(session: Session):
    """Same work from TMDB and IMDb merges into 1 canonical MediaWork with provenance."""
    tmdb_payload = {
        "work_type": "movie",
        "title": "Interestelar",
        "original_title": "Interstellar",
        "release_date": "2014-11-06",
        "release_year": 2014,
        "runtime_minutes": 169,
        "rating": 8.4,
        "rating_source": "tmdb",
        "vote_count": 35000,
        "imdb_id": "tt0816692",
        "tmdb_id": 157336,
        "genres": ["Science Fiction", "Drama"],
        "credits": [{"name": "Christopher Nolan", "role_type": "director"}],
    }
    work1, conf1 = EntityResolutionService.resolve_and_upsert_work(
        session, tmdb_payload, source_provider="tmdb"
    )
    assert conf1 == "created_new"
    assert work1.id is not None

    # Second ingestion from IMDb/Wikidata for the same movie with a different rating
    imdb_payload = {
        "work_type": "movie",
        "title": "Interstellar",
        "original_title": "Interstellar",
        "release_year": 2014,
        "rating": 8.7,
        "rating_source": "imdb",
        "vote_count": 2150000,
        "imdb_id": "tt0816692",
        "wikidata_id": "Q13417189",
        "availabilities": [
            {"provider_name": "Max", "territory": "BR", "monetization_type": "flatrate"}
        ],
    }
    work2, conf2 = EntityResolutionService.resolve_and_upsert_work(
        session, imdb_payload, source_provider="imdb"
    )
    assert conf2 == "deterministic"
    assert work2.id == work1.id

    # Verify both ratings are preserved in ratings_breakdown without loss
    breakdown = json.loads(work2.ratings_breakdown)
    assert breakdown["tmdb"]["rating"] == 8.4
    assert breakdown["imdb"]["rating"] == 8.7
    assert work2.canonical_rating == 8.7
    assert work2.rating_source == "imdb"

    # Verify external identifiers registered
    ext_ids = session.exec(
        select(ExternalIdentifier).where(ExternalIdentifier.work_id == work1.id)
    ).all()
    providers = {e.provider for e in ext_ids}
    assert "imdb" in providers
    assert "tmdb_movie" in providers
    assert "wikidata" in providers

    # Verify field-level provenance entries exist for both sources
    prov_records = session.exec(
        select(DataProvenance).where(DataProvenance.work_id == work1.id)
    ).all()
    prov_sources = {p.source_provider for p in prov_records}
    assert "tmdb" in prov_sources
    assert "imdb" in prov_sources


def test_anti_collision_remake_protection(session: Session):
    """Homonymous works from different years must not merge destructively."""
    dune_1984 = {
        "work_type": "movie",
        "title": "Duna",
        "original_title": "Dune",
        "release_year": 1984,
        "imdb_id": "tt0087182",
        "rating": 6.3,
        "credits": [{"name": "David Lynch", "role_type": "director"}],
    }
    dune_2021 = {
        "work_type": "movie",
        "title": "Duna",
        "original_title": "Dune",
        "release_year": 2021,
        "imdb_id": "tt1160419",
        "rating": 8.0,
        "credits": [{"name": "Denis Villeneuve", "role_type": "director"}],
    }

    w84, _ = EntityResolutionService.resolve_and_upsert_work(session, dune_1984, "imdb")
    w21, _ = EntityResolutionService.resolve_and_upsert_work(session, dune_2021, "imdb")

    assert w84.id != w21.id
    all_works = session.exec(select(MediaWork)).all()
    assert len(all_works) == 2

    # Check that an explicit remake relation was automatically recorded
    rel = session.exec(
        select(WorkRelation).where(
            WorkRelation.source_work_id == w21.id,
            WorkRelation.target_work_id == w84.id,
        )
    ).first()
    assert rel is not None
    assert rel.relation_type == "remake"
