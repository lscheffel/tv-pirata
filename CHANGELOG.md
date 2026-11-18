# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — ADR-012 (2026-11-17)

### Added
- **Unified `Explorar` Experience & Hybrid Filter Engine (`ADR-012`, `DEC-001`, `DEC-005`):**
  - Merged `Descobrir` and `Explorar Universo` into the unified `Explorar` tab (`Navbar.tsx` reduced to 4 main tabs + dedicated Status/Sync/Config trigger) with Adaptive Mode: renders `HeroBanner`, Quick-Intent bar, 3-item contrastive Roulette (*Roleta de Descoberta*), and curated carousels while idle, collapsing smoothly during search/filtering.
  - Added `RequestAbortChannel` (`AbortController`), `350ms` text debounce, top-10 expandable genre accordion (`show_all_genres`), non-destructive linear progress bar keeping grid mounted, and hybrid `"Aplicar Filtros"` / optional `"Auto-aplicar"` toggle.
- **Multi-Provider `Fontes de Dados` Layer & Unified `MediaBadge` (`DEC-002`):**
  - Added isolated `sources_metadata` models (`ExternalSourceRecord`, `ExternalRelease`) in `src/backend/models/sources_db.py`, polymorphic registry `SourcesRegistryService` (`eztv`, `yify`, `1337x`) in `src/backend/services/sources_registry.py`, and `/api/sources/{summary,releases,catalog,sync}` routes in `src/backend/api/sources.py`, preserving `/api/catalog/*` and `/api/torrents/*` backwards compatibility.
  - Replaced EZTV-coupled catalog UI with multi-provider `SourcesView.tsx` (`Fontes de Dados`), upgraded `EztvBadge.tsx` -> `MediaBadge.tsx`, generalized `TorrentModal.tsx` into provider-tabbed media sources modal, and annotated `/api/explore` & `/api/discovery` with `has_media`, `media_sources`, and `sources_count`.
- **Central `Status, Sincronização & Config` & Hybrid Preferences (`DEC-003`):**
  - Added `GET`/`PUT /api/explore/preferences` backed by `data/mainstream.db` `sync_state` (`ExplorePreferencesRepository`), `preferencesStorage.ts` + `PreferencesContext.tsx`, and `StatusConfigView.tsx` accessed from a `44×44px` gear + health dot button in `Navbar.tsx`.
- **Interactive `ShowCard` Redesign & WCAG 2.2 AA Hardening (`DEC-004`, `DEC-006`):**
  - Refactored `ShowCard.tsx` to stack all normalized streaming `ProviderBadge`s above `StatusBadge` on `>= 190px` posters (condensing automatically to `1 + N` below `190px` on `375px` mobile), display `MediaBadge` below the IMDb rating, support configurable clickable badges (`stopPropagation()` + dynamic `aria-label`/tooltip), and expose a `44×44px` expandable quick-action drawer.
  - Added `:focus-visible` outline and `@media (prefers-reduced-motion: reduce)` in `index.css`, explicit `<label>` on global search in `Navbar.tsx`, and 5 new tests in `tests/integration/test_sources_and_preferences_api.py` (`69 passed`).

---

## [0.7.0] - 2026-11-17

### Added
- **Dual-SSOT Consolidation (`data/mainstream.db` + `data/sources.db`) & SQL Pushdown Engine (ADR-011):**
  - Unified universal IMDb backbone (`279,362` canonical titles in `shows`, `4,529,748` episodes in `episodes_catalog`), TMDB/TVMaze metadata, `MediaWork`, and personal library tables into `data/mainstream.db` (`IMDbCatalogShow`, `IMDbEpisodeCatalog` isolated on `imdb_metadata`), while isolating all EZTV & P2P external resources (`860` series, `140,571` episodes, `CatalogShow`, `CatalogRelease`) in `data/sources.db`.
  - Cross-linked and upserted 100% of `sources.db` records into `mainstream.db` (`has_eztv = 1`, `878` badged titles) via `scripts/sync-eztv-bade.py` and `scripts/sync_canonical_facets_and_providers.py`.
  - Refactored `DiscoveryEngineRepository` (`src/backend/repositories/discovery_engine.py`) with 100% SQL Pushdown pagination, boolean filters, covering B-tree indexes (`idx_shows_filter_cover`, `idx_shows_score_cover`, `idx_shows_facets_cover`), and `GLOBAL_FACETS_V2` precomputed snapshot in `sync_state`, cutting filtered query latency from `1,675.97 ms` to `5.80 ms`.
- **Bilingual (PT-BR & EN-US) FTS5 Search & Exact/Similarity Relevance Ranking:**
  - Added accent-insensitive `shows_fts` (`tokenize='unicode61 remove_diacritics 2'`) with automatic `INSERT`/`DELETE`/`UPDATE` triggers in `data/mainstream.db`.
  - Implemented 3-stage FTS5 retrieval and multi-tier relevance/similarity scoring (`score_title_pair_relevance`, `score_imdb_show_relevance`) across `/api/discovery/search` and `/api/explore/works`, supporting accentless Portuguese and English queries with exact matches ranked first.
- **Canonical Taxonomy, Real BR/US Streaming Availability & Filter Overhaul:**
  - Created `src/backend/core/canonical_taxonomy.py` as Single Source of Truth defining **31 canonical PT-BR categories**, **25 normalized streaming providers/networks**, **8 audiovisual formats** (including genre-backed `documentary`, `animation`, `special`, `short`), and **8 data sources** (`eztv`, `p2p_active`, `imdb`, `tmdb`, `ptbr`, `youtube_trailer`, `tvmaze`, `personal_library`).
  - Created `scripts/sync_canonical_facets_and_providers.py` to harvest real streaming availability from TMDB `/3/discover/movie` & `/3/discover/tv` (`12,373` titles mapped) and normalize `175,397` rows across `data/mainstream.db`.
  - Upgraded `scripts/imdb-metadata-catalog.py` to request `watch/providers` and store canonicalized genres and streaming providers on `--resume` and `--update`.
  - Implemented exact CSV token matching (`_csv_token_in`) preventing substring collisions (`Ação` vs `Animação`, `Music` vs `Musical`, `Max` vs `Cinemax`), `data_sources` intersection filtering, and `role_type` pushdown in `/api/explore/works`.
- **Dual-SSOT UI Update Controls & Filter Reset Controls:**
  - Added `GET /api/explore/mainstream-stats` and `POST /api/explore/update-mainstream` (`delta`, `badges`, `hydrate`) in `src/backend/api/explore.py`, plus automatic badge propagation on `POST /api/catalog/sync`.
  - Redesigned the Filter Panel in `ExplorerView.tsx` with Dual-SSOT database update bars, prominent filter reset/clear buttons (`Limpar / Resetar Filtros`), `data_sources` pills, status filter selector, all 31 canonical genres, all 25 streaming providers, and locale-formatted counters (`formatFacetCount`).
  - Added `tests/integration/test_mainstream_sources_ssot.py`, bringing the hermetic test suite to **64 passing tests**.

### Changed
- Aligned package and runtime version metadata to `0.7.0` across `pyproject.toml`, `src/frontend/package.json`, and `src/backend/main.py`.
- Archived `ADR-011` (`16/16` tasks complete) with algorithmic Evidence Record (`docs/adr/ADR-011-ER.md`) via `spx adr archive ADR-011`.
- Reconciled all 6 canonical documentation pillars (`README.md`, `CHANGELOG.md`, `USAGE.md`, `RELEASE-NOTES.md`, `STATE.md`, `AGENTS.md`).

---

## [0.6.0] - 2026-11-15

### Added
- **Dual-Database Separation & EZTV Cross-Referencing (ADR-009):**
  - Implemented isolated SQLModel persistence for `data/eztv_metadata.db` (`EZTVShow`, `EZTVEpisodeCatalog` on `eztv_metadata = MetaData()`) in `src/backend/models/eztv_db.py` and `get_eztv_session()` / `init_eztv_db()` in `src/backend/core/database.py`.
  - Refactored `CatalogRepository` (`src/backend/repositories/catalog.py`) and `/api/catalog` (`src/backend/api/catalog.py`) to serve shows, curated sections, episode guides, and genres directly from `data/eztv_metadata.db`, overlaid with P2P seed telemetry from `data/tv_pirata.db` and `/api/catalog/enrich-pending` gap filling.
  - Cross-referenced `DiscoveryEngineRepository` (`src/backend/repositories/discovery_engine.py`) and `/api/discovery` (`src/backend/api/discovery.py`) against `data/eztv_metadata.db` via normalized IMDb ID (`ttXXXXXXX`) and deterministic title/slug fallback, exposing `eztv_available`, `eztv_show_id`, `status`, `network`, and `streaming_providers`.
  - Created custom vector badge components `EztvBadge.tsx` (`src/frontend/src/components/EztvBadge.tsx`) and `ShowBadges.tsx` (`StatusBadge` & `ProviderBadge` in `src/frontend/src/components/ShowBadges.tsx`) integrated across all channels (`ShowCard.tsx`, `ExplorerView.tsx`, `CatalogView.tsx`).
  - Upgraded `scripts/eztv-metadata-catalog.py` with Cloudflare challenge detection (`is_cloudflare_challenge`), automatic fallback to EZTV's official JSON API (`/api/get-torrents`), TVMaze name-search fallback (`fetch_tvmaze_by_name`), and TMDB enrichment (`fetch_tmdb_enrichment`).
- **Dual-SQLite High-Performance Read Pipeline, Materialized Stats & FTS5 (ADR-010):**
  - Added SQLAlchemy `@event.listens_for(Engine, "connect")` hook in `src/backend/core/database.py` configuring `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-64000` (64 MB), `mmap_size=268435456` (256 MB), and `busy_timeout=5000`.
  - Added materialized episode statistics (`episodes_count`, `max_season`, `max_episode`) to `EZTVShow` with idempotent SQL backfill and `shows_fts` (`FTS5` virtual table + `AFTER INSERT/DELETE/UPDATE` triggers).
  - Implemented thread-safe `EngineScopedCache` in `src/backend/core/cache.py` partitioned by `(id(engine), table_fingerprint)`, single-pass `get_curated_sections`, and `_SEEDED_ENGINES` guard in `FederatedCatalogService`, cutting `list_shows` latency by **98.4%** (`965.61 ms` $\rightarrow$ `15.19 ms`) and `get_curated_sections` by **99.3%** (`692.07 ms` $\rightarrow$ `4.74 ms`).
- **Audiovisual Discovery Core — Layer 1 Foundation (ADR-008):**
  - Implemented multi-format canonical domain model in `src/backend/models/catalog_domain.py` (`MediaWork`, `ExternalIdentifier`, `DataProvenance`, `PersonRecord`, `WorkCredit`, `GenreRecord`, `WorkGenreLink`, `StreamingAvailability`, `WorkRelation`, `ReleaseCalendarEvent`) supporting Movies, TV Series, Mini-series, Documentaries, Animations, and Specials independently of local files or P2P torrents.
  - Implemented `EntityResolutionService` in `src/backend/services/entity_resolution.py` with confidence-tiered matching (`deterministic`, `high`), anti-collision remake protection, per-source rating preservation (`ratings_breakdown`), and field-level `DataProvenance` tracking.
  - Implemented `FederatedCatalogService` in `src/backend/services/federated_catalog.py` combining curated multi-source works (`curated_catalog_seed.json`), automatic bridging with existing `CatalogShow` and `ShowRecord` entities, and complementary live connector ingestion.
  - Implemented `DiscoveryEngineRepository` in `src/backend/repositories/discovery_engine.py` featuring an Advanced Filtering Engine (`AND`/`OR`/`NOT` genres, format, year range, rating, runtime, director/actor/creator, streaming platform, country, language, watched exclusion), dynamic facet aggregation, Relationship Discovery (filmographies and shared 2-person collaborations), Objective Similarity Engine, and Unified Release Calendar.
  - Exposed `/api/explore` REST router in `src/backend/api/explore.py` (`/works`, `/works/{id}`, `/people`, `/people/{id}`, `/people/collaborations`, `/calendar`, `/rankings`, `/federate`).
  - Integrated cinematic **`ExplorerView.tsx`** ("Explorar Universo") in the React 19 SPA with interactive boolean filters, dynamic facet counters, canonical work dossiers with provenance and streaming availability, filmography/collaboration explorer, and release calendar.
  - Added unit and integration tests (`test_entity_resolution.py`, `test_discovery_engine.py`, `test_explore_api.py`, `test_dual_db_eztv.py`, `test_db_performance.py`), expanding the automated test suite to **63 passing tests**.

### Changed
- Aligned package and runtime version metadata to `0.6.0` across `pyproject.toml`, `src/frontend/package.json`, and `src/backend/main.py`.
- Archived completed Decision Sets `ADR-005` through `ADR-010` via `spx adr archive` with algorithmic Evidence Records (`ADR-005-ER.md` to `ADR-010-ER.md`) and pruned resolved technical debts to `docs/governance/archive/tech-debt-archive.json`.
- Reconciled all 6 canonical documentation pillars (`README.md`, `CHANGELOG.md`, `USAGE.md`, `RELEASE-NOTES.md`, `STATE.md`, `AGENTS.md`/`GEMINI.md`) and `docs/DOCUMENTATION_AUDIT_REPORT.md`.

---

## [0.5.0] - 2026-11-12

### Added
- **Background Auto-Sync, Asynchronous Scheduling & Release Notifier (ADR-007):**
  - Implemented relational entity `ReleaseNotificationRecord` in `src/backend/models/db.py` with unique constraint on `(show_id, season, episode)` for strict release deduplication and idempotency.
  - Implemented `NotificationRepository` in `src/backend/repositories/notification.py` supporting unread filtering, global unread counters, single mark-as-read, and batch dismissal.
  - Developed `sync_and_reconcile_recent` reconciliation engine in `src/backend/services/catalog_indexer.py` cross-referencing fresh EZTV torrent feeds with tracked user library shows.
  - Created `BackgroundSyncService` in `src/backend/services/scheduler.py` running native `asyncio.Task` inside FastAPI `lifespan` with $\pm 10\%$ jitter, exponential error backoff, and cooperative timeout guard ($\le 3.0$s) ensuring zero orphaned processes on shutdown.
  - Implemented `/api/notifications` REST endpoints in `src/backend/api/notifications.py` for notification listing, count retrieval, dismissal, scheduler health telemetry, and manual on-demand triggers.
  - Integrated notification badges in frontend `Navbar.tsx` (desktop & mobile) and dynamic new-release banners, episode ribbons, and instant torrent download shortcuts in `LibraryView.tsx`.
  - Added comprehensive unit and integration test suites in `tests/unit/test_scheduler.py` and `tests/integration/test_notifications_api.py`, expanding the test suite to **47 passing tests** with 100% Ruff lint conformance.

---

## [0.4.0] - 2026-11-12

### Added
- **Persistent EZTV Catalog & P2P Ingestion Engine (ADR-006):**
  - Implemented relational entities `CatalogShow` and `CatalogRelease` in `src/backend/models/db.py` to persist torrent distributions directly into SQLite.
  - Developed `EZTVIndexerService` in `src/backend/services/catalog_indexer.py` with multi-page crawling, regex-based title sanitization, and automated enrichment via TVMaze and TMDB by `imdb_id`.
  - Implemented `CatalogRepository` in `src/backend/repositories/catalog.py` with fast local querying by seeds, release date, and full-text search.
  - Implemented `/api/catalog` REST router in `src/backend/api/catalog.py` exposing paginated shows, show releases by IMDB ID, acervo statistics, and on-demand background sync.
  - Implemented CLI synchronization tool in `scripts/sync_catalog.py` and added `make sync-catalog` automation in `Makefile`.
  - Added `lookup_by_imdb` methods in `TVMazeProvider` and `TMDBProvider` with redirect following.
  - Integrated dedicated **"Catálogo EZTV"** view (`CatalogView.tsx`) and streaming carousels with guaranteed active seed counts in the frontend.
  - Added 9 unit and integration tests, expanding the test suite to **33 passing tests**.

---

## [0.3.0] - 2026-11-12

### Added
- **Cinematic Web Frontend SPA (ADR-005):**
  - Implemented modern React 19 + TypeScript + Tailwind CSS Single-Page Application in `src/frontend/`.
  - Configured OLED-Safe Deep Slate design system (`#090a0f`, `#131722`, `#d81f26`) compliant with WCAG 2.1 AAA contrast and $\ge 44\text{px}$ touch targets.
  - Developed `Navbar` with debounced live search and smooth scroll blur.
  - Implemented `HeroBanner` with high-definition backdrop, dynamic vignettes, rating badges, and quick actions.
  - Developed horizontal streaming `ShowCarousel` with scroll-snap and lazy-loading posters.
  - Developed `ShowDetailModal` with season selection tabs, overview, local SMB availability badge, and optimistic episode watch tracking.
  - Developed `TorrentModal` aggregating EZTV releases by resolution (4K, 1080p, 720p, SD), sorted by seeders, with 1-click clipboard magnet copy and direct `magnet:?` protocol triggering.
  - Developed `LibraryView` with user status filters (`watching`, `plan_to_watch`, `completed`, `paused`, `abandoned`) and status dropdowns.
  - Developed `CollectionsView` with dynamic tag creation and JSON-based smart collection filtering.
  - Configured Vite build outputting directly to `src/backend/static/dist/`, served seamlessly by FastAPI on `/` and `/assets`.
- **Quality Gates & Tests:**
  - Added frontend SPA delivery test in `tests/integration/test_api_endpoints.py`, bringing total passing tests to 24.
  - Added `make build-front` and `make dev-front` automations in `Makefile`.

---

## [0.2.0] - 2026-11-11

### Added
- **Relational Persistence Layer with SQLModel (ADR-004):**
  - Implemented database entities `ShowRecord`, `SeasonRecord`, `EpisodeRecord`, `EpisodeWatchRecord`, `LocalMediaRecord`, `TagRecord`, `ShowTagLink`, and `CollectionRecord` in `src/backend/models/db.py`.
  - Configured atomic SQLite engine with timezone-aware datetime validation in `src/backend/core/database.py`.
  - Implemented `LibraryRepository` in `src/backend/repositories/library.py` providing transactional upsert, episode watch toggling, season watch-all, and dynamic smart collection execution.
- **FastAPI REST Application & Routers:**
  - Configured `src/backend/main.py` with lifespan database initialization, CORS middleware, and `/api/health`.
  - Implemented `/api/discovery` endpoints for trending, search, and show details.
  - Implemented `/api/library` endpoints for CRUD operations on the user's personal show collection.
  - Implemented `/api/watches` endpoints for episode toggles and show progress aggregation.
  - Implemented `/api/torrents` endpoints querying EZTV releases by IMDB ID.
  - Implemented `/api/collections` endpoints for tags and smart collections.
- **Expanded Test Suite:**
  - Added in-memory unit tests in `tests/unit/test_db_models.py` and comprehensive API integration tests in `tests/integration/test_api_endpoints.py` bringing total passing tests to 22.

---

## [0.1.0] - 2026-11-11

### Added
- **Repository Bootstrap & Governance (ADR-001):**
  - Provisioned canonical directory topology, `AGENTS.md`, `GEMINI.md`, `Makefile`, and `scripts/quality_gate.sh`.
  - Configured Python 3.14 virtual environment with `uv` tooling and Git hooks.
- **Unified Domain Models (ADR-002, ADR-003):**
  - Implemented `UnifiedShow`, `UnifiedSeason`, `UnifiedEpisode`, and `TorrentRelease` in `src/backend/models/unified.py`.
  - Added HTML sanitization for third-party provider summaries.
- **Modular Metadata Providers:**
  - Implemented `BaseMetadataProvider` abstract interface.
  - Implemented `TMDBProvider` with support for show searches, details, and weekly trending.
  - Implemented `TVMazeProvider` as an open, token-free fallback provider.
- **Resilient Discovery Client:**
  - Implemented `ResilientDiscoveryService` with a 2.0s strict timeout on TMDB and automatic, transparent fallback to TVMaze.
- **EZTV Torrent Distribution Integration:**
  - Implemented `EZTVProvider` fetching torrent releases by IMDB ID, sorting by seeders, and mapping magnet URLs.
- **Comprehensive Test Suite:**
  - Added 13 deterministic tests in `tests/unit/` and `tests/integration/` using `respx` and JSON fixtures.
