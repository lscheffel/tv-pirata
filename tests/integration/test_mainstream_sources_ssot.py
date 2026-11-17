"""Integration tests for ADR-011 Dual-SSOT (mainstream.db & sources.db) & SQL Pushdown."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.database import (
    get_eztv_session,
    get_session,
    init_db,
    init_eztv_db,
)
from src.backend.main import app
from src.backend.models.catalog_domain import IMDbCatalogShow, IMDbEpisodeCatalog
from src.backend.models.db import CatalogShow, ShowRecord
from src.backend.models.eztv_db import EZTVShow


def test_imdb_sql_pushdown_filtering_facets_and_dossier() -> None:
    """Verify DiscoveryEngineRepository uses SQL pushdown over IMDbCatalogShow in mainstream.db."""
    catalog_cache.invalidate()
    discovery_cache.invalidate()

    main_eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    src_eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(main_eng)
    init_eztv_db(src_eng)

    with Session(main_eng) as ms:
        ms.add_all(
            [
                IMDbCatalogShow(
                    imdb_id="tt0944947",
                    imdb_num=944947,
                    tmdb_id=1399,
                    title_type="tvSeries",
                    primary_title="Game of Thrones",
                    original_title="Game of Thrones",
                    title_ptbr="Guerra dos Tronos",
                    start_year=2011,
                    end_year=2019,
                    runtime_minutes=57,
                    genres="Action, Adventure, Drama",
                    genres_ptbr="Ação, Aventura, Drama",
                    rating_score=9.2,
                    rating_votes=2400000,
                    status="Ended",
                    network="HBO",
                    streaming_providers="Max",
                    directors="David Benioff",
                    cast_members="Emilia Clarke, Peter Dinklage",
                    has_eztv=1,
                    eztv_id=481,
                    eztv_slug="game-of-thrones",
                    eztv_match_type="exact_imdb",
                    tmdb_synced=1,
                ),
                IMDbCatalogShow(
                    imdb_id="tt0111161",
                    imdb_num=111161,
                    tmdb_id=278,
                    title_type="movie",
                    primary_title="The Shawshank Redemption",
                    original_title="The Shawshank Redemption",
                    title_ptbr="Um Sonho de Liberdade",
                    start_year=1994,
                    runtime_minutes=142,
                    genres="Drama",
                    genres_ptbr="Drama",
                    rating_score=9.3,
                    rating_votes=2900000,
                    status="Released",
                    streaming_providers="Max",
                    directors="Frank Darabont",
                    cast_members="Tim Robbins, Morgan Freeman",
                    has_eztv=0,
                    tmdb_synced=1,
                ),
                IMDbCatalogShow(
                    imdb_id="tt0120737",
                    imdb_num=120737,
                    tmdb_id=120,
                    title_type="movie",
                    primary_title="The Lord of the Rings: The Fellowship of the Ring",
                    original_title="The Lord of the Rings: The Fellowship of the Ring",
                    title_ptbr="O Senhor dos Anéis: A Sociedade do Anel",
                    start_year=2001,
                    runtime_minutes=178,
                    genres="Action, Adventure, Fantasy",
                    genres_ptbr="Ação, Aventura, Fantasia",
                    rating_score=8.9,
                    rating_votes=2250000,
                    status="Released",
                    streaming_providers="Max",
                    directors="Peter Jackson",
                    cast_members="Elijah Wood, Ian McKellen",
                    has_eztv=0,
                    tmdb_synced=1,
                ),
                IMDbCatalogShow(
                    imdb_id="tt9999999",
                    imdb_num=9999999,
                    tmdb_id=999999,
                    title_type="movie",
                    primary_title="Shawshank: Behind the Scenes",
                    original_title="Shawshank: Behind the Scenes",
                    title_ptbr="Bastidores de um Sonho",
                    start_year=2004,
                    runtime_minutes=30,
                    genres="Documentary",
                    genres_ptbr="Documentário",
                    rating_score=9.9,
                    rating_votes=80,
                    status="Released",
                    has_eztv=0,
                    tmdb_synced=1,
                ),
            ]
        )
        ms.add(
            IMDbEpisodeCatalog(
                episode_imdb_id="tt1480055",
                show_imdb_id="tt0944947",
                season=1,
                episode=1,
                title="Winter Is Coming",
                rating_score=9.0,
            )
        )
        ms.add(
            ShowRecord(
                tmdb_id=278,
                imdb_id="tt0111161",
                title="Um Sonho de Liberdade",
                user_status="completed",
            )
        )
        ms.commit()

    with Session(src_eng) as ss:
        ss.add(
            EZTVShow(
                id=481,
                slug="game-of-thrones",
                name="Game of Thrones",
                imdb_id="tt0944947",
                status="Ended",
                network="HBO",
                streaming_providers="Max",
            )
        )
        ss.add(
            CatalogShow(
                imdb_id="tt0944947",
                title="Game of Thrones",
                max_seeds=320,
                total_torrents=50,
            )
        )
        ss.commit()

    def override_main():
        with Session(main_eng) as s:
            yield s

    def override_sources():
        with Session(src_eng) as s:
            yield s

    app.dependency_overrides[get_session] = override_main
    app.dependency_overrides[get_eztv_session] = override_sources
    try:
        client = TestClient(app)

        # 1. All works query ordered by popularity/votes
        res_all = client.get("/api/explore/works")
        assert res_all.status_code == 200
        body = res_all.json()
        assert body["total"] == 4
        assert body["items"][0]["imdb_id"] == "tt0111161"
        assert body["items"][1]["eztv_available"] is True
        assert body["items"][1]["eztv_show_id"] == 481
        assert body["items"][1]["p2p_max_seeds"] == 320

        # 2. Filter only_with_p2p=True uses has_eztv index in mainstream.db
        res_p2p = client.get("/api/explore/works", params={"only_with_p2p": "true"})
        assert res_p2p.status_code == 200
        assert res_p2p.json()["total"] == 1
        assert res_p2p.json()["items"][0]["title"] == "Guerra dos Tronos"

        # 3. exclude_watched=True filters out completed ShowRecord in SQL
        res_unwatched = client.get("/api/explore/works", params={"exclude_watched": "true"})
        assert res_unwatched.status_code == 200
        assert res_unwatched.json()["total"] == 3
        assert res_unwatched.json()["items"][0]["imdb_id"] == "tt0944947"

        # 4. Dossier lookup by numeric imdb_num and ttXXXXXXX string
        d1 = client.get("/api/explore/works/944947")
        d2 = client.get("/api/explore/works/tt0944947")
        assert d1.status_code == 200
        assert d2.status_code == 200
        assert d1.json()["episodes_count"] == 1
        assert d1.json()["eztv_available"] is True
        assert d1.json()["streaming_providers"] == ["Max"]

        # 5. Bilingual (PT-BR & EN-US) accent-insensitive search & exact/similarity ranking
        # Searching without accents in PT-BR ("senhor dos aneis") on both Descobrir & Explorar
        disc_pt = client.get("/api/discovery/search", params={"q": "senhor dos aneis"})
        assert disc_pt.status_code == 200
        assert len(disc_pt.json()) >= 1
        assert disc_pt.json()[0]["imdb_id"] == "tt0120737"
        assert disc_pt.json()[0]["title"] == "O Senhor dos Anéis: A Sociedade do Anel"
        assert (
            disc_pt.json()[0]["original_title"]
            == "The Lord of the Rings: The Fellowship of the Ring"
        )

        exp_en = client.get("/api/explore/works", params={"q": "Shawshank"})
        assert exp_en.status_code == 200
        assert exp_en.json()["total"] == 2
        # Exact/popular work ("The Shawshank Redemption", 9.3, 2.9M votes) beats 9.9 obscure short
        assert exp_en.json()["items"][0]["imdb_id"] == "tt0111161"

        disc_exact = client.get("/api/discovery/search", params={"q": "Um Sonho de Liberdade"})
        assert disc_exact.status_code == 200
        assert disc_exact.json()[0]["imdb_id"] == "tt0111161"

        # 6. UnifiedShow detail endpoint resolves seasons/episodes from mainstream.db
        show_det = client.get("/api/discovery/shows/944947", params={"provider": "imdb"})
        assert show_det.status_code == 200
        assert show_det.json()["imdb_id"] == "tt0944947"
        assert len(show_det.json()["seasons"]) == 1
        assert show_det.json()["seasons"][0]["episodes"][0]["title"] == "Winter Is Coming"

        # 7. External sources catalog serves P2P shows/stats directly from sources.db
        cat_stats = client.get("/api/catalog/stats")
        assert cat_stats.status_code == 200
        assert cat_stats.json()["total_shows"] == 1
        assert cat_stats.json()["max_seeds_in_catalog"] == 320

        # 8. Canonical mainstream.db stats and update endpoint
        ms_stats = client.get("/api/explore/mainstream-stats")
        assert ms_stats.status_code == 200
        assert ms_stats.json()["total_titles"] == 4
        assert ms_stats.json()["eztv_badged_titles"] == 1

        ms_upd = client.post("/api/explore/update-mainstream", params={"mode": "badges"})
        assert ms_upd.status_code == 200
        assert ms_upd.json()["status"] == "updated"
        assert ms_upd.json()["stats"]["total_titles"] == 4

        # 9. Canonical facets normalization (31 genres, data_sources, formats, providers)
        from src.backend.core.canonical_taxonomy import merge_canonical_providers

        assert merge_canonical_providers("HBO Max, Amazon Prime Video, Apple TV, TV Globo") == [
            "Max",
            "Prime Video",
            "Apple TV+",
            "Globoplay",
        ]
        facet_genres = {g["key"]: g["count"] for g in body["facets"]["genres"]}
        assert facet_genres["Drama"] == 2
        assert facet_genres["Ação"] == 2
        assert facet_genres["Fantasia"] == 1
        assert facet_genres["Documentário"] == 1

        facet_types = {w["key"]: w["count"] for w in body["facets"]["work_types"]}
        assert facet_types["movie"] == 3
        assert facet_types["tv_show"] == 1
        assert facet_types["documentary"] == 1

        facet_sources = {s["key"]: s["count"] for s in body["facets"]["data_sources"]}
        assert facet_sources["imdb"] == 4
        assert facet_sources["eztv"] == 1
        assert facet_sources["tmdb"] == 4

        # Filtering by documentary work_type & streaming_providers="Max" & data_sources="eztv"
        res_doc = client.get("/api/explore/works", params={"work_types": "documentary"})
        assert res_doc.status_code == 200
        assert res_doc.json()["total"] == 1
        assert res_doc.json()["items"][0]["imdb_id"] == "tt9999999"

        res_max = client.get("/api/explore/works", params={"streaming_providers": "Max"})
        assert res_max.status_code == 200
        assert res_max.json()["total"] == 3

        res_ez = client.get("/api/explore/works", params={"data_sources": "eztv"})
        assert res_ez.status_code == 200
        assert res_ez.json()["total"] == 1
        assert res_ez.json()["items"][0]["imdb_id"] == "tt0944947"
    finally:
        app.dependency_overrides.clear()
