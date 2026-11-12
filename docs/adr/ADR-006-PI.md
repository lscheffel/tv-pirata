# Implementation Plan: ADR-006 — Catálogo Local EZTV e Motor de Ingestão P2P

## 1. Escopo & Dependências
- **Dependências:** SQLModel, httpx, FastAPI, pytest, respx.
- **DCI:** 7 (ScopeDepth: 3, StatefulInteractions: 2, UncertaintyPenalty: 2) -> Tier 2 / Quadra SOTA com Elevação Adversarial obrigatória.
- **Fases:** 4 fases sequenciais.

## 2. Fase 1: Camada de Dados & Lookup por IMDB ID (T01 - T03)
- Adicionar `CatalogShow` e `CatalogRelease` em `src/backend/models/db.py`.
- Adicionar `lookup_by_imdb(imdb_id)` no `TVMazeProvider` (`https://api.tvmaze.com/lookup/shows?imdb=tt...` com follow redirects).
- Adicionar suporte a lookup no `TMDBProvider` via `/find/{imdb_id}?external_source=imdb_id`.
- Testar criação de tabelas no banco de dados.

## 3. Fase 2: Motor de Indexação & Ingestão (T04 - T06)
- Criar `EZTVIndexerService` com método `sync_pages(start_page=1, max_pages=10)`.
- Fazer deduplicação por hash de release e agregação por `imdb_id`.
- Criar `CatalogRepository` gerenciando transações atômicas de upsert para centenas de releases por lote.

## 4. Fase 3: Camada REST & Automação CLI (T07 - T09)
- Implementar `src/backend/api/catalog.py` com filtros e ordenação por `seeds` desc, `latest_release` desc.
- Implementar `GET /api/catalog/stats` e `POST /api/catalog/sync`.
- Criar comando `make sync-catalog pages=10` no `Makefile`.

## 5. Fase 4: Integração de UI, Testes & Fechamento (T10 - T12)
- Integrar visualização de séries do catálogo no frontend.
- Criar testes unitários para o parser/indexador com mocks `respx`.
- Criar testes de integração para as rotas `/api/catalog`.
- Executar `make test` e `make lint`.

