---
id: ADR-003-TODO
title: "TODO: Implementação do Contrato Unificado, Provedores com Fallback e EZTV"
adr_ref: ADR-003
created: "2026-11-11"
status: CONSOLIDATED
---

# Checklist de Implementação — ADR-003

- [x] Criar fixtures determinísticas JSON (`tests/fixtures/tmdb_show.json`, `tests/fixtures/tvmaze_show.json`, `tests/fixtures/eztv_torrents.json`).
- [x] Implementar modelos canônicos em `src/backend/models/unified.py`.
- [x] Implementar contrato abstrato `BaseMetadataProvider` em `src/backend/providers/base.py`.
- [x] Implementar cliente `TMDBProvider` em `src/backend/providers/tmdb.py`.
- [x] Implementar cliente `TVMazeProvider` em `src/backend/providers/tvmaze.py`.
- [x] Implementar cliente `EZTVProvider` em `src/backend/providers/eztv.py`.
- [x] Implementar serviço de resiliência `ResilientDiscoveryService` com timeout e fallback em `src/backend/providers/discovery_service.py`.
- [x] Implementar suíte de testes unitários herméticos com `pytest` e `respx`.
- [x] Implementar teste de integração para o fallback dinâmico TMDB -> TVMaze.
- [x] Validar aprovação completa no pre-commit Quality Gate (`make lint` e `make test`).
