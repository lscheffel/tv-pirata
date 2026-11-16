---
id: ADR-009-TODO
adr_ref: ADR-009
title: "TODO — Separação de Bases e Entrelaçamento EZTV"
status: COMPLETED
created: "2026-11-13"
updated: "2026-11-13"
---

# Checklist de Implementação — ADR-009

- [x] **T1 (Persistência Dual):** Configurar `EZTV_DATABASE_URL`, `eztv_engine`, `init_eztv_db()` e `get_eztv_session()` em `src/backend/core/database.py`, chamando `init_eztv_db()` no `lifespan` em `src/backend/main.py`.
- [x] **T2 (Modelos EZTV):** Criar `src/backend/models/eztv_db.py` com `EZTVShow` (`shows`) e `EZTVEpisodeCatalog` (`episodes_catalog`) compatíveis com `data/eztv_metadata.db`.
- [x] **T3 (Repositório Catálogo EZTV):** Refatorar `src/backend/repositories/catalog.py` e `src/backend/api/catalog.py` para consumir `eztv_metadata.db` como fonte primária (listagem, filtros, gêneros, seções, stats, detalhes + episódios e enriquecimento via `TVMazeProvider`/`TMDBProvider`).
- [x] **T4 (Cruzamento Explore ↔ EZTV):** Atualizar `src/backend/repositories/discovery_engine.py` e `src/backend/api/explore.py` para cruzar `MediaWork` com `eztv_metadata.db` (`imdb_id` forte + fallback por título/slug) e expor `eztv_available` e `eztv_show_id`.
- [x] **T5 (Frontend Contratos e UI):** Atualizar `src/frontend/src/types.ts`, `src/frontend/src/services/api.ts`, `ExplorerView.tsx` (badge EZTV no cartaz e no dossiê) e `CatalogView.tsx` (consumo de `eztv_metadata.db` com episódios e metadados).
- [x] **T6 (Testes Herméticos):** Criar testes unitários e de integração em `tests/` com bancos isolados em memória (`get_session` + `get_eztv_session`).
- [x] **T7 (Validação Final):** Executar `make test`, `make lint` e `make build-front`.
