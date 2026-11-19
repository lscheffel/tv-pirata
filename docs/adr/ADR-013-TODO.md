---
id: ADR-013-TODO
parent_adr: ADR-013
title: "Checklist Executável de Implementação — ADR-013"
status: ACCEPTED
implementation_status: PENDENTE
language: PT-BR
---

# ADR-013-TODO: Lista de Tarefas Verificáveis (1:1 com o Decision Ledger)

> [!IMPORTANT]
> Todas as tarefas abaixo permanecem estritamente desmarcadas (`[ ]`) até a execução implementada e validada pelos portões automáticos (`ruff`, `pytest`, `tsc`, `vite build`).

## Onda 1 — Fundação Plugável, Segurança Zero-Trust & Migração Aditiva (`sources.db`)

- [ ] **TODO-13.01 (`DEC-001`):** Criar pacote `src/backend/providers/sources/` com `base.py` (`BaseSourceAdapter`, `@register_source_adapter`, `AdapterSearchOutcome`, `SourceDiagnostic`) e autodiscovery via `pkgutil.iter_modules` com isolamento de exceções por módulo.
- [ ] **TODO-13.02 (`DEC-001`):** Estender `ExternalSourceRecord` (`adapter_key`, `source_kind`, `config_json`, `priority`, `cooldown_until`) e `ExternalRelease` (`matched_by`, `match_confidence`, `last_checked_at`) em `src/backend/models/sources_db.py`, mantendo `eztv_metadata` intacta.
- [ ] **TODO-13.03 (`DEC-001`):** Implementar migração `ALTER TABLE ADD COLUMN` idempotente em `init_eztv_db()` (`src/backend/core/database.py`) para bases `sources.db` existentes com preenchimento seguro de `adapter_key` padrão.
- [ ] **TODO-13.04 (`DEC-004`):** Implementar utilitários de segurança Zero-Trust: whitelist estrita de URL (`validate_safe_url` aceitando apenas `http`, `https`, `magnet`), mascaramento de campos `secret=True` na saída da API e preservação via sentinel (`RT13-02`) em atualizações parciais.

## Onda 2 — Adapters Concretos, Circuit Breaker 2 Níveis & Motor Lazy-Cache

- [ ] **TODO-13.05 (`DEC-002`):** Migrar `EZTVSourceProvider` e `YIFYSourceProvider` para `src/backend/providers/sources/` (`eztv_adapter.py`, `yify_adapter.py`) suportando rotação de `mirrors[]` e `search()` sem quebrar rotas/testes legados.
- [ ] **TODO-13.06 (`DEC-002`):** Implementar adapters HTTP enxutos sobre `httpx`: `torrent_api_py_adapter.py` (bridge para `Ryuk-me/Torrent-Api-py` com presets `1337x`, `tgx`, `nyaasi`, `piratebay`), `torznab_adapter.py` (XML/JSON Prowlarr/Jackett) e `unique_web_adapter.py` (detecção de challenge anti-bot sem bypass).
- [ ] **TODO-13.07 (`DEC-002`):** Implementar *circuit breaker* em **2 níveis** no `SourcesRegistryService` (cooldown por `source_key` vs. cooldown compartilhado por host base do sidecar em erros TCP/timeout).
- [ ] **TODO-13.08 (`DEC-003`):** Implementar motor *Lazy-Cache* (TTL `24h` via `last_checked_at` com fallback offline) integrado ao `EntityResolutionService` (`>= 0.85` grava `ExternalRelease` + invalida cache; `0.60–0.84` retorna apenas em `approx_matches` na sessão).

## Onda 3 — APIs Dinâmicas & Deshardcoding no Backend

- [ ] **TODO-13.09 (`DEC-004`, `DEC-005`):** Estender `src/backend/api/sources.py`: endpoints `GET /api/sources/adapters`, `POST /api/sources`, `PATCH /api/sources/{source_key}`, `DELETE /api/sources/{source_key}` (protegendo `eztv`), `POST /api/sources/{source_key}/test` e retorno estendido (`source_diagnostics`, `approx_matches`, `live`, `q_override`) em `/api/sources/releases`.
- [ ] **TODO-13.10 (`DEC-005`):** Deshardcodar `DiscoveryEngineRepository` (`query_works`, `_build_imdb_facets`) e `canonical_taxonomy.py`, substituindo listas estáticas de fontes externas por resolução dinâmica contra instâncias/registros de `sources.db` com invalidação de `discovery_cache`.

## Onda 4 — Evolução de Frontend (`StatusConfigView`, `TorrentModal`, `ExplorerView`)

- [ ] **TODO-13.11 (`DEC-005`):** Evoluir `StatusConfigView.tsx` com lista expansível de instâncias (`enabled`, prioridade, `mirrors[]`), formulário dinâmico renderizado por `config_schema` (com proteção sentinel de segredos), botão **"Testar Conexão"** e fluxo **"+ Adicionar Fonte"**.
- [ ] **TODO-13.12 (`DEC-003`):** Atualizar `TorrentModal.tsx` para busca *Lazy* com `AbortController`, botão **"Buscar Ao Vivo"**, campo editável de refino de busca e exibição separada de `approx_matches` com tag *"Correspondência aproximada (não salva)"*.
- [ ] **TODO-13.13 (`DEC-004`):** Implementar no `TorrentModal.tsx` barra/indicador de diagnóstico por fonte e cartão explícito `44×44px` **"Abrir Página no Navegador"** (`challenge_url` validada `http/https` + `rel="noopener noreferrer"`) + **"Tentar Novamente"** quando `status === "challenge_required"`.
- [ ] **TODO-13.14 (`DEC-005`):** Deshardcodar chips de fontes em `ExplorerView.tsx` (alimentados dinamicamente por `GET /api/sources/summary` + filtro agregado `"Com Mídia"`) e atualizar `SourcesView.tsx` / `types.ts` / `api.ts` com contratos tipados.

## Onda 5 — Suíte Contratual Universal & Fechamento de Governança

- [ ] **TODO-13.15 (`DEC-005`):** Criar `tests/integration/test_source_plugins_contract.py` parametrizando todos os adapters descobertos via `respx` (timeout, `403`/challenge, URL maliciosa `javascript:` bloqueada, matching `< 0.85` não persistido, preservação de segredos e migração idempotente `sources.db`).
- [ ] **TODO-13.16 (`DEC-001`..`DEC-005`):** Validar `make lint`, `make test`, `npx tsc --noEmit`, `make build-front`, atualizar os 6 pilares documentais PT-BR e arquivar via `spx adr archive ADR-013`.
