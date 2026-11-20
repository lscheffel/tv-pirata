---
id: ADR-015-TODO
title: "Checklist de Execução (TODO) — ADR-015"
parent_adr: ADR-015
date: 2026-11-19
status: ACCEPTED
language: PT-BR
---

# ADR-015-TODO: Checklist Determinístico de Execução (16 Tarefas)

## Onda 1 — Pilar 1B: Cursores Persistentes de Presença, Paginação Profunda & `Canonical Catalog Anchor Sweep`
- [x] **TODO-15.01 (`DEC-001`):** Implementar `SmartBootstrapDetector` para classificar automaticamente cada pilar e fonte entre `BOOTSTRAP` (instalação limpa ou cursor incompleto) e `DELTA` (catálogo maduro: `IMDb >= 250k` e `EZTV >= 500`), persistindo o estado em `sync_state` (`hydration_pipeline_v1`).
- [x] **TODO-15.02 (`DEC-002`, `DEC-003`):** Atualizar `YIFYSourceAdapter` (`src/backend/providers/sources/yify_adapter.py`) com cursor persistente `next_page` (`1..1572`), cálculo de `total_pages` a partir de `movie_count` (`78.565` filmes), transição automática `bootstrap_completed = True` e modo `compact_presence = True` com `Batch SELECT/UPSERT`.
- [x] **TODO-15.03 (`DEC-002`):** Expandir `TorrentApiPySourceAdapter` (`src/backend/providers/sources/torrent_api_py_adapter.py`) e `src/backend/sidecar/torrent_api_sidecar.py` com paginação multi-página real (`page=1..N`), coleta das 6 categorias de vídeo da APIBay (`201..209` em `glodls`), paginação `Movies`/`TV` em `therarbg.to` (`tgx`), páginas/anos em `bitsearch.to`, `75` itens por página em `nyaa.si` e parser de títulos alternativos entre parênteses.
- [x] **TODO-15.04 (`DEC-002`, `DEC-003`):** Implementar `sweep_canonical_catalog_presence` em `SourcesRegistryService` (`src/backend/services/sources_registry.py`) com cursor `catalog_sweep_offset` para descobrir proativamente em `tgx`, `nyaasi`, `bitsearch` e `glodls` as obras mais populares de `mainstream.db`.

## Onda 2 — Pilar 3: Cascata Hierárquica de 6 Degraus & `HydrationOrchestratorService`
- [x] **TODO-15.05 (`DEC-004`):** Criar `CascadingMetadataEnricher` em `src/backend/services/cascading_enricher.py` implementando a cascata hierárquica estrita de 6 degraus: **(1) `IMDb`** (JSON-LD `<script type="application/ld+json">` & `og:image` de `imdb.com/title/tt...`), **(2) `TMDB`** (`pt-BR` + `en-US` + `watch/providers`), **(3) `TVMaze`** (`/lookup/shows?imdb=...`), **(4) `EZTV`** (`Cross-DB Self-Healing`), **(5) `YIFY / YTS`** (`movie_details.json?imdb_id=tt...`) e **(6) `Outras Fontes Abertas`** (`Wikidata Batch SPARQL P345 + Wikipédia PT/EN REST Summary` + `Jikan v4`).
- [x] **TODO-15.06 (`DEC-004`, `DEC-005`):** Implementar `cross_db_self_heal` bidirecional (`EZTVShow` em `sources.db` $\leftrightarrow$ `IMDbCatalogShow` em `mainstream.db`) curando as séries órfãs da EZTV (`guide_synced = -1`) e sincronizando capas, sinopses PT-BR/EN-US, notas e streamings.
- [x] **TODO-15.07 (`DEC-005`):** Implementar a **Fila Bipartida Prioritária** (`Media-First`: 1º `Minha Biblioteca` e obras com mídia em `sources.db`; 2º Sub-Fila `Sem Capa` [`poster_url IS NULL`]; 3º Sub-Fila `Sem Sinopse` [`synopsis_ptbr IS NULL OR synopsis IS NULL`]) e a máquina de 4 estados `details_fetched` (`0, 1, 2, -1`) com telemetria de proveniência por degrau.
- [x] **TODO-15.08 (`DEC-001`, `DEC-006`):** Criar `HydrationOrchestratorService` em `src/backend/services/hydration_orchestrator.py` com worker assíncrono cooperativo (`start`, `pause`, `run_single_step`, `reset_cursor`, `get_status`) e integração no `lifespan` de `src/backend/main.py` com teardown seguro (`<= 3.0s`).
- [x] **TODO-15.09 (`DEC-006`):** Expor as rotas REST `GET /api/explore/hydration/status`, `POST /api/explore/hydration/start`, `POST /api/explore/hydration/pause`, `POST /api/explore/hydration/step` e `POST /api/explore/hydration/reset-cursor` em `src/backend/api/explore.py`.
- [x] **TODO-15.10 (`DEC-006`):** Criar o utilitário CLI `scripts/hydrate_ecosystem.py` (com suporte a `--resume`, `--scope`, `--max-steps`) e o alvo `make hydrate` no `Makefile`.

## Onda 3 — Frontend: Console Unificado de 1 Botão dos 3 Pilares
- [x] **TODO-15.11 (`DEC-006`):** Adicionar os contratos TypeScript (`HydrationPipelineStatus`, `PillarSourceCursorStatus`, `WaterfallProvenanceCounts`) em `src/frontend/src/types.ts` e os métodos `api.explore.hydration.*` em `src/frontend/src/services/api.ts`.
- [x] **TODO-15.12 (`DEC-006`):** Construir o painel mestre **"Motor Unificado dos 3 Pilares de Hidratação (Com Checkpoint `--resume`)"** em `src/frontend/src/components/StatusConfigView.tsx` com botão de 1 clique `▶️ Iniciar / Retomar Hidratação` $\leftrightarrow$ `⏸️ Pausar`, seletor de escopo, barras de progresso dos 3 pilares, cursores `BOOTSTRAP` vs `DELTA` e badges de proveniência dos 6 degraus.
- [x] **TODO-15.13 (`DEC-006`):** Integrar a barra compacta de progresso e botão rápido de retomada/avanço de cursor no **Sync Command Deck** de `src/frontend/src/components/SourcesView.tsx`.

## Onda 4 — Verificação Hermética, Hidratação Real & Arquivamento
- [x] **TODO-15.14 (`DEC-001`..`DEC-006`):** Criar a suíte de testes herméticos `tests/integration/test_three_pillar_hydration.py` validando `SmartBootstrapDetector`, avanço de cursores na Fase 1B, `Cross-DB Self-Healing`, Cascata Hierárquica de 6 Degraus (`IMDb` $\rightarrow$ `TMDB` $\rightarrow$ `TVMaze` $\rightarrow$ `EZTV` $\rightarrow$ `YIFY` $\rightarrow$ `Wikidata/Jikan`) e rotas `/api/explore/hydration/*`.
- [x] **TODO-15.15 (`DEC-002`, `DEC-004`, `DEC-005`):** Executar ciclo real de hidratação nos bancos `data/sources.db` e `data/mainstream.db` para escalar a presença de títulos em `YTS`, `TGx`, `Nyaa`, `BitSearch` e `GloDLS` e curar as séries órfãs da EZTV e obras com mídia sem capa/sinopse.
- [x] **TODO-15.16 (`DEC-001`..`DEC-006`):** Validar `make lint`, `make test`, `make build-front`, reconciliar os 6 pilares documentais (`README.md`, `CHANGELOG.md`, `USAGE.md`, `RELEASE-NOTES.md`, `STATE.md`, `AGENTS.md`), arquivar via `spx adr archive ADR-015`, rodar `spx docs build` e executar `git commit && git push`.
