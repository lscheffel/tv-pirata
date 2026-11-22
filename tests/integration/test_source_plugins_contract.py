"""Universal contract & integration tests for ADR-013 source plugins ecosystem."""

from __future__ import annotations

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
from src.backend.models.sources_db import ExternalRelease
from src.backend.providers.sources import discover_source_adapters
from src.backend.providers.sources.base import (
    OFFICIAL_YTS_TRACKERS,
    build_official_magnet,
    compute_title_match_confidence,
    merge_preserving_secrets,
    validate_safe_url,
)
from src.backend.providers.sources.eztv_adapter import EZTVSourceAdapter
from src.backend.providers.sources.torrent_api_py_adapter import TORRENT_API_PY_SITE_CATALOG
from src.backend.sidecar import sidecar_app


@pytest.fixture
def plugin_client():
    """Create isolated mainstream & sources in-memory SQLite engines for plugin contract tests."""
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
                imdb_id="tt1160419",
                imdb_num=1160419,
                title_type="movie",
                primary_title="Dune",
                original_title="Dune: Part One",
                title_ptbr="Duna",
                start_year=2021,
                genres="Action,Adventure,Sci-Fi",
                genres_ptbr="Ação, Aventura, Ficção Científica",
                rating_score=8.0,
                rating_votes=850000,
                streaming_providers="Max",
                has_eztv=0,
            )
        )
        ms.commit()

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


def test_autodiscovery_and_zero_trust_security_helpers():
    adapters = discover_source_adapters(force=True)
    assert set(adapters.keys()) >= {
        "eztv",
        "yify",
        "torrent_api_py",
        "torznab",
        "unique_web",
    }

    # Strict URI scheme whitelist
    assert validate_safe_url("https://yts.mx/api") == "https://yts.mx/api"
    assert validate_safe_url("magnet:?xt=urn:btih:123456") == "magnet:?xt=urn:btih:123456"
    assert validate_safe_url("javascript:alert(1)") is None
    assert validate_safe_url("data:text/html,<script>") is None
    assert validate_safe_url("file:///etc/passwd") is None

    # Sentinel secret preservation (RT13-02)
    existing = {"base_url": "http://127.0.0.1:9696/1/api", "api_key": "super_secret_token_9999"}
    merged = merge_preserving_secrets(
        existing,
        {"base_url": "http://127.0.0.1:9696/2/api", "api_key": "••••9999"},
        {"api_key"},
    )
    assert merged["api_key"] == "super_secret_token_9999"
    assert merged["base_url"] == "http://127.0.0.1:9696/2/api"

    # Short/ambiguous title guard (RT13-04)
    high_conf = compute_title_match_confidence(
        query_title="Duna",
        query_original_title="Dune: Part One",
        query_year=2021,
        query_work_type="movie",
        candidate_title="Dune Part One 2021 1080p BluRay",
    )
    assert high_conf >= 0.85

    wrong_year_conf = compute_title_match_confidence(
        query_title="Duna",
        query_original_title="Dune",
        query_year=2021,
        query_work_type="movie",
        candidate_title="Dune 1984 1080p BluRay",
    )
    assert wrong_year_conf < 0.85


def test_dynamic_instance_crud_and_secret_masking(plugin_client):
    client, _main_e, _src_e = plugin_client

    adp_res = client.get("/api/sources/adapters")
    assert adp_res.status_code == 200
    adapter_keys = {a["adapter_key"] for a in adp_res.json()["adapters"]}
    assert {"eztv", "yify", "torrent_api_py", "torznab", "unique_web"} <= adapter_keys

    # Create a Torznab instance with secret api_key
    create_res = client.post(
        "/api/sources",
        json={
            "adapter_key": "torznab",
            "source_key": "prowlarr_hd",
            "display_name": "Prowlarr HD",
            "source_kind": "torrent_mirrorable",
            "config": {
                "base_url": "http://127.0.0.1:9696/1/api",
                "api_key": "my_secret_prowlarr_key",
                "categories": "2000,5000",
            },
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["source_key"] == "prowlarr_hd"
    assert created["config"]["api_key"] == "••••_key"
    assert created["config"]["api_key__has_secret"] is True

    # Reject dangerous javascript: base_url
    bad_url_res = client.post(
        "/api/sources",
        json={
            "adapter_key": "unique_web",
            "source_key": "evil_web",
            "display_name": "Evil",
            "config": {"base_url": "javascript:alert(1)"},
        },
    )
    assert bad_url_res.status_code == 400

    # Patch display_name while sending masked api_key -> preserves secret
    patch_res = client.patch(
        "/api/sources/prowlarr_hd",
        json={
            "display_name": "Prowlarr 4K Ultra",
            "config": {
                "base_url": "http://127.0.0.1:9696/1/api",
                "api_key": "••••_key",
            },
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["display_name"] == "Prowlarr 4K Ultra"
    assert patch_res.json()["config"]["api_key"] == "••••_key"

    # Base EZTV cannot be deleted
    del_eztv = client.delete("/api/sources/eztv")
    assert del_eztv.status_code == 400

    del_custom = client.delete("/api/sources/prowlarr_hd")
    assert del_custom.status_code == 200


@respx.mock
def test_lazy_cache_torrent_api_py_torznab_and_captcha_challenge(plugin_client):
    client, _main_e, _src_e = plugin_client

    # Point default tgx instance to mocked sidecar.local:8009 & register a Unique Web Source
    patch_tgx = client.patch(
        "/api/sources/tgx",
        json={
            "display_name": "TorrentGalaxy",
            "config": {"base_url": "http://sidecar.local:8009", "site": "tgx"},
        },
    )
    assert patch_tgx.status_code == 200
    client.post(
        "/api/sources",
        json={
            "adapter_key": "unique_web",
            "source_key": "cinema_ddl",
            "display_name": "Cinema DDL Web",
            "source_kind": "unique_web_source",
            "config": {
                "base_url": "https://ddl.example.org/api/search",
                "browser_search_url": "https://ddl.example.org/search?q={query}",
            },
        },
    )

    # Mock Torrent-Api-py returning 1 high-confidence match (2021), 1 wrong-year match (1984),
    # and 1 malicious javascript: link that must be dropped
    respx.get("http://sidecar.local:8009/api/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": "Dune Part One 2021 1080p BluRay x265",
                        "size": "2.5 GB",
                        "seeders": "410",
                        "leechers": "35",
                        "magnet": "magnet:?xt=urn:btih:dune2021hash1234567890",
                        "url": "https://torrentgalaxy.to/torrent/1",
                    },
                    {
                        "name": "Dune 1984 Classic 720p",
                        "size": "1.1 GB",
                        "seeders": "15",
                        "leechers": "2",
                        "magnet": "magnet:?xt=urn:btih:dune1984hash1234567890",
                    },
                    {
                        "name": "Dune Part One 2021 XSS Payload",
                        "seeders": "999",
                        "url": "javascript:alert('xss')",
                    },
                ]
            },
        )
    )

    # Mock Unique Web Source returning Cloudflare Turnstile 403 Challenge
    respx.get("https://ddl.example.org/api/search").mock(
        return_value=httpx.Response(
            403,
            headers={"server": "cloudflare"},
            text="<html><title>Just a moment...</title><div class='cf-turnstile'></div></html>",
        )
    )

    # 1. Query tgx live -> persists >= 0.85 match into ExternalRelease
    tgx_res = client.get("/api/sources/releases?imdb_id=tt1160419&source=tgx&live=force")
    assert tgx_res.status_code == 200
    tgx_data = tgx_res.json()
    assert tgx_data["total"] == 1
    assert "2021" in tgx_data["items"][0]["title"]
    assert tgx_data["source_diagnostics"]["tgx"]["status"] == "ok"

    # Verify dynamic filter in /api/explore/works recognizes data_sources=tgx without hardcoding!
    exp_res = client.get("/api/explore/works?data_sources=tgx")
    assert exp_res.status_code == 200
    exp_items = exp_res.json()["items"]
    assert len(exp_items) == 1
    assert exp_items[0]["imdb_id"] == "tt1160419"
    assert "tgx" in exp_items[0]["media_sources"]

    # 2. Query unique_web live -> emits challenge_required + safe challenge_url
    ddl_res = client.get("/api/sources/releases?imdb_id=tt1160419&source=cinema_ddl&live=force")
    assert ddl_res.status_code == 200
    ddl_diag = ddl_res.json()["source_diagnostics"]["cinema_ddl"]
    assert ddl_diag["status"] == "challenge_required"
    assert ddl_diag["challenge_url"].startswith("https://ddl.example.org/search?q=")


@respx.mock
def test_adr014_yts_accel_enrichment_eztv_rss_numeric_imdb_and_bipartite_prune(plugin_client):
    client, _main_e, src_e = plugin_client

    # 1. Official 10-tracker magnet builder & 12-site Torrent-Api-py catalog
    assert len(OFFICIAL_YTS_TRACKERS) == 10
    mag = build_official_magnet("f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4b5a6f1e2", "Dune: Part One")
    assert mag is not None
    assert "dn=Dune%3A+Part+One" in mag
    assert mag.count("&tr=") == 10
    assert set(TORRENT_API_PY_SITE_CATALOG.keys()) == {
        "tgx",
        "nyaasi",
        "bitsearch",
        "glodls",
        "magnetdl",
        "limetorrent",
        "torlock",
        "kickass",
        "zooqle",
        "yts",
        "1337x",
        "piratebay",
    }

    # 2. Official EZTV RSS parser & numeric imdb_id lookup without 'tt'
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:torrent="http://xmlns.ezrss.it/0.1/">
      <channel>
        <item>
          <title>Severance S02E01 1080p WEB</title>
          <link>https://eztvx.to/ep/12345</link>
          <torrent:magnetURI>magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</torrent:magnetURI>
        </item>
      </channel>
    </rss>"""
    rss_cands = EZTVSourceAdapter.parse_rss_xml(rss_xml)
    assert len(rss_cands) == 1
    assert rss_cands[0].season == 2
    assert rss_cands[0].episode == 1

    eztv_route = respx.get("https://eztvx.to/api/get-torrents").mock(
        return_value=httpx.Response(
            200,
            json={
                "torrents": [
                    {
                        "id": 7711,
                        "hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "filename": "Game.of.Thrones.S01E01.1080p.mkv",
                        "title": "Game of Thrones S01E01",
                        "imdb_id": "6048596",
                        "season": "1",
                        "episode": "1",
                        "seeds": 220,
                        "peers": 18,
                        "size_bytes": 1500000000,
                        "magnet_url": (
                            "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                        ),
                    }
                ]
            },
        )
    )
    eztv_rel = client.get("/api/sources/releases?imdb_id=tt6048596&source=eztv&live=force")
    assert eztv_rel.status_code == 200
    assert eztv_rel.json()["total"] == 1
    assert eztv_route.calls[0].request.url.params["imdb_id"] == "6048596"

    # 3. Official YTS v2 enrichment (movies-api.accel.li details, suggestions, parental_guides)
    respx.get("https://movies-api.accel.li/api/v2/list_movies.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "movies": [
                        {
                            "id": 9001,
                            "imdb_code": "tt1160419",
                            "title": "Dune",
                            "year": 2021,
                            "rating": 8.0,
                            "rt_critics_score": 83,
                            "torrents": [],
                        }
                    ]
                },
            },
        )
    )
    respx.get("https://movies-api.accel.li/api/v2/movie_details.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "movie": {
                        "id": 9001,
                        "title": "Dune",
                        "year": 2021,
                        "runtime": 155,
                        "mpa_rating": "PG-13",
                        "cast": [{"name": "Timothee Chalamet", "character_name": "Paul Atreides"}],
                    }
                },
            },
        )
    )
    respx.get("https://movies-api.accel.li/api/v2/movie_suggestions.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "movies": [
                        {
                            "id": 9002,
                            "imdb_code": "tt15239678",
                            "title": "Dune: Part Two",
                            "year": 2024,
                            "rating": 8.5,
                        }
                    ]
                },
            },
        )
    )
    respx.get("https://movies-api.accel.li/api/v2/movie_parental_guides.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "data": {
                    "parental_guides": [
                        {"type": "Violence", "parental_guide_text": "Intense sci-fi action"}
                    ]
                },
            },
        )
    )
    yts_intel = client.get("/api/sources/yify/enrichment/tt1160419")
    assert yts_intel.status_code == 200
    intel_json = yts_intel.json()
    assert intel_json["status"] == "ok"
    assert intel_json["details"]["mpa_rating"] == "PG-13"
    assert intel_json["parental_guides"][0]["type"] == "Violence"
    assert intel_json["suggestions"][0]["title"] == "Dune: Part Two"

    # 4. Stage 1 Incremental Recent Sync + Canonical Match + Prune Dead Seeds
    client.patch(
        "/api/sources/tgx",
        json={"config": {"base_url": "http://sidecar.local:8009", "site": "tgx"}},
    )
    respx.get("http://sidecar.local:8009/api/v1/recent").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": "Dune.Part.One.2021.2160p.WEB-DL",
                        "seeders": "150",
                        "leechers": "12",
                        "magnet": "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
                    },
                    {
                        "name": "Dune.Part.One.2021.Dead.Copy",
                        "seeders": "0",
                        "leechers": "0",
                        "magnet": "magnet:?xt=urn:btih:dddddddddddddddddddddddddddddddddddddddd",
                    },
                ]
            },
        )
    )
    sync_recent = client.post("/api/sources/sync?source=tgx&pages=1&mode=incremental")
    assert sync_recent.status_code == 200
    assert sync_recent.json()["results"]["tgx"]["telemetry"]["releases_indexed"] == 1

    # Inject a dead 0-seed row and prune it via /api/sources/prune
    with Session(src_e) as ss:
        ss.add(
            ExternalRelease(
                source_key="tgx",
                external_id="tgx:dead_old",
                imdb_id="tt1160419",
                title="Old Dead Torrent",
                seeds=0,
                magnet_url="magnet:?xt=urn:btih:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            )
        )
        ss.commit()

    # Default prune (48h grace period) keeps fresh 0-seed rows; explicit 0h prunes immediately
    default_prune = client.post("/api/sources/prune?source=tgx")
    assert default_prune.status_code == 200
    assert default_prune.json()["removed_releases"] == 0
    assert default_prune.json()["max_zero_seed_hours"] == 48

    prune_res = client.post("/api/sources/prune?source=tgx&min_seeds_floor=1&max_zero_seed_hours=0")
    assert prune_res.status_code == 200
    assert prune_res.json()["removed_releases"] == 1

    # YIFY persist_sync_candidates skips brand-new 0-seed rows to avoid churn
    from src.backend.providers.sources.base import NormalizedReleaseCandidate
    from src.backend.providers.sources.yify_adapter import YIFYSourceAdapter

    with Session(src_e) as ss:
        idx_y, upd_y = YIFYSourceAdapter.persist_sync_candidates(
            ss,
            "yify",
            [
                NormalizedReleaseCandidate(
                    external_id="yts:presence:tt9990001",
                    imdb_id="tt9990001",
                    title="Dead Movie (2025)",
                    work_type="movie",
                    seeds=0,
                    magnet_url="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                ),
                NormalizedReleaseCandidate(
                    external_id="yts:presence:tt9990002",
                    imdb_id="tt9990002",
                    title="Alive Movie (2025)",
                    work_type="movie",
                    seeds=5,
                    magnet_url="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                ),
            ],
        )
        assert idx_y == 1
        assert upd_y == 0


@respx.mock
def test_adr019_yify_mirror_strategy_series_filter_and_jit_self_heal(plugin_client) -> None:
    """ADR-019: official_first mirrors, valid BTIH + tvSeries exclusion, and JIT self-heal."""
    from sqlmodel import select

    client, main_e, src_e = plugin_client

    from src.backend.providers.sources.yify_adapter import (
        YIFYAdapterConfig,
        YIFYSourceAdapter,
        _is_valid_btih,
    )
    from src.backend.services.sources_registry import SourcesRegistryService

    # 1. mirror_strategy ordering + BTIH validation (40-hex & 32-base32)
    off_urls = YIFYSourceAdapter._candidate_endpoints(
        YIFYAdapterConfig(mirror_strategy="official_first")
    )
    assert off_urls[0].startswith("https://yts.mx")
    acc_urls = YIFYSourceAdapter._candidate_endpoints(
        YIFYAdapterConfig(mirror_strategy="accel_first")
    )
    assert acc_urls[0].startswith("https://movies-api.accel.li")

    assert _is_valid_btih("A" * 40) is True
    assert _is_valid_btih("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") is True
    assert _is_valid_btih("bad-hash") is False

    # 2. tvSeries excluded on Stage 1B persist_sync_candidates & pruned by prune_obsolete_releases
    with Session(main_e) as ms, Session(src_e) as ss:
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt0413550",
                title_type="tvSeries",
                primary_title="CMT Top 20 Countdown",
                start_year=2001,
            )
        )
        ms.commit()
        SourcesRegistryService.ensure_sources_registered(ss)

        raw_cands = YIFYSourceAdapter._movies_to_presence_candidates(
            [
                {
                    "id": 9001,
                    "imdb_code": "tt0413550",
                    "title": "CMT Top 20 Countdown",
                    "year": 2001,
                    "torrents": [
                        {"quality": "720p", "seeds": 10, "peers": 2, "hash": "A" * 40}
                    ],
                },
                {
                    "id": 9002,
                    "imdb_code": "tt1160419",
                    "title": "Dune",
                    "year": 2021,
                    "torrents": [
                        {"quality": "1080p", "seeds": 50, "peers": 10, "hash": "B" * 40}
                    ],
                },
            ]
        )
        idx, _ = YIFYSourceAdapter.persist_sync_candidates(
            ss, "yify", raw_cands, mainstream_session=ms
        )
        assert idx == 1  # tt0413550 (tvSeries) skipped!

        # Inject phantom presence for tt0413550 and verify prune_obsolete_releases removes it
        ss.add(
            ExternalRelease(
                source_key="yify",
                external_id="yts:presence:tt0413550",
                imdb_id="tt0413550",
                title="CMT Top 20 Countdown (2001)",
                seeds=5,
                magnet_url="magnet:?xt=urn:btih:" + ("A" * 40),
            )
        )
        ss.commit()
        prune_res = SourcesRegistryService.prune_obsolete_releases(
            ss, ms, source_key="yify", max_zero_seed_hours=48
        )
        assert prune_res["removed_releases"] >= 1

    # 3. Stage 2 JIT self-heal: empty ok response removes phantom yts:presence:tt1160419
    respx.get(url__regex=r"https://.*/api/v2/list_movies\.json.*").mock(
        return_value=httpx.Response(200, json={"status": "ok", "data": {"movies": []}})
    )
    respx.get(url__regex=r"https://.*/api/v2/movie_details\.json.*").mock(
        return_value=httpx.Response(200, json={"status": "ok", "data": {"movie": {}}})
    )
    jit_res = client.get("/api/sources/releases?imdb_id=tt1160419&source=yify&live=force")
    assert jit_res.status_code == 200
    assert jit_res.json().get("exact", []) == []
    with Session(src_e) as ss:
        rem = ss.exec(
            select(ExternalRelease).where(
                ExternalRelease.source_key == "yify",
                ExternalRelease.imdb_id == "tt1160419",
            )
        ).all()
        assert len(rem) == 0

    # 5. Embedded Torrent-Api-py Sidecar (:8009) contract (/health, /api/v1/sites)
    with TestClient(sidecar_app) as sc:
        h_res = sc.get("/health")
        assert h_res.status_code == 200
        assert h_res.json()["total_sites"] == 12
        sites_res = sc.get("/api/v1/sites")
        assert sites_res.status_code == 200
        assert "tgx" in sites_res.json()["supported_sites"]
