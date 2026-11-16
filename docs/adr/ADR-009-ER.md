---
id: ADR-009-ER
type: er
title: "Evidence Record - ADR-009: Separação de Bases (tv_pirata.db vs eztv_metadata.db) + Entrelaçamento EZTV"
created: 2026-11-15
updated: 2026-11-15
adr_ref: ADR-009
implementation_status: CONSOLIDADA
tasks_completed: 7/7
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-009: Separação de Bases (tv_pirata.db vs eztv_metadata.db) + Entrelaçamento EZTV

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-009` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-009`](./ADR-009.md) |
| **Título da Decisão** | Separação de Bases (tv_pirata.db vs eztv_metadata.db) + Entrelaçamento EZTV |
| **Data de Início (Planejamento)** | 2026-11-13 |
| **Data de Conclusão (Auditoria)** | 2026-11-15 |
| **Taxa de Conclusão de Tarefas** | **100%** (7/7 tarefas concluídas) |
| **Branch Git** | `develop` |
| **Commit SHA de Validação** | `379e30b` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-009.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-009 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **T1 (Persistência Dual):** Configurar `EZTV_DATABASE_URL`, `eztv_engine`, `init_eztv_db()` e `get_eztv_session()` em `src/backend/core/database.py`, chamando `init_eztv_db()` no `lifespan` em `src/backend/main.py`. | ✅ Concluído | Aprovado no Gate |
| `T02` | **T2 (Modelos EZTV):** Criar `src/backend/models/eztv_db.py` com `EZTVShow` (`shows`) e `EZTVEpisodeCatalog` (`episodes_catalog`) compatíveis com `data/eztv_metadata.db`. | ✅ Concluído | Aprovado no Gate |
| `T03` | **T3 (Repositório Catálogo EZTV):** Refatorar `src/backend/repositories/catalog.py` e `src/backend/api/catalog.py` para consumir `eztv_metadata.db` como fonte primária (listagem, filtros, gêneros, seções, stats, detalhes + episódios e enriquecimento via `TVMazeProvider`/`TMDBProvider`). | ✅ Concluído | Aprovado no Gate |
| `T04` | **T4 (Cruzamento Explore ↔ EZTV):** Atualizar `src/backend/repositories/discovery_engine.py` e `src/backend/api/explore.py` para cruzar `MediaWork` com `eztv_metadata.db` (`imdb_id` forte + fallback por título/slug) e expor `eztv_available` e `eztv_show_id`. | ✅ Concluído | Aprovado no Gate |
| `T05` | **T5 (Frontend Contratos e UI):** Atualizar `src/frontend/src/types.ts`, `src/frontend/src/services/api.ts`, `ExplorerView.tsx` (badge EZTV no cartaz e no dossiê) e `CatalogView.tsx` (consumo de `eztv_metadata.db` com episódios e metadados). | ✅ Concluído | Aprovado no Gate |
| `T06` | **T6 (Testes Herméticos):** Criar testes unitários e de integração em `tests/` com bancos isolados em memória (`get_session` + `get_eztv_session`). | ✅ Concluído | Aprovado no Gate |
| `T07` | **T7 (Validação Final):** Executar `make test`, `make lint` e `make build-front`. | ✅ Concluído | Aprovado no Gate |

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

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-009` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-009.md`](./archive/ADR-009.md)
* **Blueprint:** [`docs/adr/archive/ADR-009-BP.md`](./archive/ADR-009-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-009-TODO.md`](./archive/ADR-009-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-009-PI.md`](./archive/ADR-009-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-009
DATA: 2026-11-15
HASH DE VALIDAÇÃO: 3C7326154BCD578A
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
