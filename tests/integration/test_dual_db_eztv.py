"""Integration tests for ADR-009 dual-database separation and EZTV cross-referencing."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, delete

from src.backend.core.database import get_eztv_session, get_session
from src.backend.main import app
from src.backend.models.catalog_domain import MediaWork
from src.backend.models.eztv_db import EZTVEpisodeCatalog, EZTVShow, eztv_metadata

main_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(main_engine)

eztv_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
eztv_metadata.create_all(eztv_engine)


def override_main_session():
    with Session(main_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def override_eztv_session():
    with Session(eztv_engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_isolated_dual_dbs():
    app.dependency_overrides[get_session] = override_main_session
    app.dependency_overrides[get_eztv_session] = override_eztv_session

    with Session(main_engine) as s:
        s.exec(delete(MediaWork))
        s.add(
            MediaWork(
                id=101,
                work_type="tv_show",
                title="Severance",
                overview="Work-life balance thriller.",
                imdb_id="tt11280740",
                canonical_rating=8.7,
                rating_source="tmdb",
                genres_csv="Drama, Sci-Fi",
            )
        )
        s.add(
            MediaWork(
                id=102,
                work_type="tv_show",
                title="Dark Matter",
                overview="Multiverse sci-fi series.",
                imdb_id=None,
                canonical_rating=7.9,
                rating_source="tmdb",
                genres_csv="Sci-Fi",
            )
        )
        s.add(
            MediaWork(
                id=103,
                work_type="movie",
                title="Non EZTV Original Film",
                overview="Not on EZTV.",
                imdb_id="tt9990001",
                canonical_rating=8.0,
                rating_source="tmdb",
                genres_csv="Drama",
            )
        )
        s.commit()

    with Session(eztv_engine) as ez:
        ez.exec(delete(EZTVEpisodeCatalog))
        ez.exec(delete(EZTVShow))
        ez.add(
            EZTVShow(
                id=11280740,
                slug="severance",
                name="Severance",
                status="Running",
                rating_score=8.7,
                imdb_id="tt11280740",
                poster_url="https://example.com/severance.jpg",
                synopsis="Work-life balance thriller.",
                genres="Drama, Sci-Fi",
                network="Apple TV+",
            )
        )
        ez.add(
            EZTVShow(
                id=22222222,
                slug="dark-matter",
                name="Dark Matter",
                status="Running",
                rating_score=7.9,
                imdb_id=None,
                genres="Sci-Fi",
            )
        )
        ez.add(
            EZTVEpisodeCatalog(
                show_id=11280740,
                season=1,
                episode=1,
                title="Good News About Hell",
                airdate="2022-02-18",
                source="tvmaze",
            )
        )
        ez.commit()

    yield
    app.dependency_overrides.clear()


def test_dual_database_tables_are_physically_isolated():
    main_tables = set(inspect(main_engine).get_table_names())
    eztv_tables = set(inspect(eztv_engine).get_table_names())

    assert "mediawork" in main_tables
    assert "shows" not in main_tables
    assert "episodes_catalog" not in main_tables

    assert eztv_tables == {"shows", "episodes_catalog"}


def test_explore_cross_references_eztv_by_imdb_and_slug():
    res = client.get("/api/explore/works")
    assert res.status_code == 200
    items = {item["title"]: item for item in res.json()["items"]}

    # Strong match by IMDb ID
    assert items["Severance"]["eztv_available"] is True
    assert items["Severance"]["eztv_show_id"] == 11280740

    # Fallback match by normalized title/slug when IMDb ID is absent
    assert items["Dark Matter"]["eztv_available"] is True
    assert items["Dark Matter"]["eztv_show_id"] == 22222222

    # Unmatched work
    assert items["Non EZTV Original Film"]["eztv_available"] is False
    assert items["Non EZTV Original Film"]["eztv_show_id"] is None

    # Dossier endpoint also carries EZTV availability
    dossier_res = client.get("/api/explore/works/101")
    assert dossier_res.status_code == 200
    assert dossier_res.json()["eztv_available"] is True
    assert dossier_res.json()["eztv_show_id"] == 11280740


def test_catalog_reads_from_eztv_metadata_db_and_returns_episodes():
    res = client.get("/api/catalog/shows")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    titles = {s["title"] for s in data["items"]}
    assert titles == {"Severance", "Dark Matter"}

    detail = client.get("/api/catalog/shows/tt11280740")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["show"]["eztv_show_id"] == 11280740
    assert len(payload["episodes"]) == 1
    assert payload["episodes"][0]["title"] == "Good News About Hell"

    stats = client.get("/api/catalog/stats")
    assert stats.status_code == 200
    assert stats.json()["total_shows"] == 2
    assert stats.json()["total_episodes"] == 1

