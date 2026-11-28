"""Hermetic integration tests for ADR-015 Unified 3-Pillar Resumable Hydration Engine."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.backend.core.database import (
    get_eztv_session,
    get_session,
    init_db,
    init_eztv_db,
)
from src.backend.main import app
from src.backend.models.catalog_domain import IMDbCatalogShow
from src.backend.models.eztv_db import EZTVShow
from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord
from src.backend.providers.sources.base import compute_title_match_confidence
from src.backend.providers.sources.yify_adapter import YIFYSourceAdapter
from src.backend.services.cascading_enricher import CascadingMetadataEnricher
from src.backend.services.hydration_orchestrator import (
    SmartBootstrapDetector,
    hydration_orchestrator,
)
from src.backend.services.sources_registry import SourcesRegistryService


@pytest.fixture
def hydration_client():
    """Isolated Dual-SSOT SQLite engines wired to FastAPI TestClient."""
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

    def override_main():
        with Session(main_engine) as s:
            yield s

    def override_sources():
        with Session(src_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_main
    app.dependency_overrides[get_eztv_session] = override_sources
    try:
        with TestClient(app) as client:
            yield client, main_engine, src_engine
    finally:
        app.dependency_overrides.clear()
        SQLModel.metadata.drop_all(main_engine)


def test_smart_bootstrap_detector_zero_vs_warm(hydration_client, monkeypatch):
    """Verify Zero-State -> BOOTSTRAP and >= threshold -> DELTA detection."""
    _client, main_engine, src_engine = hydration_client

    with Session(main_engine) as ms, Session(src_engine) as ss:
        st0 = hydration_orchestrator.get_status(ms, ss)
        assert st0.overall_mode == "BOOTSTRAP"
        assert st0.imdb_backbone_mode == "BOOTSTRAP"
        assert st0.eztv_mode == "BOOTSTRAP"

        # Seed canonical shows & EZTV rows and test lowered threshold switch
        for idx in range(5):
            ms.add(
                IMDbCatalogShow(
                    imdb_id=f"tt100000{idx}",
                    title_type="tvSeries",
                    primary_title=f"Show {idx}",
                    start_year=2022,
                    rating_votes=10000 - idx,
                    poster_url="https://example.org/p.jpg",
                    synopsis="Sample synopsis EN",
                    synopsis_ptbr="Sinopse exemplo PT",
                )
            )
            ss.add(
                EZTVShow(
                    id=500 + idx,
                    slug=f"show-{idx}",
                    name=f"Show {idx}",
                    imdb_id=f"tt100000{idx}",
                )
            )
        ms.commit()
        ss.commit()

        monkeypatch.setattr(
            "src.backend.services.hydration_orchestrator.IMDB_BOOTSTRAP_THRESHOLD",
            5,
        )
        monkeypatch.setattr(
            "src.backend.services.hydration_orchestrator.EZTV_BOOTSTRAP_THRESHOLD",
            5,
        )
        st1 = hydration_orchestrator.get_status(ms, ss)
        assert st1.imdb_backbone_mode == "DELTA"
        assert st1.eztv_mode == "DELTA"
        assert st1.sources["yify"].mode == "BOOTSTRAP"
        st1.sources["yify"].bootstrap_completed = True
        refreshed = SmartBootstrapDetector.refresh_modes(st1, ms, ss)
        assert refreshed.sources["yify"].mode == "DELTA"


@respx.mock
def test_yify_paginated_compact_presence_and_jit_upgrade(hydration_client):
    """Verify YTS compact Stage 1B batch upsert + cursor advance + Stage 2 JIT magnet upgrade."""
    client, _main_engine, src_engine = hydration_client

    route = respx.get("https://movies-api.accel.li/api/v2/list_movies.json").mock(
        side_effect=[
            # Page 2 response during compact presence sync
            httpx.Response(
                200,
                json={
                    "status": "ok",
                    "data": {
                        "movie_count": 100,
                        "limit": 50,
                        "page_number": 2,
                        "movies": [
                            {
                                "id": 9001,
                                "imdb_code": "tt0816692",
                                "title": "Interstellar",
                                "year": 2014,
                                "rating": 8.7,
                                "genres": ["Sci-Fi", "Drama"],
                                "url": "https://movies-api.accel.li/movies/interstellar-2014",
                                "torrents": [
                                    {
                                        "hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                        "quality": "720p",
                                        "seeds": 120,
                                        "peers": 10,
                                        "size_bytes": 1100000000,
                                    },
                                    {
                                        "hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                                        "quality": "1080p",
                                        "video_codec": "x265",
                                        "seeds": 450,
                                        "peers": 40,
                                        "size_bytes": 2100000000,
                                    },
                                ],
                            }
                        ],
                    },
                },
            ),
            # Stage 2 JIT full lookup when opening modal
            httpx.Response(
                200,
                json={
                    "status": "ok",
                    "data": {
                        "movies": [
                            {
                                "id": 9001,
                                "imdb_code": "tt0816692",
                                "title": "Interstellar",
                                "year": 2014,
                                "rating": 8.7,
                                "genres": ["Sci-Fi", "Drama"],
                                "url": "https://movies-api.accel.li/movies/interstellar-2014",
                                "torrents": [
                                    {
                                        "hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                        "quality": "720p",
                                        "seeds": 120,
                                        "peers": 10,
                                        "size_bytes": 1100000000,
                                    },
                                    {
                                        "hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                                        "quality": "1080p",
                                        "video_codec": "x265",
                                        "seeds": 450,
                                        "peers": 40,
                                        "size_bytes": 2100000000,
                                    },
                                ],
                            }
                        ]
                    },
                },
            ),
        ]
    )

    with Session(src_engine) as ss:
        SourcesRegistryService.ensure_sources_registered(ss)
        yify_inst = ss.get(ExternalSourceRecord, "yify")
        assert yify_inst is not None

        tel = asyncio.run(
            YIFYSourceAdapter().sync(
                yify_inst,
                ss,
                pages=1,
                start_page=2,
                compact_presence=True,
                mode="baseline",
            )
        )
        assert tel["start_page"] == 2
        assert tel["total_pages"] == 2
        assert tel["bootstrap_completed"] is True
        assert tel["releases_indexed"] == 1

        rows = list(
            ss.exec(select(ExternalRelease).where(ExternalRelease.source_key == "yify")).all()
        )
        assert len(rows) == 1
        assert rows[0].external_id == "yts:presence:tt0816692"
        assert "720p,1080p.x265" == rows[0].quality

    # Stage 2 auto lookup must treat yts:presence as non-materialized and expand JIT releases
    rel_res = client.get(
        "/api/sources/releases?imdb_id=tt0816692&source=yify&live=auto&title=Interstellar"
    )
    assert rel_res.status_code == 200
    assert rel_res.json()["total"] == 2
    assert route.call_count == 2


@respx.mock
def test_cross_db_self_heal_and_strict_6_tier_waterfall(hydration_client, monkeypatch):
    """Verify Cross-DB EZTV<->mainstream self-heal and non-destructive 6-tier coalesce."""
    _client, main_engine, src_engine = hydration_client
    monkeypatch.setenv("TMDB_API_KEY", "dummy_tmdb_v3_key")

    with Session(main_engine) as ms, Session(src_engine) as ss:
        # 1) Case A: EZTV has poster/synopsis, mainstream lacks it; EZTV orphan gets IMDb synopsis
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt0903747",
                title_type="tvSeries",
                primary_title="Breaking Bad",
                start_year=2008,
                genres="Crime,Drama",
                rating_votes=2000000,
                poster_url=None,
                synopsis=None,
                synopsis_ptbr="Sinopse PT-BR pré-existente protegida contra sobrescrita.",
            )
        )
        ss.add(
            EZTVShow(
                id=10,
                slug="breaking-bad",
                name="Breaking Bad",
                imdb_id="tt0903747",
                poster_url="https://eztv.example/bb.jpg",
                synopsis="A high school chemistry teacher diagnosed with cancer.",
            )
        )
        # 2) Case B: Movie missing poster & synopses, hits Tier 5 YTS + Tier 6 Wikidata/Wiki PT-BR
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt1160419",
                title_type="movie",
                primary_title="Dune",
                start_year=2021,
                genres="Sci-Fi,Adventure",
                rating_votes=850000,
                details_fetched=0,
            )
        )
        # 3) Case C: Orphan with zero results anywhere -> marked details_fetched = -1
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt9999999",
                title_type="movie",
                primary_title="Unknown Film XYZ",
                start_year=1990,
                genres="Drama",
                rating_votes=500,
                details_fetched=0,
            )
        )
        ms.commit()
        ss.commit()

        respx.get("https://www.imdb.com/title/tt0903747/").mock(return_value=httpx.Response(404))
        respx.get("https://www.imdb.com/title/tt1160419/").mock(return_value=httpx.Response(404))
        respx.get("https://www.imdb.com/title/tt9999999/").mock(return_value=httpx.Response(404))

        respx.get("https://api.themoviedb.org/3/find/tt0903747").mock(
            return_value=httpx.Response(200, json={"movie_results": [], "tv_results": []})
        )
        respx.get("https://api.themoviedb.org/3/find/tt1160419").mock(
            return_value=httpx.Response(200, json={"movie_results": [], "tv_results": []})
        )
        respx.get("https://api.themoviedb.org/3/find/tt9999999").mock(
            return_value=httpx.Response(200, json={"movie_results": [], "tv_results": []})
        )
        respx.get("https://api.tvmaze.com/lookup/shows").mock(return_value=httpx.Response(404))

        respx.get("https://movies-api.accel.li/api/v2/movie_details.json").mock(
            side_effect=lambda req: (
                httpx.Response(
                    200,
                    json={
                        "data": {
                            "movie": {
                                "id": 77,
                                "large_cover_image": "https://yts.example/dune_large.jpg",
                                "description_full": (
                                    "Paul Atreides leads nomadic tribes in Arrakis."
                                ),
                                "yt_trailer_code": "8g18jFHCLXk",
                            }
                        }
                    },
                )
                if req.url.params.get("imdb_id") == "tt1160419"
                else httpx.Response(200, json={"data": {"movie": {}}})
            )
        )

        respx.get("https://query.wikidata.org/sparql").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": {
                        "bindings": [
                            {
                                "imdb": {"value": "tt1160419"},
                                "ptTitle": {"value": "Duna (filme de 2021)"},
                            }
                        ]
                    }
                },
            )
        )
        respx.get(
            "https://pt.wikipedia.org/api/rest_v1/page/summary/Duna_%28filme_de_2021%29"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "extract": (
                        "Duna é um filme épico de ficção científica dirigido por Denis Villeneuve."
                    ),
                },
            )
        )

        report = asyncio.run(CascadingMetadataEnricher.enrich_batch(ms, ss, batch_size=10))
        assert report["self_heal"]["eztv_to_mainstream"] == 1
        # Breaking Bad is healed locally in Step 0, leaving Dune & Unknown for 6-tier HTTP
        assert report["processed"] == 2

        bb = ms.get(IMDbCatalogShow, "tt0903747")
        assert bb is not None
        assert bb.poster_url == "https://eztv.example/bb.jpg"
        assert bb.synopsis == "A high school chemistry teacher diagnosed with cancer."
        # Pre-existing synopsis_ptbr MUST remain untouched (RT15-02)
        assert bb.synopsis_ptbr == "Sinopse PT-BR pré-existente protegida contra sobrescrita."
        assert bb.details_fetched == 1

        dune = ms.get(IMDbCatalogShow, "tt1160419")
        assert dune is not None
        assert dune.poster_url == "https://yts.example/dune_large.jpg"
        assert "Arrakis" in (dune.synopsis or "")
        assert "Denis Villeneuve" in (dune.synopsis_ptbr or "")
        assert dune.details_fetched == 1

        orphan = ms.get(IMDbCatalogShow, "tt9999999")
        assert orphan is not None
        assert orphan.details_fetched == -1


@respx.mock
def test_hydration_endpoints_and_nyaa_bilingual_sweep(hydration_client):
    """Verify REST /api/explore/hydration/* console routes & Nyaa anime sweep cursor."""
    client, main_engine, src_engine = hydration_client

    # Verify Nyaa parenthesized bilingual anime title confidence
    conf = compute_title_match_confidence(
        query_title="Attack on Titan",
        query_original_title="Shingeki no Kyojin",
        query_year=2013,
        query_work_type="tvSeries",
        candidate_title="[SubsPlease] Shingeki no Kyojin (Attack on Titan) - 01 [1080p]",
    )
    assert conf >= 0.85

    with Session(main_engine) as ms, Session(src_engine) as ss:
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt2560140",
                title_type="tvSeries",
                primary_title="Attack on Titan",
                original_title="Shingeki no Kyojin",
                start_year=2013,
                genres="Action,Adventure,Animation",
                rating_votes=550000,
                poster_url="https://example.org/aot.jpg",
                synopsis="Eren fights Titans.",
                synopsis_ptbr="Eren luta contra Titãs.",
            )
        )
        ms.commit()
        SourcesRegistryService.ensure_sources_registered(ss)

        # Mock Nyaa direct fallback RSS search response
        respx.get("https://nyaa.si/").mock(
            return_value=httpx.Response(
                200,
                text="""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:nyaa="https://nyaa.si/xmlns/nyaa">
  <channel>
    <item>
      <title>[SubsPlease] Shingeki no Kyojin (Attack on Titan) - S01E01 [1080p]</title>
      <link>https://nyaa.si/download/12345.torrent</link>
      <guid>https://nyaa.si/view/12345</guid>
      <nyaa:infoHash>cccccccccccccccccccccccccccccccccccccccc</nyaa:infoHash>
      <nyaa:seeders>95</nyaa:seeders>
      <nyaa:leechers>12</nyaa:leechers>
      <nyaa:size>1.4 GiB</nyaa:size>
    </item>
  </channel>
</rss>""",
            )
        )
        # Sidecar offline simulation for sweep
        respx.get("http://127.0.0.1:8009/api/v1/search").mock(
            side_effect=httpx.ConnectError("sidecar offline")
        )
        sw = asyncio.run(
            SourcesRegistryService.sweep_canonical_catalog_presence(
                ss, ms, source_key="nyaasi", offset=0, batch_size=5
            )
        )
        assert sw["titles_scanned"] == 1
        assert sw["titles_matched"] == 1
        assert sw["releases_indexed"] == 1
        assert sw["next_offset"] == 1

    # Exercise /api/explore/hydration/* endpoints
    st = client.get("/api/explore/hydration/status")
    assert st.status_code == 200
    assert st.json()["sources"]["nyaasi"]["titles_indexed"] == 1

    start_res = client.post("/api/explore/hydration/start?scope=sources")
    assert start_res.status_code == 200
    assert start_res.json()["state"] == "RUNNING"
    assert len(start_res.json()["recent_events"]) >= 1

    # Simulate live telemetry step on metadata
    respx.get("https://www.imdb.com/title/tt2560140/").mock(return_value=httpx.Response(404))
    step_res = client.post("/api/explore/hydration/step?scope=metadata&meta_batch=2")
    assert step_res.status_code == 200
    step_status = step_res.json()["status"]
    assert "elapsed_seconds" in step_status
    assert "total_elapsed_seconds" in step_status
    assert "rate_per_minute" in step_status
    assert "sources_eta_seconds" in step_status
    assert "metadata_eta_seconds" in step_status
    assert isinstance(step_status["recent_events"], list)
    assert step_status["recent_events"][0]["stage"] == "metadata"

    pause_res = client.post("/api/explore/hydration/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["state"] == "PAUSED"
    assert pause_res.json()["current_target"] is None

    reset_res = client.post("/api/explore/hydration/reset-cursor?target=yify")
    assert reset_res.status_code == 200
    assert reset_res.json()["sources"]["yify"]["next_page"] == 1


@respx.mock
def test_sidecar_422_and_exhaustion_transitions_to_sweep(hydration_client):
    """Verify page>20 on sidecar returns 200 empty and 422 from external sidecar triggers sweep."""
    from src.backend.providers.sources.torrent_api_py_adapter import TorrentApiPySourceAdapter
    from src.backend.sidecar.torrent_api_sidecar import sidecar_app

    # 1. Embedded sidecar_app accepts page=21 cleanly without 422
    sc_client = TestClient(sidecar_app)
    r_sc = sc_client.get("/api/v1/recent?site=nyaasi&page=21")
    assert r_sc.status_code == 200
    assert r_sc.json()["exhausted"] is True
    assert r_sc.json()["data"] == []

    # 2. Adapter treats external 422 gracefully as empty -> exhausted=True
    _client, _main_e, src_e = hydration_client
    with Session(src_e) as ss:
        SourcesRegistryService.ensure_sources_registered(ss)
        nyaa = ss.get(ExternalSourceRecord, "nyaasi")
        assert nyaa is not None
        respx.get("http://127.0.0.1:8009/api/v1/recent").mock(
            return_value=httpx.Response(422, json={"detail": "page > 20"})
        )
        cands = asyncio.run(
            TorrentApiPySourceAdapter().fetch_recent_candidates(nyaa, pages=1, start_page=21)
        )
        assert cands == []


@respx.mock
def test_domain_semaphore_loop_isolation_and_parallel_fanout(hydration_client, monkeypatch):
    """Verify WeakKeyDictionary semaphores across loops and parallel Fan-out -> Fan-in."""
    from src.backend.core.domain_concurrency import DomainSemaphoreRegistry

    reg = DomainSemaphoreRegistry(limits={"tmdb": 4})

    async def _grab_sem():
        return reg.get("tmdb")

    s1 = asyncio.run(_grab_sem())
    s2 = asyncio.run(_grab_sem())
    assert s1 is not s2

    _client, main_e, src_e = hydration_client
    monkeypatch.setenv("TMDB_API_KEY", "dummy_tmdb_key")
    with Session(main_e) as ms, Session(src_e) as ss:
        for i in range(6):
            ms.add(
                IMDbCatalogShow(
                    imdb_id=f"tt700000{i}",
                    title_type="movie",
                    primary_title=f"Parallel Movie {i}",
                    start_year=2023,
                    genres="Action",
                    rating_votes=50000 - i,
                    details_fetched=0,
                )
            )
        ms.commit()

        respx.get(url__regex=r"https://www\.imdb\.com/title/tt700000\d/").mock(
            return_value=httpx.Response(404)
        )
        respx.get(url__regex=r"https://api\.themoviedb\.org/3/find/tt700000\d").mock(
            return_value=httpx.Response(
                200,
                json={
                    "movie_results": [
                        {
                            "id": 4242,
                            "title": "Filme Paralelo",
                            "overview": "Sinopse em português preenchida via Fan-out.",
                            "poster_path": "/parallel.jpg",
                        }
                    ],
                    "tv_results": [],
                },
            )
        )
        respx.get("https://api.themoviedb.org/3/movie/4242").mock(
            return_value=httpx.Response(
                200,
                json={
                    "overview": "English overview fetched concurrently.",
                    "status": "Released",
                },
            )
        )

        report = asyncio.run(CascadingMetadataEnricher.enrich_batch(ms, ss, batch_size=6))
        assert report["processed"] == 6
        assert report["updated"] == 6
        assert report["provenance"]["tmdb"] == 6


def test_adr018_telemetry_skip_recent_and_imdb_admin(hydration_client, monkeypatch) -> None:
    """ADR-018: Mainstream coverage, EMA, 0-of-0 suppression, skip-recent, and IMDb endpoints."""
    client, main_e, _src_e = hydration_client
    monkeypatch.setenv("TMDB_API_KEY", "dummy_tmdb_key")

    with Session(main_e) as ms:
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt8100001",
                title_type="movie",
                primary_title="Mainstream Movie",
                start_year=2022,
                tmdb_id=101,
                poster_url="https://img.example/m.jpg",
                synopsis="Complete movie.",
                synopsis_ptbr="Filme completo.",
                details_fetched=1,
            )
        )
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt8100002",
                title_type="tvSeries",
                primary_title="Mainstream Series",
                start_year=2023,
                tvmaze_id=202,
                poster_url="https://img.example/s.jpg",
                synopsis="Complete series.",
                synopsis_ptbr="Série completa.",
                details_fetched=1,
            )
        )
        ms.commit()

    st_res = client.get("/api/explore/hydration/status")
    assert st_res.status_code == 200
    cov = st_res.json()["coverage"]
    assert cov["total_shows"] == 2
    assert cov["with_tmdb_id"] == 1
    assert cov["tmdb_pct"] == 50.0
    assert cov["series_total"] == 1
    assert cov["series_with_tvmaze_id"] == 1
    assert cov["tvmaze_pct"] == 100.0
    assert cov["tmdb_configured"] is True

    # Step on empty metadata queue should silence repeated 0-of-0 events
    step1 = client.post("/api/explore/hydration/step?scope=metadata")
    assert step1.status_code == 200
    assert step1.json()["status"]["metadata_batches_executed"] == 0
    step2 = client.post("/api/explore/hydration/step?scope=metadata")
    assert step2.status_code == 200
    events = step2.json()["status"]["recent_events"]
    zero_msgs = [e for e in events if "0 de 0" in e["message"]]
    assert len(zero_msgs) == 0

    # Manual skip-recent advances Sidecar cursor into sweep mode
    skip_res = client.post("/api/explore/hydration/sources/nyaasi/skip-recent")
    assert skip_res.status_code == 200
    assert skip_res.json()["sources"]["nyaasi"]["recent_exhausted"] is True

    # IMDb admin endpoints (Bloco 2)
    imdb_st = client.get("/api/explore/imdb/status")
    assert imdb_st.status_code == 200
    assert imdb_st.json()["state"] in ("IDLE", "COMPLETED")

    imdb_sync = client.post("/api/explore/imdb/sync?include_episodes=false")
    assert imdb_sync.status_code == 200
    assert imdb_sync.json()["state"] == "COMPLETED"

    imdb_fts = client.post("/api/explore/imdb/reindex-fts")
    assert imdb_fts.status_code == 200
    assert imdb_fts.json()["state"] == "COMPLETED"


@respx.mock
def test_adr020_run_mode_novidades_varredura_and_config(hydration_client) -> None:
    """ADR-020: finite run_mode='novidades', varredura skipping DELTA, and /hydration/config."""
    client, main_e, _src_e = hydration_client

    with Session(main_e) as ms:
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt8200001",
                title_type="movie",
                primary_title="Popular Movie",
                start_year=2024,
                rating_votes=2500,
                poster_url="https://img.example/p1.jpg",
                synopsis="S1",
                synopsis_ptbr="S1 PT",
                details_fetched=1,
            )
        )
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt8200002",
                title_type="movie",
                primary_title="Niche Movie",
                start_year=2024,
                rating_votes=150,
                poster_url="https://img.example/p2.jpg",
                synopsis="S2",
                synopsis_ptbr="S2 PT",
                details_fetched=1,
            )
        )
        ms.commit()

    # Check vote_tier_counts in coverage
    st_res = client.get("/api/explore/hydration/status")
    assert st_res.status_code == 200
    tiers = st_res.json()["coverage"]["vote_tier_counts"]
    assert tiers["0"] == 2
    assert tiers["100"] == 2
    assert tiers["1000"] == 1
    assert tiers["5000"] == 0

    # Update config via POST /api/explore/hydration/config
    cfg_res = client.post(
        "/api/explore/hydration/config",
        json={
            "sweep_min_votes": 100,
            "sweep_enabled_sources": ["tgx"],
            "recent_pages_per_source": 3,
        },
    )
    assert cfg_res.status_code == 200
    cfg_data = cfg_res.json()
    assert cfg_data["sweep_min_votes"] == 100
    assert cfg_data["sweep_enabled_sources"] == ["tgx"]
    assert cfg_data["recent_pages_per_source"] == 3
    assert cfg_data["sources"]["tgx"]["sweep_total"] == 2

    # Mock YTS & Sidecar recent for 1 finite novidades step -> COMPLETED
    respx.get(url__regex=r"https://.*/api/v2/list_movies\.json.*").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "data": {"movie_count": 0, "movies": []}}
        )
    )
    respx.get(url__regex=r"http://127\.0\.0\.1:8009/api/v1/recent.*").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    nov_start = client.post("/api/explore/hydration/start?scope=all&run_mode=novidades")
    assert nov_start.status_code == 200
    assert nov_start.json()["run_mode"] == "novidades"

    nov_step = client.post("/api/explore/hydration/step?scope=all")
    assert nov_step.status_code == 200
    nov_st = nov_step.json()["status"]
    assert nov_st["state"] == "COMPLETED"
    assert nov_st["last_novidades_at"] is not None
