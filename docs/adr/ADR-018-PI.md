---
adr_ref: ADR-018
title: "Plano de Implementação — ADR-018"
status: ACCEPTED (ELEVATED)
updated: "2026-11-22"
---

# ADR-018 Plano de Implementação (PI)

## Fase 1 — Backend Telemetria, EMA e Orquestrador Direcionável (Bloco 1)
1. Atualizar modelos Pydantic em `src/backend/services/hydration_orchestrator.py`.
2. Atualizar `SmartBootstrapDetector.refresh_modes` para consultar cobertura real de `tmdb_id` e `tvmaze_id` em `mainstream.db` e verificar credencial `TMDB_API_KEY` / `TMDB_READ_TOKEN`.
3. Atualizar `_apply_live_telemetry` com EMA persistida em `state.ema_rates`, `sweep_pct` e `sidecar_eta_seconds`.
4. Atualizar `run_single_step` para:
   - Suportar `target_provider` e `metadata_mode` (`pending` vs `missing_synopsis_ptbr`).
   - Incrementar `metadata_batches_executed` apenas quando `proc_m > 0`.
   - Silenciar evento repetido de `0 de 0` quando `pending_details == 0`.
   - Aplicar `consecutive_zero_recent_pages >= 2` -> `recent_exhausted = True`.
5. Adicionar parâmetros em `/api/explore/hydration/start` e `/step`, mais `POST /api/explore/hydration/sources/{source_key}/skip-recent` em `src/backend/api/explore.py`.

## Fase 2 — Serviço e Endpoints IMDb Base Canônica (Bloco 2)
1. Extrair/reutilizar funções puras de `scripts/imdb-metadata-catalog.py` (ou encapsular via `src/backend/services/imdb_sync_service.py`) com progresso em etapas e lock cooperativo para não colidir com o orquestrador em `mainstream.db`.
2. Expor `/api/explore/imdb/status`, `/api/explore/imdb/sync` e `/api/explore/imdb/reindex-fts` em `src/backend/api/explore.py`.

## Fase 3 — Frontend (`types.ts`, `api.ts`, `HydrationConsoleCard.tsx`)
1. Atualizar interfaces em `src/frontend/src/types.ts` e chamadas em `src/frontend/src/services/api.ts`.
2. Refatorar `HydrationConsoleCard.tsx` com:
   - Banner de prontidão em 2 níveis.
   - Bloco Mainstream (IMDb, TMDB, TVMaze) com barras reais e controles individuais.
   - Bloco Fontes P2P com micro-barra de `%` do *sweep* e botão `"Pular recentes"`.
   - Gaveta técnica expansível (recolhida por padrão).

## Fase 4 — Testes e Build
1. Testes unitários/integração em `tests/integration/test_three_pillar_hydration.py` (ou novo `tests/integration/test_adr018_telemetry_and_mainstream.py`).
2. `make lint && make test && make build-front`.
