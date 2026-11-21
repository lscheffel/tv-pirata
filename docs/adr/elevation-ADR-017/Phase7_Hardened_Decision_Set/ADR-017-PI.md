---
id: ADR-017-PI
title: "Plano de Implementação (PI) — ADR-017: Paralelismo Bifurcado & Correção 422"
parent_adr: ADR-017
date: 2026-11-20
status: PROPOSED
language: PT-BR
---

# ADR-017-PI: Plano de Implementação em 4 Ondas

## Onda 1 — Correção `422`, Exaustão Inteligente & `DomainSemaphoreRegistry` (`DEC-001`, `DEC-002`, `DEC-005`)
1. **`src/backend/core/domain_concurrency.py`:** Criar `DomainSemaphoreRegistry` baseado em `WeakKeyDictionary[AbstractEventLoop, dict[str, asyncio.Semaphore]]` + helper `create_shared_http_client()`.
2. **`src/backend/sidecar/torrent_api_sidecar.py` & `Makefile`:** Remover teto `le=20` em `get_recent_torrents` (retornando `data: []` além da pág. 20) e adicionar `--workers 4` em `make run-sidecar`.
3. **`src/backend/providers/sources/torrent_api_py_adapter.py`:** Tratar HTTP `422` em `fetch_recent_candidates` como exaustão limpa (`return candidates`), aceitar `client: Optional[httpx.AsyncClient] = None` e usar `DomainSemaphoreRegistry`.

## Onda 2 — Fan-out HTTP Puro nos Adaptadores & `sweep` Paralelo (`DEC-002`, `DEC-003`)
4. **`src/backend/providers/sources/yify_adapter.py`:** Buscar `start_page` e disparar demais páginas até `total_pages` via `asyncio.gather` sob semáforo `yify (4)`, mantendo `Batch SELECT/UPSERT` único no Fan-in.
5. **`src/backend/services/sources_registry.py`:** Paralelizar buscas de `sweep_canonical_catalog_presence` via `asyncio.gather` sob semáforo do domínio (Fan-in único no final) e marcar `exhausted=True` quando `mode=="baseline" and start_page > 1 and indexed == 0`.

## Onda 3 — Cascata Paralela, Lanes `Fontes || Metadados` & Lotes `6/12/20` (`DEC-003`, `DEC-004`)
6. **`src/backend/services/cascading_enricher.py`:** Separar coleta HTTP pura (Tiers 1–5 em paralelo por obra via `asyncio.gather` + Tier 6 Wikidata Batch + Wikipédia/Jikan paralelo com semáforos por domínio) do Fan-in (`cross_db_self_heal` + `_apply_coalesce` + commits).
7. **`src/backend/services/hydration_orchestrator.py` & `src/backend/api/explore.py`:** Orquestrar execução paralela entre fontes P2P e metadados (`return_exceptions=True` + Fan-in SQLite sequencial), atualizar `yts_pages=6`, `sweep_batch=12`, `meta_batch=20` e telemetria multi-faixa.

## Onda 4 — Testes Herméticos, Gate de Qualidade & Arquivamento (`DEC-001`..`DEC-005`)
8. **`tests/integration/test_three_pillar_hydration.py`:** Testar `422 -> recent_exhausted=True -> sweep`, `0` inéditos em `page > 1`, `DomainSemaphoreRegistry` em múltiplos event loops, paralelismo real com `respx` + contadores de concorrência máxima e Fan-in sem erros de `Session`.
9. **Fechamento:** Executar `make lint && make test && cd src/frontend && npx tsc --noEmit && cd ../.. && make build-front`, reconciliar os 6 pilares documentais, marcar `12/12` em `ADR-017-TODO.md`, arquivar via `spx adr archive ADR-017`, atualizar `ADR-INDEX.md`, rodar `spx docs build` e executar `git commit && git push`.
