---
id: ADR-009-PI
adr_ref: ADR-009
title: "Plano de Implementação — ADR-009"
status: ACCEPTED
created: "2026-11-13"
updated: "2026-11-13"
---

# Plano de Implementação Incremental (TDD / DAG) — ADR-009

1. **Fase 1 — Persistência Dual & Modelos (`T1`, `T2`):**
   - `src/backend/core/database.py`: adicionar `EZTV_DATABASE_URL`, `eztv_engine`, `get_eztv_engine()`, `init_eztv_db()` (usando `CREATE TABLE IF NOT EXISTS` idempotente para `shows` e `episodes_catalog`) e `get_eztv_session()`.
   - `src/backend/main.py`: chamar `init_eztv_db()` no `lifespan`.
   - `src/backend/models/eztv_db.py`: definir `EZTVShow` e `EZTVEpisodeCatalog` (com `SQLModel` sem poluir `SQLModel.metadata` global ou usando metadata dedicada/tabelas isoladas para que `init_db()` não crie `shows` dentro de `tv_pirata.db`).

2. **Fase 2 — Catálogo EZTV sobre `eztv_metadata.db` (`T3`):**
   - `src/backend/repositories/catalog.py`: adaptar `list_shows`, `get_show`, `get_show_episodes`, `get_genres_with_counts`, `get_curated_sections`, `get_stats` para ler `EZTVShow` e `EZTVEpisodeCatalog` de `eztv_session`, mesclando opcionalmente telemetria P2P (`CatalogShow`/`CatalogRelease`) de `session`.
   - `src/backend/api/catalog.py`: injetar `eztv_session: Session = Depends(get_eztv_session)` e `session: Session = Depends(get_session)`, retornando `episodes` nos detalhes e enriquecendo lacunas em `eztv_metadata.db` via `TVMazeProvider`/`TMDBProvider`.

3. **Fase 3 — Cruzamento Explore ↔ EZTV (`T4`):**
   - `src/backend/repositories/discovery_engine.py`: construir `build_eztv_lookup_index(eztv_session)` e injetar `eztv_available` e `eztv_show_id` em `_serialize_work_summary` e `get_work_dossier`.
   - `src/backend/api/explore.py`: injetar `eztv_session: Session = Depends(get_eztv_session)` em `/works` e `/works/{work_id}`.

4. **Fase 4 — Frontend (`T5`):**
   - `types.ts` e `api.ts`: adicionar `eztv_available`, `eztv_show_id` em `MediaWorkSummary`/`MediaWorkDossier`, e `CatalogEpisode` + campos extras em `CatalogShow`.
   - `ExplorerView.tsx`: renderizar badge `"EZTV"` sobre o cartaz quando `w.eztv_available === true` e no dossiê.
   - `CatalogView.tsx`: exibir contagem de episódios/rede e detalhes dos episódios catalogados de `eztv_metadata.db`.

5. **Fase 5 — Testes & Gates (`T6`, `T7`):**
   - `tests/integration/test_dual_db_eztv.py`: testar dual-DB isolado em memória, `/api/catalog/*`, `/api/explore/works` com `eztv_available` por `imdb_id` e fallback por título/slug.
   - Rodar `make test`, `make lint`, `make build-front`.

