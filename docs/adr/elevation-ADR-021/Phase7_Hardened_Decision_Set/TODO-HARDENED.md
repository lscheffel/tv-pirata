---
adr_ref: ADR-021
title: "Checklist Executável (TODO) — ADR-021 Hardened"
status: PENDENTE
updated: "2026-11-28"
decisions: [DEC-001, DEC-002, DEC-003, DEC-004, DEC-005, DEC-006, DEC-007]
---

# ADR-021 TODO List (1:1 com Blueprint & PI)

## Bloco 1 — Motor IMDb Canônico 2-Estágios (`DEC-001` / `AMP-01`)
- [ ] **T1.1** Adicionar `check_remote_revisions()` e limpeza de `.tmp` órfãos em `scripts/imdb-metadata-catalog.py`, retornando delta explícito (`delta_inserted`, `delta_updated`, `local_lm`, `remote_lm`, `cache_status`) sem silenciar falha de `HEAD`.
- [ ] **T1.2** Refatorar `src/backend/services/imdb_sync_service.py` para 2 estágios (download HTTP paralelo sem lock SQLite → pausa cooperativa + commit + FTS5 + `refresh_global_facets_cache` + retomada), isolando `PYTEST_CURRENT_TEST` do `mainstream_engine` global.
- [ ] **T1.3** Integrar checagem `HEAD` do IMDb no modo `novidades` de `src/backend/services/hydration_orchestrator.py` (disparando auto-sync de `ratings`+`basics`+`akas` se revisão remota > 24h).

## Bloco 2 — Motor EZTV Unificado & Varredura de Biblioteca (`DEC-002` / `AMP-02`)
- [ ] **T2.1** Implementar paginação por watermark (`max_pages=25`, parada após 2 págs consecutivas conhecidas, delay `0.35s` + backoff `429/5xx`) e dual-write atômico (`CatalogRelease`/`CatalogShow` + `ExternalRelease(source_key="eztv")` + criação de `EZTVShow` + propagação `has_eztv`) em `src/backend/services/catalog_indexer.py`.
- [ ] **T2.2** Remover bypass `if rec.source_key == "eztv": continue` em `src/backend/services/sources_registry.py` (`_recompute_source_counters`) e atualizar `state.sources["eztv"]` (`titles_indexed`, `releases_indexed`, `last_run_at`) em `hydration_orchestrator.py`.
- [ ] **T2.3** Habilitar `eztv` como alvo opcional no modo `varredura` de `hydration_orchestrator.py` para retro-preencher episódios das séries da Biblioteca (`showrecord`).

## Bloco 3 — Preferências v2 & Motor `DiscoveryFeedService` (`DEC-003`, `DEC-004`, `DEC-007` / `AMP-03`, `AMP-06`)
- [ ] **T3.1** Evoluir `src/backend/repositories/preferences.py` para `schema_version: Literal[1, 2] = 2` (migração automática de v1) com `default_smart_lists_v2()`, `discovery_variance_pct`, `hero_auto_rotate`, `hero_interval_sec`, `impression_ttl_hours`, `hidden_builtin_shortcuts` e `custom_shortcuts`.
- [ ] **T3.2** Criar `src/backend/services/discovery_feed.py` com normalização bilíngue de `showrecord`, fórmula de variância `0–100%` sobre pools pré-filtrados, alocação por escassez crescente garantindo 1.000 títulos 100% únicos nas 10 listas (7 Gerais + 3 Personalizadas), Hero pool (12–15), Roleta estratificada (3 contrastes por escopo) e ring-buffer `discovery_impressions_v1` (máx. 200, TTL 48h).
- [ ] **T3.3** Expor `GET /api/explore/feed` (*read-only*) e `POST /api/explore/impressions` em `src/backend/api/explore.py`.

## Bloco 4 — Separação `DiscoverView` / `CatalogView`, Hero Vivo & Carrossel Circular (`DEC-005`, `DEC-006` / `AMP-04`, `AMP-05`)
- [ ] **T4.1** Atualizar `src/frontend/src/types/index.ts`, `src/frontend/src/services/api.ts` e `src/frontend/src/context/PreferencesContext.tsx` para contratos v2 e endpoints `/explore/feed` e `/explore/impressions`.
- [ ] **T4.2** Atualizar `src/frontend/src/components/Navbar.tsx` (5 abas de 1 palavra: **Descobrir · Catálogo · Fontes · Biblioteca · Coleções**) e `src/frontend/src/App.tsx` (elevação de `catalogFilters: FilterSnapshot` e ponte `openCatalogWithFilters`).
- [ ] **T4.3** Refatorar `HeroBanner.tsx` (auto-rotação 12s pausável no hover, setas, indicadores, motivo de destaque) e `ShowCarousel.tsx` (janela circular virtualizada ~24 cards, loop contínuo até 100, botão *"Abrir no Catálogo"*).
- [ ] **T4.4** Extrair `DiscoverView.tsx` (Hero + Atalhos Mistos sem *Diretor* + Roleta Contextual com escopo + 10 Listas) e `CatalogView.tsx` (Filtros no topo + Busca FTS5 + Pessoas + Calendário + botão **"Fixar como Atalho"**) substituindo o monólito `ExplorerView.tsx`.
- [ ] **T4.5** Atualizar `HydrationConsoleCard.tsx` para exibir delta/revisão remota do IMDb, contadores reais do EZTV e opção EZTV na Varredura.

## Bloco 5 — 5ª Categoria de Configurações ("Vitrine & Listas Inteligentes") & QA (`DEC-007` / `AMP-06`)
- [ ] **T5.1** Criar `src/frontend/src/components/settings/DiscoveryFeedPanel.tsx` e integrá-lo como 5ª categoria em `SettingsSidebar.tsx` e `StatusConfigView.tsx` (reordenação das 10+ listas, limite 20–100, ordenação, só com mídia, variância global e por lista, Hero, TTL e gestão de Atalhos).
- [ ] **T5.2** Escrever suíte de testes unitários e de integração cobrindo IMDb 2-estágios/hermeticidade, EZTV watermark/contadores, `DiscoveryFeedService` (deduplicação 100%, variância, impressões, perfil bilíngue) e migração de preferências `v1 → v2`.
- [ ] **T5.3** Validar `make lint && make test && make build-front`, reconciliar documentação canônica e emitir `ADR-021-ER.md`.
