---
id: ADR-015-ER
type: er
title: "Evidence Record - ADR-015: Motor Unificado dos 3 Pilares de Hidratação com Checkpoints (--resume), Gatilho Inteligente de Maturidade (Bootstrap <-> Delta) e Cascata Hierárquica de 6 Degraus (IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes)"
created: 2026-11-19
updated: 2026-11-19
adr_ref: ADR-015
implementation_status: CONSOLIDADA
tasks_completed: 16/16
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-015: Motor Unificado dos 3 Pilares de Hidratação com Checkpoints (--resume), Gatilho Inteligente de Maturidade (Bootstrap <-> Delta) e Cascata Hierárquica de 6 Degraus (IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes)

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-015` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-015`](./ADR-015.md) |
| **Título da Decisão** | Motor Unificado dos 3 Pilares de Hidratação com Checkpoints (--resume), Gatilho Inteligente de Maturidade (Bootstrap <-> Delta) e Cascata Hierárquica de 6 Degraus (IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes) |
| **Data de Início (Planejamento)** | 2026-11-19 |
| **Data de Conclusão (Auditoria)** | 2026-11-19 |
| **Taxa de Conclusão de Tarefas** | **100%** (16/16 tarefas concluídas) |
| **Branch Git** | `UI-UX` |
| **Commit SHA de Validação** | `acfd711` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-015.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-015 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **TODO-15.01 (`DEC-001`):** Implementar `SmartBootstrapDetector` para classificar automaticamente cada pilar e fonte entre `BOOTSTRAP` (instalação limpa ou cursor incompleto) e `DELTA` (catálogo maduro: `IMDb >= 250k` e `EZTV >= 500`), persistindo o estado em `sync_state` (`hydration_pipeline_v1`). | ✅ Concluído | Aprovado no Gate |
| `T02` | **TODO-15.02 (`DEC-002`, `DEC-003`):** Atualizar `YIFYSourceAdapter` (`src/backend/providers/sources/yify_adapter.py`) com cursor persistente `next_page` (`1..1572`), cálculo de `total_pages` a partir de `movie_count` (`78.565` filmes), transição automática `bootstrap_completed = True` e modo `compact_presence = True` com `Batch SELECT/UPSERT`. | ✅ Concluído | Aprovado no Gate |
| `T03` | **TODO-15.03 (`DEC-002`):** Expandir `TorrentApiPySourceAdapter` (`src/backend/providers/sources/torrent_api_py_adapter.py`) e `src/backend/sidecar/torrent_api_sidecar.py` com paginação multi-página real (`page=1..N`), coleta das 6 categorias de vídeo da APIBay (`201..209` em `glodls`), paginação `Movies`/`TV` em `therarbg.to` (`tgx`), páginas/anos em `bitsearch.to`, `75` itens por página em `nyaa.si` e parser de títulos alternativos entre parênteses. | ✅ Concluído | Aprovado no Gate |
| `T04` | **TODO-15.04 (`DEC-002`, `DEC-003`):** Implementar `sweep_canonical_catalog_presence` em `SourcesRegistryService` (`src/backend/services/sources_registry.py`) com cursor `catalog_sweep_offset` para descobrir proativamente em `tgx`, `nyaasi`, `bitsearch` e `glodls` as obras mais populares de `mainstream.db`. | ✅ Concluído | Aprovado no Gate |
| `T05` | **TODO-15.05 (`DEC-004`):** Criar `CascadingMetadataEnricher` em `src/backend/services/cascading_enricher.py` implementando a cascata hierárquica estrita de 6 degraus: **(1) `IMDb`** (JSON-LD `<script type="application/ld+json">` & `og:image` de `imdb.com/title/tt...`), **(2) `TMDB`** (`pt-BR` + `en-US` + `watch/providers`), **(3) `TVMaze`** (`/lookup/shows?imdb=...`), **(4) `EZTV`** (`Cross-DB Self-Healing`), **(5) `YIFY / YTS`** (`movie_details.json?imdb_id=tt...`) e **(6) `Outras Fontes Abertas`** (`Wikidata Batch SPARQL P345 + Wikipédia PT/EN REST Summary` + `Jikan v4`). | ✅ Concluído | Aprovado no Gate |
| `T06` | **TODO-15.06 (`DEC-004`, `DEC-005`):** Implementar `cross_db_self_heal` bidirecional (`EZTVShow` em `sources.db` $\leftrightarrow$ `IMDbCatalogShow` em `mainstream.db`) curando as séries órfãs da EZTV (`guide_synced = -1`) e sincronizando capas, sinopses PT-BR/EN-US, notas e streamings. | ✅ Concluído | Aprovado no Gate |
| `T07` | **TODO-15.07 (`DEC-005`):** Implementar a **Fila Bipartida Prioritária** (`Media-First`: 1º `Minha Biblioteca` e obras com mídia em `sources.db`; 2º Sub-Fila `Sem Capa` [`poster_url IS NULL`]; 3º Sub-Fila `Sem Sinopse` [`synopsis_ptbr IS NULL OR synopsis IS NULL`]) e a máquina de 4 estados `details_fetched` (`0, 1, 2, -1`) com telemetria de proveniência por degrau. | ✅ Concluído | Aprovado no Gate |
| `T08` | **TODO-15.08 (`DEC-001`, `DEC-006`):** Criar `HydrationOrchestratorService` em `src/backend/services/hydration_orchestrator.py` com worker assíncrono cooperativo (`start`, `pause`, `run_single_step`, `reset_cursor`, `get_status`) e integração no `lifespan` de `src/backend/main.py` com teardown seguro (`<= 3.0s`). | ✅ Concluído | Aprovado no Gate |
| `T09` | **TODO-15.09 (`DEC-006`):** Expor as rotas REST `GET /api/explore/hydration/status`, `POST /api/explore/hydration/start`, `POST /api/explore/hydration/pause`, `POST /api/explore/hydration/step` e `POST /api/explore/hydration/reset-cursor` em `src/backend/api/explore.py`. | ✅ Concluído | Aprovado no Gate |
| `T10` | **TODO-15.10 (`DEC-006`):** Criar o utilitário CLI `scripts/hydrate_ecosystem.py` (com suporte a `--resume`, `--scope`, `--max-steps`) e o alvo `make hydrate` no `Makefile`. | ✅ Concluído | Aprovado no Gate |
| `T11` | **TODO-15.11 (`DEC-006`):** Adicionar os contratos TypeScript (`HydrationPipelineStatus`, `PillarSourceCursorStatus`, `WaterfallProvenanceCounts`) em `src/frontend/src/types.ts` e os métodos `api.explore.hydration.*` em `src/frontend/src/services/api.ts`. | ✅ Concluído | Aprovado no Gate |
| `T12` | **TODO-15.12 (`DEC-006`):** Construir o painel mestre **"Motor Unificado dos 3 Pilares de Hidratação (Com Checkpoint `--resume`)"** em `src/frontend/src/components/StatusConfigView.tsx` com botão de 1 clique `▶️ Iniciar / Retomar Hidratação` $\leftrightarrow$ `⏸️ Pausar`, seletor de escopo, barras de progresso dos 3 pilares, cursores `BOOTSTRAP` vs `DELTA` e badges de proveniência dos 6 degraus. | ✅ Concluído | Aprovado no Gate |
| `T13` | **TODO-15.13 (`DEC-006`):** Integrar a barra compacta de progresso e botão rápido de retomada/avanço de cursor no **Sync Command Deck** de `src/frontend/src/components/SourcesView.tsx`. | ✅ Concluído | Aprovado no Gate |
| `T14` | **TODO-15.14 (`DEC-001`..`DEC-006`):** Criar a suíte de testes herméticos `tests/integration/test_three_pillar_hydration.py` validando `SmartBootstrapDetector`, avanço de cursores na Fase 1B, `Cross-DB Self-Healing`, Cascata Hierárquica de 6 Degraus (`IMDb` $\rightarrow$ `TMDB` $\rightarrow$ `TVMaze` $\rightarrow$ `EZTV` $\rightarrow$ `YIFY` $\rightarrow$ `Wikidata/Jikan`) e rotas `/api/explore/hydration/*`. | ✅ Concluído | Aprovado no Gate |
| `T15` | **TODO-15.15 (`DEC-002`, `DEC-004`, `DEC-005`):** Executar ciclo real de hidratação nos bancos `data/sources.db` e `data/mainstream.db` para escalar a presença de títulos em `YTS`, `TGx`, `Nyaa`, `BitSearch` e `GloDLS` e curar as séries órfãs da EZTV e obras com mídia sem capa/sinopse. | ✅ Concluído | Aprovado no Gate |
| `T16` | **TODO-15.16 (`DEC-001`..`DEC-006`):** Validar `make lint`, `make test`, `make build-front`, reconciliar os 6 pilares documentais (`README.md`, `CHANGELOG.md`, `USAGE.md`, `RELEASE-NOTES.md`, `STATE.md`, `AGENTS.md`), arquivar via `spx adr archive ADR-015`, rodar `spx docs build` e executar `git commit && git push`. | ✅ Concluído | Aprovado no Gate |

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

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-015` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-015.md`](./archive/ADR-015.md)
* **Blueprint:** [`docs/adr/archive/ADR-015-BP.md`](./archive/ADR-015-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-015-TODO.md`](./archive/ADR-015-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-015-PI.md`](./archive/ADR-015-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-015
DATA: 2026-11-19
HASH DE VALIDAÇÃO: 5217E3F3D84E749D
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
