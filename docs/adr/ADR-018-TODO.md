---
adr_ref: ADR-018
title: "TODO — Telemetria por Lanes, Progresso Sidecar e Administração Mainstream"
status: ACCEPTED (ELEVATED)
updated: "2026-11-22"
---

# ADR-018 Checklist de Execução (TODO)

## Bloco 1 — Telemetria, EMA, Progresso Sidecar e Controles TMDB/TVMaze

- [ ] **T01:** Estender `HydrationCoverageSummary`, `PillarSourceCursor` e `HydrationPipelineStatus` em `hydration_orchestrator.py` com campos Mainstream (`with_tmdb_id`, `series_total`, `series_with_tvmaze_id`, `tmdb_configured`, `imdb_last_sync_at`), `metadata_batches_executed`, `ema_rates`, `sidecar_eta_seconds` e `target_provider` (`DEC-001`, `DEC-002`, `DEC-004`, `DEC-005`).
- [ ] **T02:** Atualizar `SmartBootstrapDetector.refresh_modes` e `_apply_live_telemetry` para computar cobertura real de TMDB/TVMaze, EMA persistida por fonte em `sync_state`, `sweep_pct` e `sidecar_eta_seconds` (`DEC-001`, `DEC-004`).
- [ ] **T03:** Implementar silenciamento do evento `"0 de 0"` quando `proc_m == 0` (com notificação única de conclusão), incremento de `metadata_batches_executed`, suporte a `target_provider` / `metadata_mode` e transição automática `recent -> sweep` após 2 páginas sem matches (`DEC-002`, `DEC-005`, `DEC-007`).
- [ ] **T04:** Expor `target_provider`, `metadata_mode` e `POST /api/explore/hydration/sources/{source_key}/skip-recent` em `src/backend/api/explore.py` (`DEC-005`, `DEC-007`).
- [ ] **T05:** Atualizar tipos TypeScript (`src/frontend/src/types.ts`) e cliente API (`src/frontend/src/services/api.ts`) para Bloco 1 e Bloco 2 (`DEC-003`..`DEC-008`).
- [ ] **T06:** Refatorar `HydrationConsoleCard.tsx` com banner de 2 níveis, bloco Mainstream (`IMDb`, `TMDB`, `TVMaze`), micro-barras `%` nos cards P2P, selo `"100% verificado (máximo das APIs)"` e gaveta de Tabela Técnica recolhida por padrão (`DEC-002`, `DEC-003`, `DEC-006`).

## Bloco 2 — Administração Assíncrona da Base Canônica IMDb (TSV + FTS5)

- [ ] **T07:** Criar `src/backend/services/imdb_sync_service.py` encapsulando download condicional, upsert em `data/mainstream.db` (com toggle `include_episodes`) e reconstrução `shows_fts`, com estado em etapas (`DEC-008`).
- [ ] **T08:** Expor endpoints `GET /api/explore/imdb/status`, `POST /api/explore/imdb/sync` e `POST /api/explore/imdb/reindex-fts` em `src/backend/api/explore.py` (`DEC-008`).
- [ ] **T09:** Conectar ações do card `IMDb (Base Canônica)` em `HydrationConsoleCard.tsx` ao polling de `IMDbSyncJobStatus` (`DEC-008`).

## Verificação & Fechamento

- [ ] **T10:** Adicionar testes herméticos de integração/unidade em `tests/` cobrindo EMA persistida, `sidecar_eta_seconds`, silenciamento `0 de 0`, `skip-recent`, `target_provider` e `IMDbCanonicalSyncService` (mockado).
- [ ] **T11:** Executar `make lint && make test` + `npm run build` (`make build-front`) com 100% de aprovação.
- [ ] **T12:** Reconciliar documentação e arquivar `ADR-018` via `adr-archive`.
