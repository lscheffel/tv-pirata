---
id: ADR-010-ER
type: er
title: "Evidence Record - ADR-010: ADR-010: Otimização de Desempenho de Leitura Dual-SQLite, Estatísticas Materializadas, Cache Escopado por Engine e FTS5"
created: 2026-11-15
updated: 2026-11-15
adr_ref: ADR-010
implementation_status: CONSOLIDADA
tasks_completed: 21/21
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-010: ADR-010: Otimização de Desempenho de Leitura Dual-SQLite, Estatísticas Materializadas, Cache Escopado por Engine e FTS5

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-010` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-010`](./ADR-010.md) |
| **Título da Decisão** | ADR-010: Otimização de Desempenho de Leitura Dual-SQLite, Estatísticas Materializadas, Cache Escopado por Engine e FTS5 |
| **Data de Início (Planejamento)** | 2026-11-15 |
| **Data de Conclusão (Auditoria)** | 2026-11-15 |
| **Taxa de Conclusão de Tarefas** | **100%** (21/21 tarefas concluídas) |
| **Branch Git** | `develop` |
| **Commit SHA de Validação** | `379e30b` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-010.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-010 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **T1 — Tuning de Conexão SQLite (`PRAGMA`s) e Migração Materializada + FTS5 (`DEC-001`, `DEC-002`, `DEC-006`)** | ✅ Concluído | Aprovado no Gate |
| `T02` | Registrar `@event.listens_for(Engine, "connect")` em `src/backend/core/database.py` aplicando `journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-64000`, `mmap_size=268435456` e `busy_timeout=5000`. | ✅ Concluído | Aprovado no Gate |
| `T03` | Adicionar `episodes_count`, `max_season` e `max_episode` ao modelo `EZTVShow` em `src/backend/models/eztv_db.py`. | ✅ Concluído | Aprovado no Gate |
| `T04` | Atualizar `init_eztv_db()` em `src/backend/core/database.py` para adicionar as colunas `episodes_count`, `max_season`, `max_episode`, criar índices compostos B-Tree (`idx_episodes_show_season_ep`, `idx_shows_rating_id`), executar backfill idempotente a partir de `episodes_catalog` e criar/sincronizar a tabela virtual `shows_fts` (`FTS5`) com triggers `AFTER INSERT/UPDATE/DELETE`. | ✅ Concluído | Aprovado no Gate |
| `T05` | **T2 — Motor de Cache em Memória Escopado por `Engine` + Fingerprint (`DEC-003`)** | ✅ Concluído | Aprovado no Gate |
| `T06` | Criar `src/backend/core/cache.py` implementando `EngineScopedCache` (`catalog_cache`, `discovery_cache`) thread-safe com escopo `(id(engine), ...)` e invalidação explícita. | ✅ Concluído | Aprovado no Gate |
| `T07` | **T3 — Otimização de `CatalogRepository` (`DEC-002`, `DEC-003`, `DEC-004`, `DEC-006`)** | ✅ Concluído | Aprovado no Gate |
| `T08` | Eliminar a chamada a `_build_episode_stats_map` sobre todos os `all_ids` antes da paginação em `CatalogRepository.list_shows`; usar diretamente `show.episodes_count`, `show.max_season` e `show.max_episode` (com fallback apenas para itens com `episodes_count == 0`). | ✅ Concluído | Aprovado no Gate |
| `T09` | Integrar busca acelerada via `shows_fts MATCH` em `CatalogRepository.list_shows` quando `search` for informado, com fallback seguro para substring. | ✅ Concluído | Aprovado no Gate |
| `T10` | Refatorar `CatalogRepository.get_curated_sections` para pipeline single-pass em memória + cache escopado com fingerprint `(count_shows, max_updated_at, sum_episodes)`. | ✅ Concluído | Aprovado no Gate |
| `T11` | Otimizar `CatalogRepository.get_genres_with_counts` e `CatalogRepository.get_stats` utilizando as colunas materializadas e cache escopado com fingerprint. | ✅ Concluído | Aprovado no Gate |
| `T12` | Invalidar `catalog_cache` e `discovery_cache` nas rotas de mutação de `src/backend/api/catalog.py` (`/sync`, `/enrich-pending`). | ✅ Concluído | Aprovado no Gate |
| `T13` | **T4 — Remoção de `_ensure_seeded` do Caminho Quente e Otimização de `DiscoveryEngineRepository` (`DEC-003`, `DEC-005`)** | ✅ Concluído | Aprovado no Gate |
| `T14` | Proteger `ensure_federated_catalog_seeded` em `src/backend/services/federated_catalog.py` com guarda em memória `_SEEDED_ENGINES: set[int]` por `id(session.get_bind())` e chamá-la no `lifespan` de `src/backend/main.py`. | ✅ Concluído | Aprovado no Gate |
| `T15` | Refatorar `DiscoveryEngineRepository` em `src/backend/repositories/discovery_engine.py` para cachear o snapshot base de obras desacopladas (`MediaWork.model_validate`), créditos, disponibilidade, gêneros normalizados, blobs textuais e `build_eztv_lookup_index`, além de eliminar N+1 queries em `compute_similar_works`. | ✅ Concluído | Aprovado no Gate |
| `T16` | **T5 — Sincronização de Estatísticas Materializadas no Script CLI (`DEC-002`, `DEC-006`)** | ✅ Concluído | Aprovado no Gate |
| `T17` | Atualizar `scripts/eztv-metadata-catalog.py` para criar as colunas `episodes_count`, `max_season`, `max_episode` e recalculá-las automaticamente após gravação de episódios. | ✅ Concluído | Aprovado no Gate |
| `T18` | **T6 — Testes Automatizados de Performance, FTS5 e Isolamento de Cache** | ✅ Concluído | Aprovado no Gate |
| `T19` | Adicionar testes em `tests/unit/test_db_performance.py` validando `PRAGMA`s SQLite, estatísticas materializadas em `shows`, busca via `FTS5`, invalidação automática por fingerprint e guarda `_SEEDED_ENGINES`. | ✅ Concluído | Aprovado no Gate |
| `T20` | **T7 — Verificação de Qualidade e Reconciliação Documental (`AGENTS.md`, `ADR-INDEX.md`)** | ✅ Concluído | Aprovado no Gate |
| `T21` | Executar `ruff check src/ tests/`, `pytest -q` e benchmark comparativo final comprovando a redução de latência. | ✅ Concluído | Aprovado no Gate |

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

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-010` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-010.md`](./archive/ADR-010.md)
* **Blueprint:** [`docs/adr/archive/ADR-010-BP.md`](./archive/ADR-010-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-010-TODO.md`](./archive/ADR-010-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-010-PI.md`](./archive/ADR-010-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-010
DATA: 2026-11-15
HASH DE VALIDAÇÃO: 290DB5B208BC485C
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
