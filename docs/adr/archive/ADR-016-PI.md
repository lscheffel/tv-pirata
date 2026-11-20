---
id: ADR-016-PI
title: "Plano de Implementação (PI) — ADR-016: Refatoração UI/UX das Configurações e Telemetria Viva"
parent_adr: ADR-016
date: 2026-11-20
status: PROPOSED
language: PT-BR
---

# ADR-016-PI: Plano de Implementação em 4 Ondas

## Onda 1 — Backend: Telemetria Viva, Velocidade, ETA e Ring Buffer de Atividade (`DEC-003`, `DEC-004`)
1. **`src/backend/services/hydration_orchestrator.py`:**
   - Adicionar `HydrationActivityEvent` e os campos `current_stage`, `current_target`, `started_at`, `elapsed_seconds`, `items_processed_in_run`, `rate_per_minute`, `eta_seconds` e `recent_events` em `HydrationPipelineStatus`.
   - Instrumentar `run_single_step` e `start`/`pause` para atualizar `current_stage`/`current_target` em tempo real durante a execução (não apenas no final do passo), acumular `items_processed_in_run`, calcular `rate_per_minute` e `eta_seconds` e registrar eventos legíveis em `deque(maxlen=15)`.
2. **`src/backend/services/cascading_enricher.py`:**
   - Aceitar callback opcional `on_progress(target_label: str, stage: str)` em `enrich_batch` para reportar o título corrente e o provedor ativo (`IMDb`, `TMDB`, `TVMaze`, `EZTV`, `YTS`, `Wikipédia/Wikidata/Jikan`) ao orquestrador.

## Onda 2 — Frontend: Arquitetura Master-Detail Estilo IDE & Consolidação (`DEC-001`, `DEC-002`)
3. **`src/frontend/src/types.ts`:**
   - Adicionar `HydrationActivityEvent` e os novos campos de telemetria viva em `HydrationPipelineStatus`.
4. **`src/frontend/src/components/settings/`:**
   - Extrair subcomponentes modulares:
     - `SettingsSidebar.tsx` (barra lateral `~240px` com busca rápida + 4 categorias: `Atualização & Catálogo`, `Fontes & Provedores`, `Experiência no Explorar`, `Avançado & Manutenção`);
     - `CatalogUpdatePanel.tsx` (progresso claro, controles unificados sem redundância, velocidade, ETA e Monitor de Atividade);
     - `SourcesProvidersPanel.tsx` (lista limpa de provedores, toggle, teste e drawer/painel lateral de configuração);
     - `ExplorePrefsPanel.tsx` (preferências de selos e filtros com texto humano);
     - `AdvancedMaintenancePanel.tsx` (agendador, reset, detalhes técnicos e contadores de banco recolhidos).
5. **`src/frontend/src/components/StatusConfigView.tsx`:**
   - Orquestrar o layout Master-Detail em 2 colunas substituindo o monólito vertical atual, preservando todas as props públicas (`onHealthChange`, `onDataUpdated`).

## Onda 3 — Linguagem Humana em `HydrationConsoleCard.tsx` & Monitor de Atividade (`DEC-002`, `DEC-004`)
6. **`src/frontend/src/components/HydrationConsoleCard.tsx`:**
   - Traduzir rótulos técnicos (`BOOTSTRAP`/`DELTA`, `Pilar 1B/3`, `Sweep @`, `Recent p.`) para linguagem humana, reduzir o polling de `2500ms` para `1000ms` durante `RUNNING` e exibir velocidade, tempo decorrido, ETA e o **Monitor de Atividade** colapsável (`recent_events`) tanto em `StatusConfigView` quanto na versão compacta de `SourcesView.tsx`.

## Onda 4 — Verificação Hermética, Build & Fechamento (`DEC-005`)
7. **`tests/integration/test_three_pillar_hydration.py`:**
   - Adicionar testes cobrindo `rate_per_minute`, `eta_seconds`, `current_stage`/`current_target` e `recent_events` em `/api/explore/hydration/status` e `run_single_step`.
8. **Gate Final:**
   - Executar `make lint`, `make test`, `cd src/frontend && npx tsc --noEmit && cd ../.. && make build-front`, reconciliar os 6 pilares documentais, marcar `12/12` no `ADR-016-TODO.md`, arquivar via `spx adr archive ADR-016`, rodar `spx docs build` e executar `git commit && git push`.
