---
id: ADR-016-TODO
title: "Checklist de Execução (TODO) — ADR-016"
parent_adr: ADR-016
date: 2026-11-20
status: PROPOSED
language: PT-BR
---

# ADR-016-TODO: Checklist Determinístico de Execução (12 Tarefas)

## Onda 1 — Backend: Telemetria Viva, Velocidade, ETA e Ring Buffer
- [x] **TODO-16.01 (`DEC-003`):** Adicionar `HydrationActivityEvent` e os campos `current_stage`, `current_target`, `started_at`, `elapsed_seconds`, `items_processed_in_run`, `rate_per_minute`, `eta_seconds` e `recent_events` a `HydrationPipelineStatus` em `src/backend/services/hydration_orchestrator.py`.
- [x] **TODO-16.02 (`DEC-003`):** Instrumentar `CascadingMetadataEnricher.enrich_batch` (`src/backend/services/cascading_enricher.py`) e `HydrationOrchestratorService.run_single_step` para atualizar `current_stage` / `current_target` durante a execução e calcular `rate_per_minute` e `eta_seconds`.
- [x] **TODO-16.03 (`DEC-004`):** Implementar o *ring buffer* `deque(maxlen=15)` com helper `_record_event` em `HydrationOrchestratorService` gerando mensagens legíveis em português e preservando exposição retrocompatível em `GET /api/explore/hydration/status`.

## Onda 2 — Frontend: Layout Master-Detail Estilo IDE & Consolidação
- [x] **TODO-16.04 (`DEC-003`, `DEC-004`):** Atualizar `src/frontend/src/types.ts` com `HydrationActivityEvent` e os novos campos de telemetria viva em `HydrationPipelineStatus`.
- [x] **TODO-16.05 (`DEC-001`):** Criar `src/frontend/src/components/settings/SettingsSidebar.tsx` com busca instantânea (`"Filtrar ajustes..."`), 4 categorias navegáveis por teclado e indicador pulsante quando houver atualização em andamento.
- [x] **TODO-16.06 (`DEC-001`, `DEC-002`):** Refatorar `src/frontend/src/components/StatusConfigView.tsx` para layout Master-Detail em 2 colunas (`SettingsSidebar` + painel ativo), eliminando o monólito vertical e os 4 gatilhos redundantes de sincronização.
- [x] **TODO-16.07 (`DEC-001`, `DEC-002`):** Criar os painéis dedicados sob `src/frontend/src/components/settings/` (`CatalogUpdatePanel.tsx`, `SourcesProvidersPanel.tsx`, `ExplorePrefsPanel.tsx`, `AdvancedMaintenancePanel.tsx`) com linguagem 100% humana e edição limpa de fontes.

## Onda 3 — Linguagem Humana & Monitor de Atividade ao Vivo
- [x] **TODO-16.08 (`DEC-002`):** Atualizar `src/frontend/src/components/HydrationConsoleCard.tsx` eliminando jargões internos (`BOOTSTRAP`, `DELTA`, `Pilar 1B/3`, `Sweep @`, `Recent p.`, `Dual-SSOT`) em favor de rótulos humanos claros.
- [x] **TODO-16.09 (`DEC-004`):** Exibir velocidade (`itens/min`), tempo decorrido, ETA estimado, etapa/alvo atual e **Monitor de Atividade** colapsável (`recent_events`) com polling de `1.0s` apenas enquanto `state === "RUNNING"`.

## Onda 4 — Testes, Build & Arquivamento SOTA
- [x] **TODO-16.10 (`DEC-005`):** Expandir `tests/integration/test_three_pillar_hydration.py` validando `rate_per_minute`, `eta_seconds`, `current_stage`, `current_target` e `recent_events`.
- [x] **TODO-16.11 (`DEC-005`):** Validar `make lint`, `make test`, `cd src/frontend && npx tsc --noEmit` e `make build-front`.
- [x] **TODO-16.12 (`DEC-005`):** Reconciliar os 6 pilares documentais (`README.md`, `CHANGELOG.md`, `USAGE.md`, `RELEASE-NOTES.md`, `STATE.md`, `AGENTS.md`), arquivar via `spx adr archive ADR-016`, atualizar `docs/adr/ADR-INDEX.md`, rodar `spx docs build` e executar `git commit && git push`.
