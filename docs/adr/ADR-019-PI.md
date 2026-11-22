---
adr_ref: ADR-019
title: "Plano de Implementação — ADR-019"
status: PROPOSED
updated: "2026-11-22"
---

# ADR-019 Plano de Implementação (PI)

## Fase 1 — `YIFYSourceAdapter` (`src/backend/providers/sources/yify_adapter.py`)
1. Adicionar `mirror_strategy` em `YIFYAdapterConfig` e atualizar `_candidate_endpoints`.
2. Validar `info_hash` em `_movies_to_presence_candidates` e `_movies_to_candidates`.
3. Aceitar `mainstream_session: Optional[Session] = None` em `persist_sync_candidates` para filtrar `tvSeries`/`tvMiniSeries`.

## Fase 2 — `SourcesRegistryService` e `HydrationOrchestratorService`
1. Em `hydration_orchestrator.py`, passar `mainstream_session` ao chamar `YIFYSourceAdapter.persist_sync_candidates`.
2. Em `sources_registry.py` (`get_releases_for_imdb`), limpar `yts:presence:*` da obra quando `outcome.status == "ok"` e `not outcome.releases` (sem `q_override`).
3. Em `sources_registry.py` (`prune_obsolete_releases`), remover `yts:presence:*` cujos `imdb_id`s sejam `tvSeries`/`tvMiniSeries` no `mainstream.db`.

## Fase 3 — Testes & Verificação
1. Adicionar testes em `tests/integration/test_source_plugins_contract.py`.
2. Rodar `make lint && make test`.
