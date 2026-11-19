---
id: ADR-013-PI
parent_adr: ADR-013
title: "Plano de Implementação Incremental — ADR-013"
status: ACCEPTED
implementation_status: PENDENTE
language: PT-BR
---

# ADR-013-PI: Plano de Implementação em 5 Ondas

## Estratégia de Execução (`Blast Radius = 8.5 / CRITICAL`)

Execução aditiva incremental mantendo 100% dos testes existentes (`69+`) e o build TypeScript/Vite verdes ao final de cada onda, sem alterar `eztv_metadata` nem introduzir dependências HTML no `pyproject.toml`.

---

## Onda 1 — Fundação Plugável, Segurança & Migração (`TODO-13.01` a `TODO-13.04`)
1. Criar `src/backend/providers/sources/base.py` e `__init__.py` (`pkgutil` autodiscovery com isolamento de erro).
2. Adicionar colunas em `ExternalSourceRecord` e `ExternalRelease` (`sources_db.py`) + `ALTER TABLE` idempotente em `init_eztv_db()`.
3. Implementar `validate_safe_url()` e mascaramento/preservação sentinel de segredos em `config_json`.
- **Gate da Onda 1:** `pytest` passando com testes unitários de autodiscovery, migração idempotente, whitelist URI e proteção de segredos.

## Onda 2 — Adapters Concretos, Circuit Breaker & Lazy-Cache (`TODO-13.05` a `TODO-13.08`)
1. Portar `EZTV` e `YIFY` para adapters; implementar `torrent_api_py_adapter.py`, `torznab_adapter.py` e `unique_web_adapter.py` usando `httpx`.
2. Implementar *circuit breaker* de 2 níveis e motor *Lazy-Cache* (TTL 24h + fallback offline + `EntityResolutionService` `>= 0.85`).
- **Gate da Onda 2:** `pytest` + `respx` validando `sync()`, `search()`, cooldown 2 níveis, fallback de mirrors e `challenge_required`.

## Onda 3 — APIs Dinâmicas & Deshardcoding Core (`TODO-13.09` a `TODO-13.10`)
1. Expor `/api/sources/adapters`, CRUD de instâncias, `/test` e `/releases` estendido (`source_diagnostics`, `approx_matches`).
2. Substituir listas hardcoded de fontes externas em `DiscoveryEngineRepository` e `canonical_taxonomy.py` por consulta dinâmica com invalidação de cache.
- **Gate da Onda 3:** `make test` e `make lint` 100% verdes.

## Onda 4 — UI Dinâmica, Modal CAPTCHA & Config CRUD (`TODO-13.11` a `TODO-13.14`)
1. Atualizar `types.ts` e `api.ts`.
2. Evoluir `StatusConfigView.tsx` (`+ Adicionar Fonte`, formulário por schema, testar conexão) e `ExplorerView.tsx` (chips dinâmicos).
3. Atualizar `TorrentModal.tsx` (`source_diagnostics`, botão manual `44×44px` de CAPTCHA/Challenge, *"Buscar Ao Vivo"*, refino manual e `approx_matches`).
- **Gate da Onda 4:** `npx tsc --noEmit` + `make build-front` sem erros ou warnings de tipagem.

## Onda 5 — Contrato Universal de Testes & Fechamento (`TODO-13.15` a `TODO-13.16`)
1. Adicionar `tests/integration/test_source_plugins_contract.py` parametrizando todos os adapters descobertos.
2. Rodar `./scripts/quality_gate.sh`, atualizar pilares documentais PT-BR, compilar portal `spx docs build` e arquivar `ADR-013`.
