---
id: ADR-012-PI
parent_adr: ADR-012
title: "Plano de Implementação Faseado — ADR-012"
status: ACCEPTED
implementation_status: PENDENTE
language: PT-BR
---

# ADR-012-PI: Plano de Implementação Incremental

## Estratégia de Execução (`Blast Radius = 8.5 / CRITICAL`)

Para neutralizar riscos de regressão na SPA e no acesso Dual-SSOT (`mainstream.db` + `sources.db`), a execução será dividida em **5 ondas incrementais**, mantendo sempre os testes `pytest` e o build TypeScript/Vite verdes ao final de cada onda.

---

## Onda 1 — Contratos Backend Multi-Fonte, Preferências & Baseline UX (`TODO-12.01` a `TODO-12.04`, `TODO-12.11`)
1. Registrar baseline da Avaliação Heurística de Nielsen sobre os 3 fluxos críticos.
2. Implementar migração aditiva idempotente em `data/sources.db` (`external_sources`, `external_releases`) e registro `ExternalSourceProvider` (`eztv`, `yify`, `1337x`).
3. Expor rotas `/api/sources/*` e `/api/explore/preferences` mantendo `/api/catalog/*` e `/api/torrents/*` compatíveis.
4. Estender projeção de `/api/explore` e `/api/discovery` com `has_media`, `media_sources` e `sources_count` dentro do `EngineScopedCache`.
- **Gate da Onda 1:** `pytest` passando com novos testes de integração dos endpoints aditivos e zero quebra de testes existentes.

## Onda 2 — Navegação Unificada `Explorar` & Motor Reativo (`TODO-12.05` a `TODO-12.07`)
1. Atualizar `Navbar.tsx` e `App.tsx` para 4 abas principais (`Explorar`, `Fontes de Dados`, `Biblioteca`, `Coleções`) + acesso `Status/Sync/Config`.
2. Integrar Modo Adaptativo em `ExplorerView.tsx` (Hero + Quick-Intent + Roleta 3 itens + Carrosséis em estado ocioso -> colapso ao pesquisar/filtrar).
3. Implementar `AbortController`, `350ms` debounce, barra de progresso linear não-destrutiva, top-10 gêneros inicial (`showAllGenres=false`) e botão `"Aplicar Filtros"`.
- **Gate da Onda 2:** `tsc --noEmit` + `vite build` limpos; validação via `TestClient` e inspeção de estado sem race conditions.

## Onda 3 — `Fontes de Dados` & Central `Status, Sincronização & Config` (`TODO-12.08` a `TODO-12.10`)
1. Evoluir `CatalogView.tsx` para `SourcesView` multi-provedor com telemetria e filtros por fonte (`EZTV`, `YIFY/YTS`, `1337x`).
2. Criar `StatusConfigView` e `preferencesStorage.ts` integrando botão `44×44px` + ponto de saúde na `Navbar`.
- **Gate da Onda 3:** Persistência híbrida validada em `localStorage` + `/api/explore/preferences`.

## Onda 4 — `ShowCard`, `MediaBadge` & Modal Multi-Fonte (`TODO-12.12` a `TODO-12.14`)
1. Criar `MediaBadge.tsx` e atualizar `TorrentModal.tsx` para agrupamento multi-provedor.
2. Refatorar `ShowCard.tsx`: empilhamento completo `>= 190px`, salvaguarda `1 + N` em `< 190px`, `MediaBadge` abaixo da nota IMDb, badges clicáveis configuráveis com `e.stopPropagation()` + `aria-label` dinâmico, e botão expansível `44×44px`.
- **Gate da Onda 4:** Verificação responsiva programática (`< 190px` vs `>= 190px`), isolamento de eventos e build completo sem erros.

## Onda 5 — Hardening WCAG 2.2, Auditoria Final & Arquivamento (`TODO-12.15` a `TODO-12.18`)
1. Aplicar `@media (prefers-reduced-motion: reduce)`, `<label>` na busca global, `:focus-visible` e conferência de contraste `>= 4.5:1`.
2. Rodar `make lint`, `make test`, `npx tsc --noEmit`, `make build-front` e checar os 3 cenários de Nielsen.
3. Atualizar documentação PT-BR e arquivar `ADR-012` com `ADR-012-ER.md` quando todas as tarefas estiverem concluídas.
