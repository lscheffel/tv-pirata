"""Unit and integration tests for ADR-010 dual-SQLite performance optimizations."""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from src.backend.core.cache import catalog_cache, discovery_cache
from src.backend.core.database import get_engine, get_eztv_engine, init_db, init_eztv_db
from src.backend.models.db import CatalogShow
from src.backend.models.eztv_db import EZTVEpisodeCatalog, EZTVShow
from src.backend.repositories.catalog import CatalogRepository
from src.backend.repositories.discovery_engine import DiscoveryEngineRepository
from src.backend.services.federated_catalog import FederatedCatalogService


def test_sqlite_pragmas_configured_on_connect(tmp_path) -> None:
    """Verify DEC-001: SQLite connections configure WAL, synchronous=NORMAL, and 64MB cache."""
    db_file = tmp_path / "pragma_check.db"
    eng = get_engine(f"sqlite:///{db_file}")
    init_db(eng)
    with eng.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        synchronous = conn.execute(text("PRAGMA synchronous")).scalar()
        temp_store = conn.execute(text("PRAGMA temp_store")).scalar()
        cache_size = conn.execute(text("PRAGMA cache_size")).scalar()

    assert str(journal_mode).lower() == "wal"
    assert int(synchronous) == 1  # NORMAL = 1
    assert int(temp_store) == 2  # MEMORY = 2
    assert int(cache_size) == -64000


def test_materialized_episode_stats_and_fts5_search(tmp_path) -> None:
    """Verify DEC-002 and DEC-006: init_eztv_db backfills episode stats and enables FTS5 search."""
    eztv_file = tmp_path / "eztv_perf.db"
    main_file = tmp_path / "main_perf.db"
    ez_eng = get_eztv_engine(f"sqlite:///{eztv_file}")
    main_eng = get_engine(f"sqlite:///{main_file}")

    init_eztv_db(ez_eng)
    init_db(main_eng)

    with Session(ez_eng) as ez_s:
        show = EZTVShow(
            id=101,
            slug="the-lord-of-the-rings-the-rings-of-power",
            name="The Lord of the Rings: The Rings of Power",
            imdb_id="tt7631058",
            status="Running",
            rating_score=7.1,
            genres="Action, Adventure, Fantasy",
            network="Prime Video",
            streaming_providers="Prime Video",
            episodes_count=0,
        )
        ez_s.add(show)
        ez_s.commit()

        ez_s.add_all(
            [
                EZTVEpisodeCatalog(show_id=101, season=1, episode=1, title="A Shadow of the Past"),
                EZTVEpisodeCatalog(show_id=101, season=2, episode=8, title="Shadow and Flame"),
            ]
        )
        ez_s.commit()

    # Running init_eztv_db backfills episodes_count, max_season, max_episode
    init_eztv_db(ez_eng)

    with Session(ez_eng) as ez_s, Session(main_eng) as main_s:
        main_s.add(
            CatalogShow(
                imdb_id="tt7631058",
                title="The Lord of the Rings: The Rings of Power",
                max_seeds=500,
                total_torrents=16,
                latest_season=2,
                latest_episode=8,
            )
        )
        main_s.commit()

        refreshed = ez_s.get(EZTVShow, 101)
        assert refreshed is not None
        assert refreshed.episodes_count == 2
        assert refreshed.max_season == 2
        assert refreshed.max_episode == 8

        # Verify FTS5 prefix search works and handles punctuation safely
        items, total = CatalogRepository.list_shows(
            eztv_session=ez_s,
            p2p_session=main_s,
            search="Rings Power",
            sort_by="seeds",
        )
        assert total == 1
        assert items[0]["eztv_show_id"] == 101
        assert items[0]["episodes_count"] == 2

        # Verify curated sections single-pass + cache coherence on mutation
        sections_1 = CatalogRepository.get_curated_sections(ez_s, main_s)
        assert any(sec["id"] == "top_p2p" for sec in sections_1)

        ez_s.add(
            EZTVShow(
                id=102,
                slug="mobland",
                name="MobLand",
                imdb_id="tt31510819",
                status="Running",
                rating_score=8.1,
                genres="Crime, Drama",
                episodes_count=5,
                max_season=1,
                max_episode=5,
                updated_at="2026-11-14T00:00:00Z",
            )
        )
        ez_s.commit()

        # Fingerprint automatically invalidates stale section cache when show count changes
        sections_2 = CatalogRepository.get_curated_sections(ez_s, main_s)
        top_items = next(sec["items"] for sec in sections_2 if sec["id"] == "top_p2p")
        assert len(top_items) == 2


def test_discovery_seeded_guard_and_snapshot_cache() -> None:
    """Verify DEC-003 and DEC-005: _ensure_seeded guard avoids redundant work on warm engine."""
    catalog_cache.invalidate()
    discovery_cache.invalidate()
    main_eng = get_engine("sqlite:///:memory:")
    ez_eng = get_eztv_engine("sqlite:///:memory:")
    init_db(main_eng)
    init_eztv_db(ez_eng)

    svc = FederatedCatalogService()
    with Session(main_eng) as s, Session(ez_eng) as ez_s:
        first_seed = svc.ensure_federated_catalog_seeded(s)
        assert first_seed["seeded_works"] > 0

        # Second call on same engine with unchanged counts returns 0 seeded/bridged in O(1)
        second_seed = svc.ensure_federated_catalog_seeded(s)
        assert second_seed["seeded_works"] == 0
        assert second_seed["bridged_local_works"] == 0

        res1 = DiscoveryEngineRepository.query_works(s, ez_s, page=1, page_size=10)
        res2 = DiscoveryEngineRepository.query_works(s, ez_s, page=1, page_size=10)
        assert res1["total"] == res2["total"]
        assert res1["total"] > 0
