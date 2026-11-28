---
adr_ref: ADR-021
title: "Plano de Implementação (PI) — ADR-021 Hardened"
status: CERTIFIED (ELEVATED)
updated: "2026-11-28"
decisions: [DEC-001, DEC-002, DEC-003, DEC-004, DEC-005, DEC-006, DEC-007]
---

# ADR-021 Plano de Implementação (Fases e Gates)

## Fase A — Confiabilidade de Ingestão: IMDb 2-Estágios & EZTV Unificado (`DEC-001`, `DEC-002`)
- **Escopo Backend:**
  1. `scripts/imdb-metadata-catalog.py`: expor `check_remote_revision()` (HTTP `HEAD` comparando ETag/Last-Modified sem silenciar erro de rede), limpeza de `.tmp` órfãos, retorno explícito `(delta_inserted, delta_updated, local_lm, remote_lm, cache_status)` em `sync_level1_datasets`.
  2. `src/backend/services/imdb_sync_service.py`: implementar execução em 2 estágios (Download HTTP paralelo sem lock SQLite → Pausa cooperativa do orquestrador → Commit SQLite + FTS5 + `DiscoveryEngineRepository.refresh_global_facets_cache` → Retomada); isolar `PYTEST_CURRENT_TEST` do `mainstream_engine` real; estender `IMDbSyncJobStatus`.
  3. `src/backend/services/catalog_indexer.py` + `sources_registry.py` + `hydration_orchestrator.py`: implementar paginação EZTV por watermark (`max_pages=25`, parada após 2 págs consecutivas sem novos `eztv_id`, backoff `429/5xx`), dual-write atômico (`CatalogRelease`/`CatalogShow` + `ExternalRelease(source_key="eztv")` + criação de `EZTVShow`), propagação `has_eztv` em `mainstream.db`, remoção do bypass `if rec.source_key == "eztv": continue` em `_recompute_source_counters`, integração de `HEAD` IMDb no `novidades` (>24h) e suporte opt-in a `eztv` no modo `varredura` para séries da Biblioteca.
- **Gate de Verificação A:**
  - Testes unitários/integração hermeticamente isolados (`respx` + SQLite in-memory) provando: (a) zero escrita no DB real durante `pytest`, (b) falha de `HEAD` não carimba `last_sync_at`, (c) EZTV watermark para após 2 págs conhecidas e atualiza `ExternalSourceRecord.total_releases > 0`, (d) `refresh_global_facets_cache` atualizado.

## Fase B — Motor de Vitrine Orgânica & Preferências v2 (`DEC-003`, `DEC-004`, `DEC-007`)
- **Escopo Backend:**
  1. `src/backend/repositories/preferences.py` + `src/backend/api/explore.py`: evoluir `UserExplorePreferences` para `schema_version: Literal[1, 2] = 2` com `default_smart_lists_v2()`, `discovery_variance_pct`, `hero_auto_rotate`, `hero_interval_sec`, `impression_ttl_hours`, `hidden_builtin_shortcuts` e `custom_shortcuts`.
  2. `src/backend/services/discovery_feed.py`: implementar `DiscoveryFeedService` com:
     - Normalização bilíngue de perfil da Biblioteca (`showrecord` → `canonical_taxonomy.py` + pesos por status);
     - Ring-buffer de impressões (`discovery_impressions_v1` em `sync_state`, máx. 200, TTL configurável);
     - Scoring com variância `0–100%` determinística por `session_seed`;
     - Alocação por escassez crescente garantindo **100% de unicidade entre até 1.000 itens** (10 listas × 100) + Hero (12–15) + Roleta estratificada (3 contrastes por escopo);
     - `catalog_filter` estruturado em cada lista para ponte *"Abrir no Catálogo"*.
  3. `src/backend/api/explore.py`: adicionar `GET /api/explore/feed` (*read-only*) e `POST /api/explore/impressions`.
- **Gate de Verificação B:**
  - Testes unitários/integração validando: (a) migração automática de preferências `v1 → v2`, (b) `0` colisões de `imdb_id` entre as 10 listas + Hero + Roleta, (c) `variance=0` determinístico vs `variance=80` gerando rotação sem itens sem poster, (d) `POST /impressions` reduzindo score no próximo `GET /feed`, (e) latência $P_{95} < 400\text{ ms}$ sobre `data/mainstream.db`.

## Fase C — Separação Frontend (`DiscoverView` vs `CatalogView`), Carrossel Circular & Hero Vivo (`DEC-005`, `DEC-006`)
- **Escopo Frontend:**
  1. `src/frontend/src/types/index.ts` + `src/frontend/src/services/api.ts` + `PreferencesContext.tsx`: tipagem v2 completa (`DiscoveryFeedResponse`, `SmartListConfig`, `CustomShortcutConfig`, `FilterSnapshot`) e endpoints `/explore/feed`, `/explore/impressions`.
  2. `src/frontend/src/components/Navbar.tsx` + `src/frontend/src/App.tsx`: 5 abas de 1 palavra (**Descobrir · Catálogo · Fontes · Biblioteca · Coleções**), elevação de `catalogFilters` (`FilterSnapshot`) em `App.tsx`, busca global navegando para **Catálogo**.
  3. `src/frontend/src/components/HeroBanner.tsx`: carrossel Hero auto-rotativo (pausável no hover/foco), indicadores de progresso, setas e selo explicativo.
  4. `src/frontend/src/components/ShowCarousel.tsx`: janela circular virtualizada (~24 cards no DOM), loop contínuo `1..100`, indicador de posição e botão **"Abrir no Catálogo"**.
  5. `src/frontend/src/components/DiscoverView.tsx` + `src/frontend/src/components/CatalogView.tsx`: extração limpa de `ExplorerView.tsx`, barra de Atalhos mista (removendo *Diretor*), Roleta contextual com seletor de escopo, botão **"Fixar como Atalho"** no Catálogo.
  6. `src/frontend/src/components/HydrationConsoleCard.tsx`: exibir delta real e data da revisão remota no card IMDb, contadores reais de EZTV e toggle EZTV na *Varredura*.
- **Gate de Verificação C:**
  - `npm run build` (`tsc && vite build`) com zero erros de tipo/bundle.

## Fase D — 5ª Categoria de Configurações ("Vitrine & Listas Inteligentes") & Fechamento (`DEC-007`)
- **Escopo Frontend:**
  1. `src/frontend/src/components/settings/SettingsSidebar.tsx` + `StatusConfigView.tsx`: registrar 5ª categoria `"discover_feed"` (**Vitrine & Listas Inteligentes**).
  2. `src/frontend/src/components/settings/DiscoveryFeedPanel.tsx`: controles de variância (`0–100%`), Hero, TTL de impressões, gestão das 10+ Listas Inteligentes (ativar, reordenar, limite 20–100, ordenação, só com mídia, variância por lista) e gestão de Atalhos salvos.
- **Gate Final de Fechamento:**
  - `make lint && make test && make build-front` 100% verdes (zero falhas/erros), validação empírica de 1 ciclo real de IMDb/EZTV, reconciliação documental (`CHANGELOG.md`, `STATE.md`, `USAGE.md`, `RELEASE-NOTES.md`, `AGENTS.md`).
