---
id: ADR-017-TODO
title: "Checklist de Execução (TODO) — ADR-017"
parent_adr: ADR-017
date: 2026-11-20
status: PROPOSED
language: PT-BR
---

# ADR-017-TODO: Checklist Determinístico de Execução (12 Tarefas)

## Onda 1 — Correção `422`, Exaustão de Feeds & Registro de Semáforos
- [x] **TODO-17.01 (`DEC-001`, `DEC-005`):** Atualizar `get_recent_torrents` em `src/backend/sidecar/torrent_api_sidecar.py` para aceitar `page >= 1` sem retornar `422` além da pág. 20 (retornando `data: []`), e adicionar `--workers 4` em `make run-sidecar` no `Makefile`.
- [x] **TODO-17.02 (`DEC-001`):** Tratar HTTP `422` e `[]` em `TorrentApiPySourceAdapter.fetch_recent_candidates` (`src/backend/providers/sources/torrent_api_py_adapter.py`) como exaustão limpa (`return candidates`), e em `SourcesRegistryService.sync_source` marcar `exhausted=True` quando `mode=="baseline" and start_page > 1 and indexed == 0`.
- [x] **TODO-17.03 (`DEC-002`):** Criar `src/backend/core/domain_concurrency.py` com `DomainSemaphoreRegistry` (`WeakKeyDictionary` por event loop) e factory `create_shared_http_client()` Keep-Alive.

## Onda 2 — Fan-out HTTP nos Adaptadores & `sweep` Paralelo
- [x] **TODO-17.04 (`DEC-002`, `DEC-003`):** Injetar `client` compartilhado e semáforos em `TorrentApiPySourceAdapter` (`tgx=4`, `glodls=4`, `nyaasi=2`, `bitsearch=2`, `sidecar=4`).
- [x] **TODO-17.05 (`DEC-002`, `DEC-003`):** Paralelizar páginas em `YIFYSourceAdapter.sync` (`start_page` + `asyncio.gather` das páginas restantes até `total_pages` sob semáforo `yify=4`) mantendo `Batch SELECT/UPSERT` único no Fan-in.
- [x] **TODO-17.06 (`DEC-003`):** Paralelizar consultas de `SourcesRegistryService.sweep_canonical_catalog_presence` via `asyncio.gather(..., return_exceptions=True)` com semáforo por domínio e Fan-in SQLite único.

## Onda 3 — Cascata Paralela & Lanes `Fontes || Metadados`
- [x] **TODO-17.07 (`DEC-003`):** Refatorar `CascadingMetadataEnricher.enrich_batch` (`src/backend/services/cascading_enricher.py`) em coleta HTTP paralela (Tiers 1–5 em paralelo por obra com semáforos `tmdb=8`, `imdb/tvmaze/jikan=2`, `yify=4`, seguida de Tier 6 Wikidata Batch + Wikipédia/Jikan paralelos) e Fan-in SQLite único (`cross_db_self_heal` + `_apply_coalesce` + commits).
- [x] **TODO-17.08 (`DEC-003`, `DEC-004`):** Orquestrar execução paralela entre fontes P2P e metadados em `HydrationOrchestratorService.run_single_step`, elevar lotes padrão (`yts_pages=6`, `sweep_batch=12`, `meta_batch=20`) em `hydration_orchestrator.py` e `explore.py`, e atualizar telemetria multi-faixa.

## Onda 4 — Testes Herméticos, Gate & Arquivamento
- [x] **TODO-17.09 (`DEC-001`, `DEC-002`):** Adicionar testes em `tests/integration/test_three_pillar_hydration.py` cobrindo `422 -> exhausted=True -> sweep`, zero itens inéditos em `page > 1` e `DomainSemaphoreRegistry` em múltiplos event loops.
- [x] **TODO-17.10 (`DEC-003`, `DEC-004`):** Adicionar testes em `tests/integration/test_three_pillar_hydration.py` validando paralelismo limitado por semáforo (Tiers 1–5 e fontes P2P) e Fan-in SQLite sem contenção.
- [x] **TODO-17.11 (`DEC-001`..`DEC-005`):** Executar `make lint && make test && cd src/frontend && npx tsc --noEmit && cd ../.. && make build-front` com `100%` de aprovação.
- [x] **TODO-17.12 (`DEC-001`..`DEC-005`):** Reconciliar os 6 pilares documentais, marcar `12/12` em `ADR-017-TODO.md`, executar `spx adr archive ADR-017`, atualizar `docs/adr/ADR-INDEX.md`, rodar `spx docs build` e executar `git commit && git push`.
