---
adr_ref: ADR-020
title: "TODO — Hidratação Finita (Novidades vs. Varredura) e UX em 2 Camadas"
status: IMPLEMENTED (ELEVATED)
updated: "2026-11-22"
---

# ADR-020 Checklist de Execução (TODO)

- [x] **T01:** Adicionar `run_mode`, `sweep_min_votes`, `sweep_enabled_sources`, `recent_pages_per_source`, `last_novidades_at`, `last_novidades_count` e `vote_tier_counts`/`nyaasi_sweep_totals` em `hydration_orchestrator.py` (`DEC-001`, `DEC-002`).
- [x] **T02:** Atualizar `SourcesRegistryService.select_sweep_works` para aceitar `min_votes: int = 1000` (`DEC-002`).
- [x] **T03:** Implementar lógica finita de `run_mode == "novidades"` (1 ciclo completo sem mutar `recent_exhausted` e encerrando como `COMPLETED`) e `run_mode == "varredura"` (pulando fontes com `bootstrap_completed=True` e não habilitadas em `sweep_enabled_sources`), além de `update_config` reabrindo `bootstrap_completed` ao ampliar o corte (`DEC-001`, `DEC-002`, `AMP-01`..`AMP-03`).
- [x] **T04:** Expor `run_mode` em `/hydration/start` e criar `POST /api/explore/hydration/config` em `src/backend/api/explore.py` (`DEC-001`, `DEC-002`).
- [x] **T05:** Atualizar `src/frontend/src/types.ts` e `src/frontend/src/services/api.ts` (`DEC-001`..`DEC-003`).
- [x] **T06:** Redesenhar `HydrationConsoleCard.tsx` com **Modo Simples** (padrão: última atualização, 1 linha de status vivo, barra de progresso, ETA, botões `Atualizar Novidades` e `Varredura Profunda`) e **Modo Avançado** (toggle persistido no `localStorage` com configurações de `sweep_min_votes`, checkboxes por fonte, `recent_pages`, Mainstream, P2P, Tabela Técnica e Monitor de Atividade) (`DEC-003`, `AMP-04`).
- [x] **T07:** Adicionar testes herméticos cobrindo `run_mode="novidades"`, `run_mode="varredura"` pulando `DELTA`, `sweep_min_votes` dinâmico e `POST /api/explore/hydration/config`.
- [x] **T08:** Executar `make lint && make test && make build-front` com 100% de aprovação.
