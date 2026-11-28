"""Integration & unit tests for ADR-021 (IMDb 2-stage, EZTV watermark, Feed, Prefs v2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import src.backend.models  # noqa: F401
from src.backend.core.database import get_eztv_session, get_session
from src.backend.main import app
from src.backend.models.catalog_domain import IMDbCatalogShow, imdb_metadata
from src.backend.models.db import ShowRecord
from src.backend.models.eztv_db import EZTVShow, eztv_metadata
from src.backend.models.sources_db import ExternalRelease, ExternalSourceRecord, sources_metadata
from src.backend.repositories.preferences import ExplorePreferencesRepository
from src.backend.services.catalog_indexer import EZTVIndexerService
from src.backend.services.imdb_sync_service import IMDbCanonicalSyncService
from src.backend.services.sources_registry import SourcesRegistryService


@pytest.fixture
def adr021_engines():
    ms_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    src_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(ms_engine)
    imdb_metadata.create_all(ms_engine)
    SQLModel.metadata.create_all(src_engine)
    eztv_metadata.create_all(src_engine)
    sources_metadata.create_all(src_engine)

    with Session(ms_engine) as ms:
        # Seed 35 diverse IMDbCatalogShow items across movies, running series, sci-fi, crime
        for i in range(1, 36):
            is_series = i % 2 == 0
            genre = (
                "Crime, Mystery"
                if i % 3 == 0
                else ("Sci-Fi, Thriller" if i % 5 == 0 else "Drama, Action")
            )
            ms.add(
                IMDbCatalogShow(
                    imdb_id=f"tt900{i:04d}",
                    imdb_num=9000000 + i,
                    title_type="tvSeries" if is_series else "movie",
                    primary_title=f"Sample Work {i}",
                    title_ptbr=f"Obra Exemplo {i}",
                    start_year=2024 if i <= 20 else 2019,
                    status="Running" if is_series else "Released",
                    genres=genre,
                    rating_score=7.2 + (i % 20) * 0.1,
                    rating_votes=1500 + i * 250,
                    poster_url=f"https://img.example.com/p{i}.jpg",
                    backdrop_url=f"https://img.example.com/b{i}.jpg",
                    has_eztv=(i % 4 == 0),
                )
            )
        ms.add(
            ShowRecord(
                tmdb_id=9000003,
                imdb_id="tt9000003",
                title="Nocturne",
                genres="Crime & Investigação, Suspense",
                rating=8.8,
                user_status="watching",
            )
        )
        ms.commit()

    with Session(src_engine) as ss:
        ss.add(
            ExternalSourceRecord(
                source_key="eztv",
                display_name="EZTV",
                kind="torrent_api",
                media_types="tvSeries",
                enabled=True,
                status="ready",
            )
        )
        ss.commit()

    return ms_engine, src_engine


@pytest.fixture
def adr021_client(adr021_engines):
    ms_engine, src_engine = adr021_engines

    def _override_ms():
        with Session(ms_engine) as s:
            yield s

    def _override_src():
        with Session(src_engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_ms
    app.dependency_overrides[get_eztv_session] = _override_src
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_preferences_v1_to_v2_migration(adr021_client: TestClient):
    res = adr021_client.put(
        "/api/explore/preferences",
        json={
            "schema_version": 1,
            "badge_provider_action": "open_details",
            "badge_media_action": "filter_has_media",
            "auto_apply_filters": True,
            "show_all_genres": True,
            "filter_panel_expanded": False,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["schema_version"] == 2
    assert body["auto_apply_filters"] is True
    assert len(body["smart_lists"]) >= 10
    assert body["discovery_variance_pct"] == 45


def test_discovery_feed_deduplication_and_impressions(adr021_client: TestClient):
    r1 = adr021_client.get(
        "/api/explore/feed?session_seed=seedA&roulette_scope=all&roulette_spin=0"
    )
    assert r1.status_code == 200
    data = r1.json()
    assert len(data["hero_pool"]) > 0
    assert len(data["roulette"]) == 3
    assert len(data["smart_lists"]) == 10

    # Collect all imdb_ids across hero, roulette and all smart lists -> must be 100% unique
    all_ids: list[str] = []
    for h in data["hero_pool"]:
        all_ids.append(h["imdb_id"])
    for ro in data["roulette"]:
        all_ids.append(ro["imdb_id"])
    for sl in data["smart_lists"]:
        for it in sl["items"]:
            all_ids.append(it["imdb_id"])
    assert len(all_ids) == len(set(all_ids))

    # Record impression on first hero item
    first_hero_id = data["hero_pool"][0]["imdb_id"]
    imp_res = adr021_client.post(
        "/api/explore/impressions",
        json={"imdb_ids": [first_hero_id], "surface": "hero"},
    )
    assert imp_res.status_code == 200
    assert imp_res.json()["recorded"] == 1

    # Second GET on a fresh Session must hit cache without DetachedInstanceError
    r2 = adr021_client.get(
        "/api/explore/feed?session_seed=seedB&roulette_scope=movie&roulette_spin=1"
    )
    assert r2.status_code == 200
    assert len(r2.json()["smart_lists"]) == 10


@pytest.mark.asyncio
async def test_eztv_watermark_dual_write_and_counters(adr021_engines):
    ms_engine, src_engine = adr021_engines

    mag = "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    class _FakeEZTVIndexer(EZTVIndexerService):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def fetch_page(self, page: int = 1, limit: int = 100) -> list[dict]:
            self.calls += 1
            if page == 1:
                return [
                    {
                        "id": 5001,
                        "imdb_id": "9000002",
                        "title": "Sample Work 2 S01E01 1080p WEB",
                        "filename": "Sample.Work.2.S01E01.1080p.mkv",
                        "season": "1",
                        "episode": "1",
                        "magnet_url": mag,
                        "seeds": 25,
                        "peers": 4,
                        "size_bytes": 1024000,
                        "date_released_unix": 1795836000,
                    }
                ]
            # Page 2 and 3 return already-known id=5001 -> triggers 2 consecutive known pages stop
            return [
                {
                    "id": 5001,
                    "imdb_id": "9000002",
                    "title": "Sample Work 2 S01E01 1080p WEB",
                    "filename": "Sample.Work.2.S01E01.1080p.mkv",
                    "season": "1",
                    "episode": "1",
                    "magnet_url": mag,
                    "seeds": 25,
                    "peers": 4,
                    "size_bytes": 1024000,
                    "date_released_unix": 1795836000,
                }
            ]

    indexer = _FakeEZTVIndexer()
    with Session(src_engine) as ss, Session(ms_engine) as ms:
        res = await indexer.sync_pages_until_watermark(
            session=ss,
            mainstream_session=ms,
            max_pages=25,
            stop_on_known_pages=2,
            request_delay=0.0,
        )
        assert res["pages_processed"] == 3
        assert res["torrents_indexed"] == 1

        # Verify ExternalRelease & EZTVShow dual-write
        ext = ss.exec(
            select(ExternalRelease).where(
                ExternalRelease.source_key == "eztv",
                ExternalRelease.external_id == "5001",
            )
        ).first()
        assert ext is not None
        assert ss.exec(select(EZTVShow).where(EZTVShow.imdb_id == "tt9000002")).first() is not None

        # Verify _recompute_source_counters updates eztv instead of skipping it
        SourcesRegistryService._recompute_source_counters(ss)
        ez_rec = ss.get(ExternalSourceRecord, "eztv")
        assert ez_rec is not None
        assert ez_rec.total_releases == 1
        assert ez_rec.total_titles == 1


@pytest.mark.asyncio
async def test_imdb_sync_service_pytest_isolation(adr021_engines):
    ms_engine, _ = adr021_engines
    svc = IMDbCanonicalSyncService()
    with Session(ms_engine) as ms:
        ExplorePreferencesRepository._ensure_sync_state_table(ms)
        st = await svc.start_sync(ms, include_episodes=False)
        assert st.state == "COMPLETED"
        assert st.works_processed == 0


def test_global_foreign_titles_and_parental_control(adr021_client: TestClient, adr021_engines):
    ms_engine, _ = adr021_engines
    with Session(ms_engine) as ms:
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt9900001",
                imdb_num=9900001,
                title_type="movie",
                primary_title="French Film",
                start_year=2025,
                genres="Drama",
                languages="Français",
                countries="FR",
                rating_score=8.5,
                rating_votes=9000,
                poster_url="https://img.example.com/fr.jpg",
                backdrop_url="https://img.example.com/frb.jpg",
            )
        )
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt9900002",
                imdb_num=9900002,
                title_type="movie",
                primary_title="Spanish Hit",
                start_year=2025,
                genres="Drama",
                languages="Español",
                countries="ES",
                rating_score=8.5,
                rating_votes=9000,
                poster_url="https://img.example.com/es.jpg",
                backdrop_url="https://img.example.com/esb.jpg",
            )
        )
        ms.add(
            IMDbCatalogShow(
                imdb_id="tt9900003",
                imdb_num=9900003,
                title_type="animation",
                primary_title="Kids Cartoon",
                start_year=2025,
                genres="Animation, Kids",
                languages="English",
                countries="US",
                rating_score=8.5,
                rating_votes=9000,
                poster_url="https://img.example.com/anim.jpg",
                backdrop_url="https://img.example.com/animb.jpg",
            )
        )
        ms.commit()

    # Default: foreign_titles_mode='off', parental_control_enabled=True
    w_off = adr021_client.get("/api/explore/works?page_size=100").json()["items"]
    titles_off = {w["title"] for w in w_off}
    assert "French Film" not in titles_off
    assert "Spanish Hit" not in titles_off
    assert "Kids Cartoon" not in titles_off

    # Lite + Parental Control enabled
    adr021_client.put(
        "/api/explore/preferences",
        json={"foreign_titles_mode": "lite", "parental_control_enabled": True},
    )
    w_lite = adr021_client.get("/api/explore/works?page_size=100").json()["items"]
    titles_lite = {w["title"] for w in w_lite}
    assert "Spanish Hit" in titles_lite
    assert "French Film" not in titles_lite
    assert "Kids Cartoon" not in titles_lite

    # Also verify feed respects parental control
    feed_pc = adr021_client.get("/api/explore/feed?session_seed=pc1").json()
    feed_titles = {
        it["title"] for sl in feed_pc["smart_lists"] for it in sl["items"]
    } | {h["title"] for h in feed_pc["hero_pool"]}
    assert "Kids Cartoon" not in feed_titles

    # All languages + Parental Control off
    adr021_client.put(
        "/api/explore/preferences",
        json={"foreign_titles_mode": "all", "parental_control_enabled": False},
    )
    w_all = adr021_client.get("/api/explore/works?page_size=100").json()["items"]
    titles_all = {w["title"] for w in w_all}
    assert "French Film" in titles_all
    assert "Spanish Hit" in titles_all
    assert "Kids Cartoon" in titles_all
