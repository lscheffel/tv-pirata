---
id: ADR-013-ER
type: er
title: "Evidence Record - ADR-013: Sistema Extensível de Plugins para Fontes Externas (Adapters 1:N, Torrent-Api-py, Torznab, Lazy-Cache & Challenge Manual)"
created: 2026-11-19
updated: 2026-11-19
adr_ref: ADR-013
implementation_status: CONSOLIDADA
tasks_completed: 16/16
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-013: Sistema Extensível de Plugins para Fontes Externas (Adapters 1:N, Torrent-Api-py, Torznab, Lazy-Cache & Challenge Manual)

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-013` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-013`](./ADR-013.md) |
| **Título da Decisão** | Sistema Extensível de Plugins para Fontes Externas (Adapters 1:N, Torrent-Api-py, Torznab, Lazy-Cache & Challenge Manual) |
| **Data de Início (Planejamento)** | 2026-11-19 |
| **Data de Conclusão (Auditoria)** | 2026-11-19 |
| **Taxa de Conclusão de Tarefas** | **100%** (16/16 tarefas concluídas) |
| **Branch Git** | `UI-UX` |
| **Commit SHA de Validação** | `48f4c5b` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-013.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-013 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **TODO-13.01 (`DEC-001`):** Criar pacote `src/backend/providers/sources/` com `base.py` (`BaseSourceAdapter`, `@register_source_adapter`, `AdapterSearchOutcome`, `SourceDiagnostic`) e autodiscovery via `pkgutil.iter_modules` com isolamento de exceções por módulo. | ✅ Concluído | Aprovado no Gate |
| `T02` | **TODO-13.02 (`DEC-001`):** Estender `ExternalSourceRecord` (`adapter_key`, `source_kind`, `config_json`, `priority`, `cooldown_until`) e `ExternalRelease` (`matched_by`, `match_confidence`, `last_checked_at`) em `src/backend/models/sources_db.py`, mantendo `eztv_metadata` intacta. | ✅ Concluído | Aprovado no Gate |
| `T03` | **TODO-13.03 (`DEC-001`):** Implementar migração `ALTER TABLE ADD COLUMN` idempotente em `init_eztv_db()` (`src/backend/core/database.py`) para bases `sources.db` existentes com preenchimento seguro de `adapter_key` padrão. | ✅ Concluído | Aprovado no Gate |
| `T04` | **TODO-13.04 (`DEC-004`):** Implementar utilitários de segurança Zero-Trust: whitelist estrita de URL (`validate_safe_url` aceitando apenas `http`, `https`, `magnet`), mascaramento de campos `secret=True` na saída da API e preservação via sentinel (`RT13-02`) em atualizações parciais. | ✅ Concluído | Aprovado no Gate |
| `T05` | **TODO-13.05 (`DEC-002`):** Migrar `EZTVSourceProvider` e `YIFYSourceProvider` para `src/backend/providers/sources/` (`eztv_adapter.py`, `yify_adapter.py`) suportando rotação de `mirrors[]` e `search()` sem quebrar rotas/testes legados. | ✅ Concluído | Aprovado no Gate |
| `T06` | **TODO-13.06 (`DEC-002`):** Implementar adapters HTTP enxutos sobre `httpx`: `torrent_api_py_adapter.py` (bridge para `Ryuk-me/Torrent-Api-py` com presets `1337x`, `tgx`, `nyaasi`, `piratebay`), `torznab_adapter.py` (XML/JSON Prowlarr/Jackett) e `unique_web_adapter.py` (detecção de challenge anti-bot sem bypass). | ✅ Concluído | Aprovado no Gate |
| `T07` | **TODO-13.07 (`DEC-002`):** Implementar *circuit breaker* em **2 níveis** no `SourcesRegistryService` (cooldown por `source_key` vs. cooldown compartilhado por host base do sidecar em erros TCP/timeout). | ✅ Concluído | Aprovado no Gate |
| `T08` | **TODO-13.08 (`DEC-003`):** Implementar motor *Lazy-Cache* (TTL `24h` via `last_checked_at` com fallback offline) integrado ao `EntityResolutionService` (`>= 0.85` grava `ExternalRelease` + invalida cache; `0.60–0.84` retorna apenas em `approx_matches` na sessão). | ✅ Concluído | Aprovado no Gate |
| `T09` | **TODO-13.09 (`DEC-004`, `DEC-005`):** Estender `src/backend/api/sources.py`: endpoints `GET /api/sources/adapters`, `POST /api/sources`, `PATCH /api/sources/{source_key}`, `DELETE /api/sources/{source_key}` (protegendo `eztv`), `POST /api/sources/{source_key}/test` e retorno estendido (`source_diagnostics`, `approx_matches`, `live`, `q_override`) em `/api/sources/releases`. | ✅ Concluído | Aprovado no Gate |
| `T10` | **TODO-13.10 (`DEC-005`):** Deshardcodar `DiscoveryEngineRepository` (`query_works`, `_build_imdb_facets`) e `canonical_taxonomy.py`, substituindo listas estáticas de fontes externas por resolução dinâmica contra instâncias/registros de `sources.db` com invalidação de `discovery_cache`. | ✅ Concluído | Aprovado no Gate |
| `T11` | **TODO-13.11 (`DEC-005`):** Evoluir `StatusConfigView.tsx` com lista expansível de instâncias (`enabled`, prioridade, `mirrors[]`), formulário dinâmico renderizado por `config_schema` (com proteção sentinel de segredos), botão **"Testar Conexão"** e fluxo **"+ Adicionar Fonte"**. | ✅ Concluído | Aprovado no Gate |
| `T12` | **TODO-13.12 (`DEC-003`):** Atualizar `TorrentModal.tsx` para busca *Lazy* com `AbortController`, botão **"Buscar Ao Vivo"**, campo editável de refino de busca e exibição separada de `approx_matches` com tag *"Correspondência aproximada (não salva)"*. | ✅ Concluído | Aprovado no Gate |
| `T13` | **TODO-13.13 (`DEC-004`):** Implementar no `TorrentModal.tsx` barra/indicador de diagnóstico por fonte e cartão explícito `44×44px` **"Abrir Página no Navegador"** (`challenge_url` validada `http/https` + `rel="noopener noreferrer"`) + **"Tentar Novamente"** quando `status === "challenge_required"`. | ✅ Concluído | Aprovado no Gate |
| `T14` | **TODO-13.14 (`DEC-005`):** Deshardcodar chips de fontes em `ExplorerView.tsx` (alimentados dinamicamente por `GET /api/sources/summary` + filtro agregado `"Com Mídia"`) e atualizar `SourcesView.tsx` / `types.ts` / `api.ts` com contratos tipados. | ✅ Concluído | Aprovado no Gate |
| `T15` | **TODO-13.15 (`DEC-005`):** Criar `tests/integration/test_source_plugins_contract.py` parametrizando todos os adapters descobertos via `respx` (timeout, `403`/challenge, URL maliciosa `javascript:` bloqueada, matching `< 0.85` não persistido, preservação de segredos e migração idempotente `sources.db`). | ✅ Concluído | Aprovado no Gate |
| `T16` | **TODO-13.16 (`DEC-001`..`DEC-005`):** Validar `make lint`, `make test`, `npx tsc --noEmit`, `make build-front`, atualizar os 6 pilares documentais PT-BR e arquivar via `spx adr archive ADR-013`. | ✅ Concluído | Aprovado no Gate |

---

## 4. Verificação de Integridade e Validações Realizadas

| Dimensão de Validação | Método de Verificação | Veredito |
|---|---|:---:|
| **Conformidade de Escopo (DAG)** | Inspeção estrita contra TODO / PI | **PASSOU** ✅ |
| **Isolamento de Escopo** | Scope Isolation / Offloading para Registry | **PASSOU** ✅ |
| **Sincronização Documental** | Atualização de referências e status | **PASSOU** ✅ |
| **Rastreabilidade de Artefatos** | Decision Set completo (ADR, BP, TODO, PI) | **PASSOU** ✅ |

---

## 5. Gestão de Débitos Técnicos (Tech Debt Registry)

### Débitos Mitigados por esta ADR

- Nenhum débito pré-existente foi explicitamente vinculado a esta ADR.

### Débitos Incidentais Descarregados Durante a Execução

- Zero débitos secundários registrados durante o ciclo desta ADR.

---

## 6. Rastreabilidade e Arquivamento de Artefatos

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-013` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-013.md`](./archive/ADR-013.md)
* **Blueprint:** [`docs/adr/archive/ADR-013-BP.md`](./archive/ADR-013-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-013-TODO.md`](./archive/ADR-013-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-013-PI.md`](./archive/ADR-013-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-013
DATA: 2026-11-19
HASH DE VALIDAÇÃO: 6C14389102490D4E
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
