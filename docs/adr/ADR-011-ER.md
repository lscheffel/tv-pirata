---
id: ADR-011-ER
type: er
title: "Evidence Record - ADR-011: ADR-011: Consolidação Dual-SSOT (`data/mainstream.db` vs `data/sources.db`), IMDb como Âncora Universal (279k+ Títulos / 4.5M+ Episódios) e Motor SQL Pushdown"
created: 2026-11-17
updated: 2026-11-17
adr_ref: ADR-011
implementation_status: CONSOLIDADA
tasks_completed: 16/16
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-011: ADR-011: Consolidação Dual-SSOT (`data/mainstream.db` vs `data/sources.db`), IMDb como Âncora Universal (279k+ Títulos / 4.5M+ Episódios) e Motor SQL Pushdown

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-011` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-011`](./ADR-011.md) |
| **Título da Decisão** | ADR-011: Consolidação Dual-SSOT (`data/mainstream.db` vs `data/sources.db`), IMDb como Âncora Universal (279k+ Títulos / 4.5M+ Episódios) e Motor SQL Pushdown |
| **Data de Início (Planejamento)** | 2026-11-17 |
| **Data de Conclusão (Auditoria)** | 2026-11-17 |
| **Taxa de Conclusão de Tarefas** | **100%** (16/16 tarefas concluídas) |
| **Branch Git** | `imdb` |
| **Commit SHA de Validação** | `00e0af0` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-011.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-011 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **T1 — Migração Física Dual-SSOT sem Perda de Dados (`DEC-001`)** | ✅ Concluído | Aprovado no Gate |
| `T02` | Consolidar `imdb_catalog.db` + tabelas pessoais/Camada 1 de `data/tv_pirata.db` em `data/mainstream.db` e `data/eztv_metadata.db` + `catalogshow`/`catalogrelease` em `data/sources.db` (com symlinks relativos `imdb_catalog.db -> data/mainstream.db` e `eztv_metadata.db -> data/sources.db`). | ✅ Concluído | Aprovado no Gate |
| `T03` | Garantir colunas `tvmaze_id`, `status`, `air_day_time`, `streaming_providers`, `has_eztv`, `eztv_id`, `eztv_slug`, `eztv_match_type` e índices compostos covering (`idx_shows_filter_cover`, `idx_shows_score_cover`, `idx_shows_votes_rating`, `idx_shows_year_votes`, `idx_shows_type_votes`, `idx_shows_has_eztv`) em `data/mainstream.db.shows`. | ✅ Concluído | Aprovado no Gate |
| `T04` | **T2 — Atualização dos 4 Scripts CLI & Documentação (`DEC-003`, `DEC-005`)** | ✅ Concluído | Aprovado no Gate |
| `T05` | Evoluir `scripts/sync-eztv-bade.py` para usar `data/mainstream.db` + `data/sources.db` e propagar `status`, `tvmaze_id`, `air_day_time` e `streaming_providers` além de `has_eztv`/`eztv_id`, executando o cruzamento real sobre os 279.117 títulos (`607` séries marcadas). | ✅ Concluído | Aprovado no Gate |
| `T06` | Atualizar paths padrão em `scripts/imdb-metadata-catalog.py`, `scripts/eztv-metadata-catalog.py`, `scripts/sync_catalog.py` e `imdb-update-usage.md`. | ✅ Concluído | Aprovado no Gate |
| `T07` | **T3 — Camada de Persistência Dual-SSOT & Modelos SQLModel (`DEC-001`, `DEC-002`)** | ✅ Concluído | Aprovado no Gate |
| `T08` | Adicionar `IMDbCatalogShow` e `IMDbEpisodeCatalog` isolados em `imdb_metadata` em `src/backend/models/catalog_domain.py`. | ✅ Concluído | Aprovado no Gate |
| `T09` | Atualizar `src/backend/core/database.py` com `MAINSTREAM_DATABASE_URL` (`data/mainstream.db`), `SOURCES_DATABASE_URL` (`data/sources.db`), aliases retrocompatíveis e índices covering em `init_db()`. | ✅ Concluído | Aprovado no Gate |
| `T10` | Atualizar `src/backend/api/torrents.py` e `src/backend/repositories/catalog.py` para priorizar `sources.db` com fallback defensivo. | ✅ Concluído | Aprovado no Gate |
| `T11` | **T4 — Motor SQL Pushdown para 279k+ Títulos (`DEC-004`)** | ✅ Concluído | Aprovado no Gate |
| `T12` | Refatorar `DiscoveryEngineRepository` em `src/backend/repositories/discovery_engine.py` com motor SQL Pushdown sobre `IMDbCatalogShow` (`LIMIT`/`OFFSET`, filtros booleanos, `has_eztv`, busca, facetas cacheadas e dossiê completo com `episodes_catalog` sem full-table scan). | ✅ Concluído | Aprovado no Gate |
| `T13` | Atualizar `src/backend/api/explore.py` para aceitar identificadores `ttXXXXXXX` e `imdb_num`. | ✅ Concluído | Aprovado no Gate |
| `T14` | **T5 — Testes Herméticos Dual-SSOT, Benchmark em 279k Títulos & Quality Gate** | ✅ Concluído | Aprovado no Gate |
| `T15` | Criar `tests/integration/test_mainstream_sources_ssot.py` cobrindo queries SQL Pushdown, dossiê IMDb+TMDB+EZTV e `sources.db`. | ✅ Concluído | Aprovado no Gate |
| `T16` | Executar `ruff check src/ tests/` (`All checks passed!`), `pytest -q` (`64 passed`), `make build-front` e benchmark empírico sobre os 279.117 títulos em `data/mainstream.db`. | ✅ Concluído | Aprovado no Gate |

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

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-011` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-011.md`](./archive/ADR-011.md)
* **Blueprint:** [`docs/adr/archive/ADR-011-BP.md`](./archive/ADR-011-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-011-TODO.md`](./archive/ADR-011-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-011-PI.md`](./archive/ADR-011-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-011
DATA: 2026-11-17
HASH DE VALIDAÇÃO: CC326B7F331015C4
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
