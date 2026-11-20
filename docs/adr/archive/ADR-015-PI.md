---
id: ADR-015-PI
title: "Plano de Implementação (PI) — ADR-015: Motor Unificado dos 3 Pilares de Hidratação e Cascata de 6 Degraus"
parent_adr: ADR-015
date: 2026-11-19
status: ACCEPTED
language: PT-BR
---

# ADR-015-PI: Plano de Implementação em 4 Ondas

## Onda 1 — Pilar 1B: Cursores Persistentes de Presença, Paginação Profunda & `Canonical Catalog Anchor Sweep` (`DEC-001`, `DEC-002`, `DEC-003`)
1. **`src/backend/providers/sources/yify_adapter.py`:**
   - Adicionar suporte a `start_page` (lido/atualizado no cursor `next_page` do `config_json` da instância), cálculo de `total_pages = ceil(movie_count / 50)` (`~1.572` páginas = `78.565` filmes), marcação automática de `bootstrap_completed = True` ao concluir e modo `compact_presence = True` com `Batch SELECT/UPSERT` (1 registro leve de presença por filme na Fase 1B, expandido no clique JIT da Fase 2).
2. **`src/backend/providers/sources/torrent_api_py_adapter.py`:**
   - Expandir `_fetch_native_direct_items` e `fetch_recent_candidates` com suporte a paginação real (`page=1..N`), varredura de todas as 6 categorias precompiladas de vídeo da APIBay (`201, 202, 205, 207, 208, 209` em `glodls`), paginação de `Movies` e `TV` em `therarbg.to` (`tgx`), páginas/anos em `bitsearch.to` e feed de `75` itens + busca em `nyaa.si`, além de extração bilíngue de títulos de anime entre parênteses.
3. **`src/backend/services/sources_registry.py`:**
   - Implementar `sweep_canonical_catalog_presence()` (varredura guiada pelas obras mais populares de `mainstream.db` por formato para `tgx`, `nyaasi`, `bitsearch`, `glodls` com cursor `catalog_sweep_offset`) e avanço automático do cursor `next_page` em `sync_source()`.

## Onda 2 — Pilar 3: Cascata Hierárquica de 6 Degraus (`IMDb` $\rightarrow$ `TMDB` $\rightarrow$ `TVMaze` $\rightarrow$ `EZTV` $\rightarrow$ `YIFY` $\rightarrow$ `Outras Fontes`) & `HydrationOrchestratorService` (`DEC-001`, `DEC-004`, `DEC-005`, `DEC-006`)
4. **`src/backend/services/cascading_enricher.py`:**
   - Implementar `CascadingMetadataEnricher`:
     - **Passo 0 (`cross_db_self_heal`):** reconciliação bidirecional instantânea entre `EZTVShow` (`data/sources.db`, curando as `75` séries órfãs) e `IMDbCatalogShow` (`data/mainstream.db`).
     - **Degrau 1 (`IMDb`):** extrator de `<script type="application/ld+json">` e `og:image` de `https://www.imdb.com/title/{imdb_id}/` + preservação do backbone.
     - **Degrau 2 (`TMDB`):** `/find/{imdb_id}` (`pt-BR` + `en-US` + `watch/providers`).
     - **Degrau 3 (`TVMaze`):** `/lookup/shows?imdb={imdb_id}`.
     - **Degrau 4 (`EZTV`):** fallback cruzado com `EZTVShow`.
     - **Degrau 5 (`YIFY / YTS`):** `movies-api.accel.li/api/v2/movie_details.json?imdb_id={imdb_id}`.
     - **Degrau 6 (`Outras Fontes Abertas`):** Wikidata Batch SPARQL (`P345` + resumos `pt.wikipedia.org` e `en.wikipedia.org`) + `Jikan v4` (`api.jikan.moe/v4/anime`).
5. **`src/backend/services/hydration_orchestrator.py` & `src/backend/api/explore.py` & `src/backend/main.py`:**
   - Implementar `SmartBootstrapDetector`, persistência em `sync_state` (`hydration_pipeline_v1`), worker cooperativo `asyncio.Task` integrado ao `lifespan`, endpoints `/api/explore/hydration/{status,start,pause,step,reset-cursor}` e CLI `scripts/hydrate_ecosystem.py` (`make hydrate`).

## Onda 3 — Frontend: Console Unificado de 1 Botão dos 3 Pilares de Hidratação (`DEC-006`)
6. **`src/frontend/src/types.ts` & `src/frontend/src/services/api.ts`:**
   - Adicionar contrato `HydrationPipelineStatus` e métodos `api.explore.hydration.{getStatus,start,pause,step,resetCursor}`.
7. **`src/frontend/src/components/StatusConfigView.tsx` & `src/frontend/src/components/SourcesView.tsx`:**
   - Integrar o painel **"Motor Unificado dos 3 Pilares de Hidratação (Com Checkpoint `--resume`)"** com botão mestre `▶️ Iniciar / Retomar Hidratação Completa` $\leftrightarrow$ `⏸️ Pausar (Checkpoint Seguro)`, seletor de escopo (`Tudo [1B + 3]`, `Apenas Fontes [1B]`, `Apenas Capas & Sinopses [3]`), badges de maturidade (`🟢 MODO DELTA` vs `🔵 BOOTSTRAP pág. X/Y`), barras de progresso dos 3 pilares e contadores de proveniência dos 6 degraus da cascata.

## Onda 4 — Testes Herméticos, Execução de Hidratação Real, Gate de Qualidade & Arquivamento (`DEC-001`..`DEC-006`)
8. **`tests/integration/test_three_pillar_hydration.py`:**
   - Testar `SmartBootstrapDetector` (Zero-State vs Warm-State), avanço de cursor `next_page` e `catalog_sweep_offset` na Fase 1B, `Cross-DB Self-Healing` (`EZTVShow` $\leftrightarrow$ `IMDbCatalogShow`), Cascata Hierárquica de 6 Degraus (`IMDb` $\rightarrow$ `TMDB` $\rightarrow$ `TVMaze` $\rightarrow$ `EZTV` $\rightarrow$ `YIFY` $\rightarrow$ `Wikidata/Jikan`) e endpoints `/api/explore/hydration/{status,step,start,pause,reset-cursor}`.
9. **Gate de Fechamento (`implementation` Workflow 8):**
   - Executar lote real de hidratação nos bancos locais (`data/sources.db` + `data/mainstream.db`), rodar `make lint`, `make test`, `make build-front`, reconciliar os 6 pilares documentais, marcar `16/16` tarefas em `ADR-015-TODO.md`, executar `spx adr archive ADR-015`, `spx docs build` e `git commit && git push`.
