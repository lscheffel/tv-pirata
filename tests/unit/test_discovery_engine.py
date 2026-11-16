"""Unit tests for the Advanced Discovery Engine, boolean filters, and facets (ADR-008)."""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.backend.repositories.discovery_engine import DiscoveryEngineRepository
from src.backend.services.federated_catalog import FederatedCatalogService


@pytest.fixture
def seeded_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        FederatedCatalogService().ensure_federated_catalog_seeded(session)
        yield session


def test_advanced_filtering_engine_complex_query(seeded_session: Session):
    """Test strategic handoff example query:
    Sci-Fi or Suspense movies between 2014 and 2026, rating >= 7.5, directed by Denis Villeneuve,
    runtime > 100m, available on Max or Netflix.
    """
    result = DiscoveryEngineRepository.query_works(
        session=seeded_session,
        work_types="movie",
        genres_any="Ficção Científica,Suspense",
        year_from=2014,
        year_to=2026,
        min_rating=7.5,
        min_runtime=100,
        person_query="Denis Villeneuve",
        role_type="director",
        streaming_providers="Max,Netflix",
    )

    assert result["total"] >= 3
    titles = {item["original_title"] for item in result["items"]}
    assert "Dune: Part Two" in titles
    assert "Dune" in titles
    assert "Arrival" in titles
    assert "Blade Runner 2049" in titles

    # Check dynamic facets returned
    facets = result["facets"]
    assert any(f["key"] == "movie" for f in facets["work_types"])
    assert len(facets["genres"]) > 0
    assert len(facets["streaming_providers"]) > 0


def test_boolean_genre_operators_and_not(seeded_session: Session):
    """Test genres_all (AND) and genres_not (NOT) filtering."""
    res = DiscoveryEngineRepository.query_works(
        session=seeded_session,
        genres_all="Ficção Científica,Drama",
        genres_not="Animação,Documentário",
    )
    assert res["total"] > 0
    for item in res["items"]:
        assert item["work_type"] not in ("animation", "documentary")
        assert "Ficção Científica" in item["genres"]
        assert "Drama" in item["genres"]


def test_relationship_discovery_and_collaborations(seeded_session: Session):
    """Verify actor/director filmography and shared collaboration queries."""
    collab = DiscoveryEngineRepository.find_shared_collaborations(
        seeded_session, "Denis Villeneuve", "Rebecca Ferguson"
    )
    assert collab["person_a"] == "Denis Villeneuve"
    assert collab["person_b"] == "Rebecca Ferguson"
    shared_titles = {w["title"] for w in collab["shared_works"]}
    assert "Duna" in shared_titles
    assert "Duna: Parte Dois" in shared_titles

    nolan_cillian = DiscoveryEngineRepository.find_shared_collaborations(
        seeded_session, "Christopher Nolan", "Cillian Murphy"
    )
    nc_titles = {
        w["original_title"] if "original_title" in w else w["title"]
        for w in nolan_cillian["shared_works"]
    }
    assert "Oppenheimer" in nc_titles
    assert "A Origem" in nc_titles


def test_similarity_engine_and_calendar(seeded_session: Session):
    """Verify objective similarity reasons and release calendar confidence levels."""
    search_res = DiscoveryEngineRepository.query_works(seeded_session, q="Duna: Parte Dois")
    assert search_res["total"] >= 1
    work_id = search_res["items"][0]["id"]

    dossier = DiscoveryEngineRepository.get_work_dossier(seeded_session, work_id)
    assert dossier is not None
    assert len(dossier["similar_works"]) > 0
    top_sim = dossier["similar_works"][0]
    assert top_sim["similarity_score"] > 30.0
    assert len(top_sim["similarity_reasons"]) > 0

    events = DiscoveryEngineRepository.get_calendar_events(
        seeded_session, confidence_level="confirmed"
    )
    assert len(events) >= 2
    assert all(e["confidence_level"] == "confirmed" for e in events)
