---
id: ADR-014-ER
type: er
title: "Evidence Record - ADR-014: Alinhamento Canônico com sources-apis.md (YTS movies-api.accel.li & EZTV), Curadoria Torrent-Api-py (12 Sites), Sincronia Bipartida em 2 Etapas e Sync Command Deck UI/UX"
created: 2026-11-19
updated: 2026-11-19
adr_ref: ADR-014
implementation_status: CONSOLIDADA
tasks_completed: 16/16
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-014: Alinhamento Canônico com sources-apis.md (YTS movies-api.accel.li & EZTV), Curadoria Torrent-Api-py (12 Sites), Sincronia Bipartida em 2 Etapas e Sync Command Deck UI/UX

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-014` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-014`](./ADR-014.md) |
| **Título da Decisão** | Alinhamento Canônico com sources-apis.md (YTS movies-api.accel.li & EZTV), Curadoria Torrent-Api-py (12 Sites), Sincronia Bipartida em 2 Etapas e Sync Command Deck UI/UX |
| **Data de Início (Planejamento)** | 2026-11-19 |
| **Data de Conclusão (Auditoria)** | 2026-11-19 |
| **Taxa de Conclusão de Tarefas** | **100%** (16/16 tarefas concluídas) |
| **Branch Git** | `UI-UX` |
| **Commit SHA de Validação** | `f6146fa` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-014.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-014 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **TODO-14.01 (`DEC-001`):** Implementar `OFFICIAL_YTS_TRACKERS` (10 trackers oficiais de `sources-apis.md`), `build_official_magnet(info_hash, title, trackers)` com `urllib.parse.quote_plus(dn)` e `parse_release_title_and_year(raw_title)` em `src/backend/providers/sources/base.py`. | ✅ Concluído | Aprovado no Gate |
| `T02` | **TODO-14.02 (`DEC-001`):** Atualizar `YIFYSourceAdapter` (`src/backend/providers/sources/yify_adapter.py`) para `https://movies-api.accel.li/api/v2/list_movies.json` (com mirrors `yts.gg`, `yts.mx`, `yts.lt`), suportando parâmetros nativos (`quality`, `minimum_rating`, `genre`, `sort_by`, `order_by`, `with_rt_ratings`) e `build_official_magnet`. | ✅ Concluído | Aprovado no Gate |
| `T03` | **TODO-14.03 (`DEC-001`, `DEC-005`):** Implementar `fetch_movie_enrichment` em `YIFYSourceAdapter` consumindo `movie_details.json` (`with_images=true&with_cast=true`), `movie_suggestions.json` e `movie_parental_guides.json` em paralelo com timeout seguro. | ✅ Concluído | Aprovado no Gate |
| `T04` | **TODO-14.04 (`DEC-002`):** Alinhar `EZTVSourceAdapter` (`src/backend/providers/sources/eztv_adapter.py`) e `EZTVProvider` (`src/backend/providers/eztv.py`) com `https://eztvx.to/api/get-torrents?limit=100&page=1` e lookup exato por IMDb ID numérico sem `tt` (`?imdb_id=6048596`). | ✅ Concluído | Aprovado no Gate |
| `T05` | **TODO-14.05 (`DEC-002`):** Adicionar ingestão incremental via RSS oficial `https://myrss.org/eztv` (`xml.etree.ElementTree`) e metadados de diagnóstico `status_url="https://eztvstatus.org/"` em `EZTVSourceAdapter`. | ✅ Concluído | Aprovado no Gate |
| `T06` | **TODO-14.06 (`DEC-003`):** Expandir `TorrentApiPySourceAdapter` (`src/backend/providers/sources/torrent_api_py_adapter.py`) para o catálogo completo de 12 provedores (`tgx`, `nyaasi`, `bitsearch`, `glodls`, `magnetdl`, `limetorrent`, `torlock`, `kickass`, `zooqle`, `yts`, `1337x`, `piratebay`) com `supports_sync = True` via `/api/v1/recent` e `/api/v1/search`. | ✅ Concluído | Aprovado no Gate |
| `T07` | **TODO-14.07 (`DEC-001`, `DEC-003`):** Atualizar `DEFAULT_SOURCE_INSTANCES` e a migração idempotente em `ensure_sources_registered()` (`src/backend/services/sources_registry.py`) para migrar `yify` para `movies-api.accel.li` e semear o quarteto resiliente `tgx`, `nyaasi`, `bitsearch`, `glodls`. | ✅ Concluído | Aprovado no Gate |
| `T08` | **TODO-14.08 (`DEC-004`):** Implementar `_resolve_imdb_id_against_mainstream` em `SourcesRegistryService` para casar títulos limpos da Etapa 1 (`/recent` e RSS) com `IMDbCatalogShow` em `data/mainstream.db` (`confidence >= 0.85`). | ✅ Concluído | Aprovado no Gate |
| `T09` | **TODO-14.09 (`DEC-004`):** Implementar `prune_obsolete_releases` e os modos de sincronia `incremental`, `baseline`, `library` (sincronia direcionada pela Biblioteca Pessoal) e `prune` em `SourcesRegistryService.sync_source()`, com propagação imediata de presença para `mainstream.db`. | ✅ Concluído | Aprovado no Gate |
| `T10` | **TODO-14.10 (`DEC-006`):** Implementar **Batch Sovereign Join** (`sources.db` $\rightarrow$ `mainstream.db`) e deduplicação canônica por `imdb_id` no modo `source="all"` em `SourcesRegistryService.list_catalog()`, enriquecendo cards com pôster, nota IMDb, sinopse PT-BR, gêneros, streamings, `media_sources` e `qualities`. | ✅ Concluído | Aprovado no Gate |
| `T11` | **TODO-14.11 (`DEC-005`):** Implementar Roteamento Inteligente por Formato (`movie` vs `tv_show`) e transação atômica `Replace-on-Success` na Etapa 2 (`SourcesRegistryService.get_releases_for_imdb`), além de `live_ingest_query` para a busca viva da aba Fontes de Dados. | ✅ Concluído | Aprovado no Gate |
| `T12` | **TODO-14.12 (`DEC-004`, `DEC-005`, `DEC-006`):** Expandir `src/backend/api/sources.py` com parâmetros de receita em `POST /api/sources/sync`, além das novas rotas `POST /api/sources/prune`, `POST /api/sources/live-ingest` e `GET /api/sources/yify/enrichment/{imdb_id}`. | ✅ Concluído | Aprovado no Gate |
| `T13` | **TODO-14.13 (`DEC-005`, `DEC-006`):** Atualizar contratos TypeScript (`src/frontend/src/types.ts`) e cliente HTTP (`src/frontend/src/services/api.ts`) com suporte a receitas de sincronia, poda de obsoletos, live ingest, agregação multi-fonte no catálogo e enriquecimento YTS v2. | ✅ Concluído | Aprovado no Gate |
| `T14` | **TODO-14.14 (`DEC-005`):** Atualizar `src/frontend/src/components/TorrentModal.tsx` com revalidação JIT **Stale-While-Revalidate (SWR)** sem esconder o snapshot da Etapa 1 e renderizar a faixa colapsável **"Inteligência YTS (`movies-api.accel.li`)"** (Guia Parental, Specs/RT e 4 Sugestões Clicáveis). | ✅ Concluído | Aprovado no Gate |
| `T15` | **TODO-14.15 (`DEC-006`):** Construir o **Sync Command Deck** em `src/frontend/src/components/SourcesView.tsx` com 5 receitas de 1 clique (*⚡ Incremental Delta*, *🏗️ Baseline Top Seeds*, *💎 4K / 1080p Nota 7+*, *📚 Minha Biblioteca*, *🧹 Podar Obsoletos*), gaveta de Ajuste Fino, **Onda Card a Card**, **Cards Cockpit** e gatilho **`⚡ Buscar & Ingerir ao Vivo`**. | ✅ Concluído | Aprovado no Gate |
| `T16` | **TODO-14.16 (`DEC-001`..`DEC-006`):** Atualizar e expandir `tests/integration/test_source_plugins_contract.py` e `tests/integration/test_sources_and_preferences_api.py`, validar `make lint`, `make test`, `make build-front`, reconciliar os 6 pilares documentais e arquivar via `spx adr archive ADR-014`. | ✅ Concluído | Aprovado no Gate |

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

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-014` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-014.md`](./archive/ADR-014.md)
* **Blueprint:** [`docs/adr/archive/ADR-014-BP.md`](./archive/ADR-014-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-014-TODO.md`](./archive/ADR-014-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-014-PI.md`](./archive/ADR-014-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-014
DATA: 2026-11-19
HASH DE VALIDAÇÃO: 3187D447792CDD33
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
