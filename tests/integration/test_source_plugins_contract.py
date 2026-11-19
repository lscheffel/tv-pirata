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
from src.backend.providers.sources import discover_source_adapters
from src.backend.providers.sources.base import (
    compute_title_match_confidence,
    merge_preserving_secrets,
    validate_safe_url,
)


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

    # Register a custom TorrentGalaxy instance (torrent_api_py) & a Unique Web Source
    client.post(
        "/api/sources",
        json={
            "adapter_key": "torrent_api_py",
            "source_key": "tgx",
            "display_name": "TorrentGalaxy",
            "config": {"base_url": "http://sidecar.local:8009", "site": "tgx"},
        },
    )
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
