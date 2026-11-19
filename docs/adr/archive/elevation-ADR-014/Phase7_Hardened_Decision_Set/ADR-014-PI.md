---
id: ADR-014-PI
title: "Plano de Implementação (PI) — ADR-014: Alinhamento sources-apis.md, Sincronia Bipartida e Sync Command Deck"
parent_adr: ADR-014
date: 2026-11-19
status: ACCEPTED
language: PT-BR
---

# ADR-014-PI: Plano de Implementação em 4 Ondas

## Onda 1 — Protocolos Oficiais `sources-apis.md` & Catálogo `Torrent-Api-py` (`DEC-001`, `DEC-002`, `DEC-003`)
1. **`src/backend/providers/sources/base.py`:**
   - Adicionar `OFFICIAL_YTS_TRACKERS` (10 trackers de `sources-apis.md`), `build_official_magnet(info_hash, title, trackers)` com `urllib.parse.quote_plus`, e `parse_release_title_and_year(raw_title)`.
2. **`src/backend/providers/sources/yify_adapter.py`:**
   - Atualizar base URL padrão para `https://movies-api.accel.li/api/v2/list_movies.json` (com mirrors `yts.gg`, `yts.mx`, `yts.lt`).
   - Suportar parâmetros nativos de `list_movies.json` (`limit`, `page`, `quality`, `minimum_rating`, `query_term`, `genre`, `sort_by`, `order_by`, `with_rt_ratings`) e implementar `fetch_movie_enrichment()` (`movie_details.json`, `movie_suggestions.json`, `movie_parental_guides.json`).
3. **`src/backend/providers/sources/eztv_adapter.py` & `src/backend/providers/eztv.py`:**
   - Garantir lookup numérico estrito sem `tt` (`?imdb_id=6048596`) e `limit=1..100`, adicionar ingestão RSS `https://myrss.org/eztv` e diagnóstico `https://eztvstatus.org/`.
4. **`src/backend/providers/sources/torrent_api_py_adapter.py`:**
   - Expandir `SITE_CATALOG` para os 12 provedores (`tgx`, `nyaasi`, `bitsearch`, `glodls`, `magnetdl`, `limetorrent`, `torlock`, `kickass`, `zooqle`, `yts`, `1337x`, `piratebay`), habilitar `supports_sync = True` via `/api/v1/recent` e enriquecer magnets via `build_official_magnet`.

## Onda 2 — Orquestrador Bipartido (Etapa 1 + Etapa 2) & Batch Join Soberano (`DEC-003`, `DEC-004`, `DEC-005`, `DEC-006`)
5. **`src/backend/services/sources_registry.py`:**
   - Atualizar `DEFAULT_SOURCE_INSTANCES` (`eztv`, `yify` em `movies-api.accel.li`, `tgx`, `nyaasi`, `bitsearch`, `glodls`) e migração idempotente em `ensure_sources_registered()`.
   - Implementar `_resolve_imdb_id_against_mainstream`, `prune_obsolete_releases`, `sync_library_titles` e modos `incremental | baseline | library | prune` em `sync_source()`.
   - Implementar roteamento inteligente por formato (`movie` vs `tv_show`), transação atômica `Replace-on-Success` e `get_yify_enrichment_for_imdb()` na Etapa 2 (`get_releases_for_imdb`).
   - Implementar **Batch Sovereign Join** (`sources.db` $\rightarrow$ `mainstream.db`) e deduplicação canônica por `imdb_id` (`media_sources`, `qualities`, `max_seeds`) em `list_catalog()` e `search_and_ingest_catalog()`.
6. **`src/backend/api/sources.py`:**
   - Expandir `POST /api/sources/sync` (`mode`, `quality`, `minimum_rating`, `sort_by`, `min_seeds_floor`, `prune_after`), adicionar `POST /api/sources/prune`, `POST /api/sources/live-ingest` (`Search-to-Catalog` `4D`) e `GET /api/sources/yify/enrichment/{imdb_id}`.

## Onda 3 — Frontend: Sync Command Deck, Onda Card a Card & Inteligência YTS (`DEC-005`, `DEC-006`)
7. **`src/frontend/src/types.ts` & `src/frontend/src/services/api.ts`:**
   - Adicionar tipos e métodos para receitas de sincronia (`SyncRecipeOptions`, `PruneSourcesResult`, `YifyMovieEnrichment`, `api.sources.prune`, `api.sources.liveIngest`, `api.sources.getYifyEnrichment`).
8. **`src/frontend/src/components/SourcesView.tsx`:**
   - Construir o **Sync Command Deck** (5 receitas de 1 clique + gaveta de Ajuste Fino), **Onda Card a Card** com progresso orbital e fast-skip do sidecar (`:8009`), **Cards Cockpit** com botão `⚡` individual e pílulas de qualidade/fontes agregadas, e gatilho **`⚡ Buscar & Ingerir ao Vivo`** na barra de busca.
9. **`src/frontend/src/components/TorrentModal.tsx`:**
   - Operar em modo **Stale-While-Revalidate (SWR)** na Etapa 2 (mantendo lista visível durante revalidação JIT) e exibir a faixa colapsável **"Inteligência YTS (`movies-api.accel.li`)"** com Guia Parental, Nota/Specs e 4 Sugestões Relacionadas clicáveis.

## Onda 4 — Testes Herméticos, Gate de Qualidade & Arquivamento (`DEC-001`..`DEC-006`)
10. **`tests/integration/test_source_plugins_contract.py` & `tests/integration/test_sources_and_preferences_api.py`:**
    - Testar `movies-api.accel.li/api/v2/` (`list_movies.json`, `movie_details.json`, `movie_suggestions.json`, `movie_parental_guides.json`), builder de 10 trackers com `quote_plus`, EZTV `?imdb_id` numérico + RSS `myrss.org/eztv`, catálogo de 12 sites do `Torrent-Api-py` (`/recent` + `/search`), Etapa 1 (`incremental`, `baseline`, `library`, `prune`), Etapa 2 (`Replace-on-Success` + Format Routing) e Batch Join Soberano com `mainstream.db`.
11. **Gate de Fechamento (`implementation` Workflow 8):**
    - Executar `make lint`, `make test`, `npx tsc --noEmit && make build-front`, reconciliar os 6 pilares documentais, marcar `16/16` tarefas em `ADR-014-TODO.md`, executar `spx adr archive ADR-014` e `spx docs build`.
