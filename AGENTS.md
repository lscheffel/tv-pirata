# AGENTS.md — Workspace AgentOps & Engineering Standard (SSOT)

## 1. Overview & Architectural Identity

This workspace operates under agentic governance and deterministic engineering guided by the **SynPraxis AgentOps Platform**.
All canonical guidelines for architecture, code patterns, testing standards, and lifecycle management are formally anchored in this document.

**TV Pirata (`v0.6.0`)** is an **Audiovisual Discovery Platform & Personal Media Ecosystem (Discovery-First)** organized into a strict **3-Layer Architecture**:
1. **Layer 1 — Audiovisual Discovery Core (`catalog_domain.py`, `entity_resolution.py`, `federated_catalog.py`, `discovery_engine.py`, `/api/explore`, `ExplorerView.tsx`, `ShowBadges.tsx`, `EztvBadge.tsx`):** Canonical multi-format catalog (`movie`, `tv_show`, `mini_series`, `documentary`, `animation`, `special`), confidence-tiered Entity Resolution with field-level `DataProvenance` and per-source `ratings_breakdown`, boolean filtering (`AND`/`OR`/`NOT`), dynamic facets, filmography & collaboration discovery, unified release calendar, and deterministic cross-referencing against `data/eztv_metadata.db` (`eztv_available`, `eztv_show_id`). Must NEVER depend on local file availability or torrent existence for catalog inclusion.
2. **Layer 2 — Personal Media Ecosystem (`db.py`, `eztv_db.py`, `cache.py`, `library.py`, `catalog.py`, `notification.py`, `catalog_indexer.py`, `scheduler.py`, `/api/library`, `/api/watches`, `/api/catalog`, `/api/notifications`, `/api/torrents`):** Dual-SQLite persistence (`data/tv_pirata.db` + `data/eztv_metadata.db` with WAL/mmap PRAGMAs, materialized episode counts, `shows_fts` FTS5 index, and `EngineScopedCache`), personal library management, episode watch history, SMB local file mapping, persistent EZTV catalog, and lifespan-managed asynchronous background auto-sync with release notifications.
3. **Layer 3 — Personalization & Intelligence (`discovery_engine.py`, `collections.py`, `/api/collections`):** Multi-criteria objective similarity engine with transparent explanations (`shared_reasons`), smart collections (`filter_criteria`), and watched-item exclusion.

---

## 2. Engineering Invariants for AI Agents

1. **Anti-Stub Invariant:** Every component, API contract, route, or utility must have a complete physical implementation. Permissive mocks that mask runtime exceptions in production components are strictly prohibited.
2. **Layer Decoupling, Dual-DB & Provenance Invariant (ADR-008, ADR-009, ADR-010):** Layer 1 (`MediaWork` in `tv_pirata.db`) must remain independent of P2P torrents or SMB files, while `EZTVShow` and `EZTVEpisodeCatalog` reside exclusively in `eztv_metadata.db` (`eztv_metadata = MetaData()`). In-memory caches must use `EngineScopedCache` partitioned by `(id(engine), table_fingerprint)` to preserve hermetic `pytest` isolation.
3. **Quality & Strict Typing:** Python code must adopt complete type hints (`from __future__ import annotations`), passing cleanly through linter checks (`ruff` with 100-char line limit) and the hermetic test suite (`pytest`, currently 63 tests).
4. **RAG-First Protocol:** Before planning structural changes or complex refactoring, query the repository knowledge store via CLI (`spx search` or MCP `rag_hybrid_search`) to map existing patterns and architecture decisions.
5. **ADR Governance:** Significant architectural changes (DCI $\ge 1.5$) must be recorded via Quadra SOTA in `docs/adr/` (`ADR-XXX.md`, `ADR-XXX-BP.md`, `ADR-XXX-TODO.md`, `ADR-XXX-PI.md`).
6. **Zero Orphaned Servers:** Agents must never terminate sessions leaving dev servers or daemon processes running in the background without explicit request. Background tasks inside FastAPI must use the cooperative `lifespan` manager (`BackgroundSyncService`).
7. **No Graphical Browser Testing:** Never invoke Chrome/Chromium or `browser` subagents in this headless environment; validate all frontend/API contracts via deterministic `pytest` (`TestClient`), `respx`, TypeScript compiler (`tsc`), and Vite build checks.
8. **Invariant Linguistic Governance (Dual Consumption: PT-BR vs EN-US):**
   - **Human Consumption & Chat (PT-BR):** Documentation intended for human reading and consumption (`README.md`, `USAGE.md`, `RELEASE-NOTES.md`, `STATE.md`, ADRs, audit reports, web portals) and all interactive chat communication with the user must be written in **Portuguese (PT-BR)**.
   - **Agentic Consumption & Code (EN-US):** Artifacts consumed directly by AI agents (`AGENTS.md`, Agent Skills, system prompts, LLM context payloads, structured schemas) and all source code (application code, tests, typing, technical API docstrings, and commit messages) must be written strictly in **English (EN-US)**.

---

## 3. Useful Commands Matrix

| Command | Description |
| :--- | :--- |
| `make run` | Starts the integrated FastAPI + SPA server on `http://127.0.0.1:8000` |
| `make build-front` | Compiles the React 19 + TypeScript + Tailwind SPA into `src/backend/static/dist/` |
| `make dev-front` | Runs the Vite development server (`http://127.0.0.1:5173`) with API proxy |
| `make sync-catalog` | Synchronizes recent EZTV torrent pages into the local SQLite catalog (`scripts/sync_catalog.py`) |
| `make test` | Runs the automated hermetic test suite via `pytest` (63 unit & integration tests) |
| `make lint` | Runs static code analysis with `ruff check src/ tests/` |
| `make format` | Automatically formats Python source code with `ruff format src/ tests/` |
| `make setup-hooks` | Configures `scripts/quality_gate.sh` as the local Git `pre-commit` hook |
| `spx sync` | Synchronizes and reindexes the workspace vector store |
| `spx audit` | Runs forensic quality audit across the workspace |
