---
adr_ref: ADR-020
title: "Plano de Implementação — ADR-020"
status: ACCEPTED (ELEVATED)
updated: "2026-11-22"
---

# ADR-020 Plano de Implementação (PI)

## Fase 1 — Backend (`sources_registry.py`, `hydration_orchestrator.py`, `api/explore.py`)
1. Parametrizar `min_votes` em `SourcesRegistryService.select_sweep_works`.
2. Estender `CanonicalCoverageSnapshot` e `HydrationPipelineStatus` com `run_mode`, `sweep_min_votes`, `sweep_enabled_sources`, `recent_pages_per_source`, `last_novidades_at`, `last_novidades_count` e `vote_tier_counts`.
3. Implementar `run_mode="novidades"` vs `"varredura"` em `run_single_step` e `update_config` em `HydrationOrchestratorService`.
4. Expor `run_mode` em `/hydration/start` e `POST /api/explore/hydration/config` em `api/explore.py`.

## Fase 2 — Frontend (`types.ts`, `api.ts`, `HydrationConsoleCard.tsx`)
1. Atualizar tipos e cliente API.
2. Reestruturar `HydrationConsoleCard.tsx` em 2 camadas (Simples + Avançado persistido no `localStorage`).

## Fase 3 — Testes & Build
1. Testes de integração em `tests/integration/test_three_pillar_hydration.py`.
2. `make lint && make test && make build-front`.
