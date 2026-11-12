# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
