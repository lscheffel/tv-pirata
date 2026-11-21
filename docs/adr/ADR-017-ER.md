---
id: ADR-017-ER
type: er
title: "Evidence Record - ADR-017: Paralelismo Bifurcado (Fan-out HTTP com Semáforos por Domínio -> Fan-in SQLite) & Correção de Exaustão 422 do Sidecar"
created: 2026-11-20
updated: 2026-11-20
adr_ref: ADR-017
implementation_status: CONSOLIDADA
tasks_completed: 12/12
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-017: Paralelismo Bifurcado (Fan-out HTTP com Semáforos por Domínio -> Fan-in SQLite) & Correção de Exaustão 422 do Sidecar

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-017` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-017`](./ADR-017.md) |
| **Título da Decisão** | Paralelismo Bifurcado (Fan-out HTTP com Semáforos por Domínio -> Fan-in SQLite) & Correção de Exaustão 422 do Sidecar |
| **Data de Início (Planejamento)** | 2026-11-20 |
| **Data de Conclusão (Auditoria)** | 2026-11-20 |
| **Taxa de Conclusão de Tarefas** | **100%** (12/12 tarefas concluídas) |
| **Branch Git** | `UI-UX` |
| **Commit SHA de Validação** | `9d2ecc4` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-017.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-017 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **TODO-17.01 (`DEC-001`, `DEC-005`):** Atualizar `get_recent_torrents` em `src/backend/sidecar/torrent_api_sidecar.py` para aceitar `page >= 1` sem retornar `422` além da pág. 20 (retornando `data: []`), e adicionar `--workers 4` em `make run-sidecar` no `Makefile`. | ✅ Concluído | Aprovado no Gate |
| `T02` | **TODO-17.02 (`DEC-001`):** Tratar HTTP `422` e `[]` em `TorrentApiPySourceAdapter.fetch_recent_candidates` (`src/backend/providers/sources/torrent_api_py_adapter.py`) como exaustão limpa (`return candidates`), e em `SourcesRegistryService.sync_source` marcar `exhausted=True` quando `mode=="baseline" and start_page > 1 and indexed == 0`. | ✅ Concluído | Aprovado no Gate |
| `T03` | **TODO-17.03 (`DEC-002`):** Criar `src/backend/core/domain_concurrency.py` com `DomainSemaphoreRegistry` (`WeakKeyDictionary` por event loop) e factory `create_shared_http_client()` Keep-Alive. | ✅ Concluído | Aprovado no Gate |
| `T04` | **TODO-17.04 (`DEC-002`, `DEC-003`):** Injetar `client` compartilhado e semáforos em `TorrentApiPySourceAdapter` (`tgx=4`, `glodls=4`, `nyaasi=2`, `bitsearch=2`, `sidecar=4`). | ✅ Concluído | Aprovado no Gate |
| `T05` | **TODO-17.05 (`DEC-002`, `DEC-003`):** Paralelizar páginas em `YIFYSourceAdapter.sync` (`start_page` + `asyncio.gather` das páginas restantes até `total_pages` sob semáforo `yify=4`) mantendo `Batch SELECT/UPSERT` único no Fan-in. | ✅ Concluído | Aprovado no Gate |
| `T06` | **TODO-17.06 (`DEC-003`):** Paralelizar consultas de `SourcesRegistryService.sweep_canonical_catalog_presence` via `asyncio.gather(..., return_exceptions=True)` com semáforo por domínio e Fan-in SQLite único. | ✅ Concluído | Aprovado no Gate |
| `T07` | **TODO-17.07 (`DEC-003`):** Refatorar `CascadingMetadataEnricher.enrich_batch` (`src/backend/services/cascading_enricher.py`) em coleta HTTP paralela (Tiers 1–5 em paralelo por obra com semáforos `tmdb=8`, `imdb/tvmaze/jikan=2`, `yify=4`, seguida de Tier 6 Wikidata Batch + Wikipédia/Jikan paralelos) e Fan-in SQLite único (`cross_db_self_heal` + `_apply_coalesce` + commits). | ✅ Concluído | Aprovado no Gate |
| `T08` | **TODO-17.08 (`DEC-003`, `DEC-004`):** Orquestrar execução paralela entre fontes P2P e metadados em `HydrationOrchestratorService.run_single_step`, elevar lotes padrão (`yts_pages=6`, `sweep_batch=12`, `meta_batch=20`) em `hydration_orchestrator.py` e `explore.py`, e atualizar telemetria multi-faixa. | ✅ Concluído | Aprovado no Gate |
| `T09` | **TODO-17.09 (`DEC-001`, `DEC-002`):** Adicionar testes em `tests/integration/test_three_pillar_hydration.py` cobrindo `422 -> exhausted=True -> sweep`, zero itens inéditos em `page > 1` e `DomainSemaphoreRegistry` em múltiplos event loops. | ✅ Concluído | Aprovado no Gate |
| `T10` | **TODO-17.10 (`DEC-003`, `DEC-004`):** Adicionar testes em `tests/integration/test_three_pillar_hydration.py` validando paralelismo limitado por semáforo (Tiers 1–5 e fontes P2P) e Fan-in SQLite sem contenção. | ✅ Concluído | Aprovado no Gate |
| `T11` | **TODO-17.11 (`DEC-001`..`DEC-005`):** Executar `make lint && make test && cd src/frontend && npx tsc --noEmit && cd ../.. && make build-front` com `100%` de aprovação. | ✅ Concluído | Aprovado no Gate |
| `T12` | **TODO-17.12 (`DEC-001`..`DEC-005`):** Reconciliar os 6 pilares documentais, marcar `12/12` em `ADR-017-TODO.md`, executar `spx adr archive ADR-017`, atualizar `docs/adr/ADR-INDEX.md`, rodar `spx docs build` e executar `git commit && git push`. | ✅ Concluído | Aprovado no Gate |

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

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-017` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-017.md`](./archive/ADR-017.md)
* **Blueprint:** [`docs/adr/archive/ADR-017-BP.md`](./archive/ADR-017-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-017-TODO.md`](./archive/ADR-017-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-017-PI.md`](./archive/ADR-017-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-017
DATA: 2026-11-20
HASH DE VALIDAÇÃO: 27C1BCD29EF10074
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
