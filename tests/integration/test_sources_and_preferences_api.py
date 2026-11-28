"""Integration tests for ADR-012 Wave 1: multi-source Fontes de Dados & Explore Preferences."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.backend.core.database import (
    get_eztv_session,
    get_session,
    init_db,
    init_eztv_db,
)
from src.backend.main import app
from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.db import CatalogRelease, CatalogShow
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease


@pytest.fixture
def dual_client():
    """Create isolated mainstream & sources in-memory SQLite engines for FastAPI TestClient."""
    main_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    src_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(main_engine)
    init_eztv_db(src_engine)

    with Session(main_engine) as ms:
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt0944947",
                imdb_num=944947,
                title_type="tvSeries",
                primary_title="Game of Thrones",
                original_title="Game of Thrones",
                title_ptbr="Guerra dos Tronos",
                start_year=2011,
                genres="Action,Adventure,Drama",
                genres_ptbr="Ação, Aventura, Drama",
                rating_score=9.2,
                rating_votes=2200000,
                streaming_providers="Max",
                has_eztv=1,
                eztv_id=101,
            )
        )
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt0133093",
                imdb_num=133093,
                title_type="movie",
                primary_title="The Matrix",
                original_title="The Matrix",
                title_ptbr="Matrix",
                start_year=1999,
                genres="Action,Sci-Fi",
                genres_ptbr="Ação, Ficção Científica",
                rating_score=8.7,
                rating_votes=2000000,
                streaming_providers="Max, Prime Video",
                has_eztv=0,
            )
        )
        ms.commit()

    with Session(src_engine) as ss:
        ss.add(
            EZTVShow(
                id=101,
                slug="game-of-thrones",
                name="Game of Thrones",
                imdb_id="tt0944947",
                rating_score=9.2,
                genres="Drama,Fantasy",
                streaming_providers="Max",
            )
        )
        ss.add(
            CatalogShow(
                imdb_id="tt0944947",
                title="Game of Thrones",
                rating=9.2,
                total_torrents=1,
                max_seeds=450,
            )
        )
        ss.add(
            CatalogRelease(
                eztv_id=99001,
                hash="deadbeef1",
                imdb_id="tt0944947",
                title="Game of Thrones S01E01 1080p",
                filename="got.s01e01.mkv",
                season=1,
                episode=1,
                quality="1080p",
                seeds=450,
                peers=40,
                size_bytes=1200000000,
                magnet_url="magnet:?xt=urn:btih:deadbeef1",
            )
        )
        ss.add(
            ExternalRelease(
                source_key="yify",
                external_id="yts-133093-1080p",
                imdb_id="tt0133093",
                title="The Matrix (1999) 1080p BluRay",
                work_type="movie",
                quality="1080p",
                seeds=980,
                peers=120,
                size_bytes=2100000000,
                release_type="magnet",
                magnet_url="magnet:?xt=urn:btih:matrixyify1080",
                genres="Action, Sci-Fi",
                year=1999,
                rating=8.7,
            )
        )
        ss.add(
            ExternalRelease(
                source_key="1337x",
                external_id="1337x-133093-4k",
                imdb_id="tt0133093",
                title="The.Matrix.1999.2160p.UHD",
                work_type="movie",
                quality="4K",
                seeds=310,
                peers=45,
                size_bytes=8400000000,
                release_type="link",
                external_url="https://1337x.to/torrent/133093/matrix",
                genres="Action, Sci-Fi",
                year=1999,
                rating=8.7,
            )
        )
        ss.commit()

    def override_main():
        with Session(main_engine) as s:
            yield s

    def override_sources():
        with Session(src_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_main
    app.dependency_overrides[get_eztv_session] = override_sources
    try:
        with TestClient(app) as c:
            yield c, main_engine, src_engine
    finally:
        app.dependency_overrides.clear()
        SQLModel.metadata.drop_all(main_engine)


def test_sources_summary_catalog_and_releases_multisource(dual_client):
    client, _main_e, _src_e = dual_client

    summary_res = client.get("/api/sources/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    by_key = {s["source_key"]: s for s in summary["sources"]}
    assert set(by_key.keys()) >= {"eztv", "yify", "tgx", "nyaasi", "bitsearch", "glodls"}
    assert by_key["yify"]["base_url"] == "https://movies-api.accel.li/api/v2/list_movies.json"
    assert by_key["eztv"]["total_titles"] >= 1
    assert by_key["yify"]["total_releases"] == 1

    # Multi-source releases for The Matrix (yify + 1337x)
    rel_res = client.get("/api/sources/releases?imdb_id=tt0133093&include_live=false")
    assert rel_res.status_code == 200
    rel_data = rel_res.json()
    assert rel_data["total"] == 2
    assert set(rel_data["available_sources"]) == {"1337x", "yify"}
    assert len(rel_data["by_source"]["yify"]) == 1
    assert len(rel_data["by_source"]["1337x"]) == 1

    # Paginated multi-source catalog filterable by source + Sovereign Batch Join from mainstream.db
    cat_yify = client.get("/api/sources/catalog?source=yify")
    assert cat_yify.status_code == 200
    yify_items = cat_yify.json()["items"]
    assert len(yify_items) == 1
    assert yify_items[0]["source_key"] == "yify"
    assert yify_items[0]["imdb_id"] == "tt0133093"
    assert yify_items[0]["is_enriched"] is True

    # Canonical IMDb deduplication in "all" mode aggregates sources for tt0133093
    cat_all = client.get("/api/sources/catalog?source=all")
    assert cat_all.status_code == 200
    by_imdb = {it["imdb_id"]: it for it in cat_all.json()["items"]}
    assert by_imdb["tt0133093"]["media_sources"] == ["1337x", "yify"]
    assert by_imdb["tt0133093"]["total_torrents"] == 2


def test_explore_preferences_hybrid_persistence(dual_client):
    client, _main_e, _src_e = dual_client

    get_default = client.get("/api/explore/preferences")
    assert get_default.status_code == 200
    defaults = get_default.json()
    assert defaults["schema_version"] in (1, 2)
    assert defaults["badge_provider_action"] == "filter_provider"
    assert defaults["badge_media_action"] == "open_sources_modal"
    assert defaults["auto_apply_filters"] is False

    updated_payload = {
        "schema_version": 1,
        "badge_provider_action": "open_details",
        "badge_media_action": "filter_has_media",
        "auto_apply_filters": True,
        "show_all_genres": True,
        "filter_panel_expanded": True,
    }
    put_res = client.put("/api/explore/preferences", json=updated_payload)
    assert put_res.status_code == 200
    assert put_res.json()["badge_provider_action"] == "open_details"

    get_persisted = client.get("/api/explore/preferences")
    assert get_persisted.status_code == 200
    persisted = get_persisted.json()
    assert persisted["schema_version"] == 2
    for key in (
        "badge_provider_action",
        "badge_media_action",
        "auto_apply_filters",
        "show_all_genres",
        "filter_panel_expanded",
    ):
        assert persisted[key] == updated_payload[key]

    invalid_res = client.put(
        "/api/explore/preferences",
        json={**updated_payload, "badge_provider_action": "invalid_action"},
    )
    assert invalid_res.status_code == 422


def test_explore_and_discovery_annotate_has_media_and_filter_sources(dual_client):
    client, _main_e, _src_e = dual_client

    res = client.get("/api/explore/works")
    assert res.status_code == 200
    items = {it["imdb_id"]: it for it in res.json()["items"]}

    assert items["tt0944947"]["has_media"] is True
    assert "eztv" in items["tt0944947"]["media_sources"]
    assert items["tt0944947"]["sources_count"] >= 1

    assert items["tt0133093"]["has_media"] is True
    assert items["tt0133093"]["media_sources"] == ["1337x", "yify"]
    assert items["tt0133093"]["sources_count"] == 2

    # Filter specifically by yify source in /api/explore/works
    yify_res = client.get("/api/explore/works?data_sources=yify")
    assert yify_res.status_code == 200
    yify_items = yify_res.json()["items"]
    assert len(yify_items) == 1
    assert yify_items[0]["imdb_id"] == "tt0133093"

    # Discovery search also carries has_media + media_sources
    disc_res = client.get("/api/discovery/search?q=Matrix")
    assert disc_res.status_code == 200
    disc_items = disc_res.json()
    assert len(disc_items) == 1
    assert disc_items[0]["has_media"] is True
    assert disc_items[0]["media_sources"] == ["1337x", "yify"]


@respx.mock
def test_sources_sync_yify_and_invalid_provider(dual_client):
    client, _main_e, _src_e = dual_client

    respx.get("https://movies-api.accel.li/api/v2/list_movies.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "movies": [
                        {
                            "id": 55501,
                            "imdb_code": "tt0816692",
                            "title": "Interstellar Odyssey",
                            "year": 2014,
                            "rating": 8.7,
                            "genres": ["Adventure", "Drama", "Sci-Fi"],
                            "url": "https://movies-api.accel.li/movies/interstellar-2014",
                            "torrents": [
                                {
                                    "hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                                    "quality": "1080p",
                                    "seeds": 740,
                                    "peers": 80,
                                    "size_bytes": 2400000000,
                                    "url": "https://movies-api.accel.li/torrent/download/abc",
                                }
                            ],
                        }
                    ]
                },
            },
        )
    )

    sync_res = client.post("/api/sources/sync?source=yify&pages=1&enrich=false&mode=baseline")
    assert sync_res.status_code == 200
    payload = sync_res.json()
    assert payload["results"]["yify"]["status"] == "success"
    assert payload["results"]["yify"]["telemetry"]["releases_indexed"] == 1
    assert (
        payload["results"]["yify"]["telemetry"]["endpoint"]
        == "https://movies-api.accel.li/api/v2/list_movies.json"
    )

    rel_res = client.get("/api/sources/releases?imdb_id=tt0816692&source=yify&include_live=false")
    assert rel_res.status_code == 200
    assert rel_res.json()["total"] == 1
    item = rel_res.json()["items"][0]
    assert item["source_key"] == "yify"
    assert "dn=Interstellar+Odyssey" in item["magnet_url"]
    assert "tracker.zhuqiy.com" in item["magnet_url"]

    bad_res = client.post("/api/sources/sync?source=unknown_provider")
    assert bad_res.status_code == 400


def test_adr012_frontend_accessibility_and_layout_contracts():
    root = Path(__file__).resolve().parents[2]
    css = (root / "src/frontend/src/index.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css

    navbar = (root / "src/frontend/src/components/Navbar.tsx").read_text(encoding="utf-8")
    assert 'htmlFor="navbar-global-search"' in navbar
    assert "Descobrir" in navbar
    assert "Catálogo" in navbar
    assert "Fontes" in navbar
    assert "min-w-[44px] min-h-[44px]" in navbar

    show_card = (root / "src/frontend/src/components/ShowCard.tsx").read_text(encoding="utf-8")
    assert "MediaBadge" in show_card
    assert "cardWidth < 190" in show_card
    assert "aria-expanded={actionsOpen}" in show_card

    api_ts = (root / "src/frontend/src/services/api.ts").read_text(encoding="utf-8")
    assert "AbortController" in api_ts
    assert "RequestAbortChannel" in api_ts
    assert "/explore/preferences" in api_ts
    assert "/sources/releases" in api_ts

    dist_html = root / "src/backend/static/dist/index.html"
    assert dist_html.exists()
