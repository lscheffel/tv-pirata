"""Integration tests for the /api/explore REST endpoints (ADR-008)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.backend.core.database import get_session
from src.backend.main import app

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)


def override_get_session():
    with Session(test_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[get_session] = override_get_session


def test_explore_works_and_facets_endpoint():
    res = client.get(
        "/api/explore/works",
        params={
            "work_types": "movie,tv_show",
            "min_rating": 8.0,
            "sort_by": "rating",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 5
    assert len(data["items"]) >= 5
    assert "facets" in data
    assert len(data["facets"]["work_types"]) >= 2
    assert len(data["facets"]["genres"]) >= 3


def test_explore_work_dossier_endpoint():
    list_res = client.get("/api/explore/works", params={"q": "Interstellar"})
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) >= 1
    work_id = items[0]["id"]

    dossier_res = client.get(f"/api/explore/works/{work_id}")
    assert dossier_res.status_code == 200
    dossier = dossier_res.json()
    assert dossier["original_title"] == "Interstellar"
    assert dossier["imdb_id"] == "tt0816692"
    assert len(dossier["external_identifiers"]) >= 2
    assert len(dossier["provenance"]) >= 2
    assert len(dossier["credits"]) >= 3
    assert len(dossier["availabilities"]) >= 1
    assert len(dossier["similar_works"]) >= 1


def test_explore_people_and_collaborations_endpoints():
    people_res = client.get("/api/explore/people", params={"department": "Directing"})
    assert people_res.status_code == 200
    directors = people_res.json()
    assert len(directors) >= 3
    villeneuve = next((d for d in directors if d["name"] == "Denis Villeneuve"), None)
    assert villeneuve is not None

    person_dossier = client.get(f"/api/explore/people/{villeneuve['id']}")
    assert person_dossier.status_code == 200
    pd = person_dossier.json()
    assert len(pd["filmography"]) >= 4
    assert len(pd["frequent_collaborators"]) >= 2

    collab_res = client.get(
        "/api/explore/people/collaborations",
        params={"person_a": "Vince Gilligan", "person_b": "Rhea Seehorn"},
    )
    assert collab_res.status_code == 200
    shared = collab_res.json()["shared_works"]
    assert len(shared) >= 2


def test_explore_calendar_and_rankings_endpoints():
    cal_res = client.get("/api/explore/calendar")
    assert cal_res.status_code == 200
    events = cal_res.json()
    assert len(events) >= 3
    assert any(e["confidence_level"] == "confirmed" for e in events)

    rank_res = client.get("/api/explore/rankings")
    assert rank_res.status_code == 200
    rankings = rank_res.json()
    assert len(rankings["top_movies"]) >= 3
    assert len(rankings["top_series"]) >= 3
    assert len(rankings["upcoming_productions"]) >= 1
