---
adr_ref: ADR-019
title: "TODO — Integridade do Acervo YIFY/YTS e Auto-Cura de Presença Fantasma"
status: IMPLEMENTED (ELEVATED)
updated: "2026-11-22"
---

# ADR-019 Checklist de Execução (TODO)

- [x] **T01:** Adicionar `mirror_strategy` (`official_first` | `accel_first`) em `YIFYAdapterConfig` e ajustar `_candidate_endpoints` em `src/backend/providers/sources/yify_adapter.py` (`DEC-001`).
- [x] **T02:** Adicionar validação estrita de `info_hash` (`40` hex ou `32` base32) e `seeds >= 1` em `_movies_to_presence_candidates` e `_movies_to_candidates`, e filtrar `tvSeries`/`tvMiniSeries` via `mainstream_session` em `persist_sync_candidates` (`DEC-003`).
- [x] **T03:** Passar `mainstream_session` para `YIFYSourceAdapter.persist_sync_candidates` em `HydrationOrchestratorService.run_single_step` (`DEC-003`).
- [x] **T04:** Implementar auto-cura (`replace_on_empty_success`) em `SourcesRegistryService.get_releases_for_imdb` para remover `yts:presence:*` quando busca ao vivo padrão retornar `ok` com 0 releases (`DEC-002`).
- [x] **T05:** Estender `SourcesRegistryService.prune_obsolete_releases` para limpar marcadores `yts:presence:*` vinculados a `tvSeries`/`tvMiniSeries` em `mainstream.db` (`DEC-004`).
- [x] **T06:** Adicionar testes herméticos (com `respx`) cobrindo `mirror_strategy`, exclusão de `tvSeries` na ingestão/poda e remoção automática de `yts:presence:` no Stage 2 JIT vazio.
- [x] **T07:** Executar `make lint && make test` com 100% de aprovação.
