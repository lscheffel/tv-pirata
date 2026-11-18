---
id: ADR-012-TODO
parent_adr: ADR-012
title: "Checklist Executável de Implementação — ADR-012"
status: ACCEPTED
implementation_status: PENDENTE
language: PT-BR
---

# ADR-012-TODO: Lista de Tarefas Verificáveis (1:1 com o Decision Ledger)

> [!IMPORTANT]
> Todas as tarefas abaixo permanecem desmarcadas (`[ ]`) até a execução da implementação e comprovação pelos portões de teste (`pytest`, `tsc`, `vite build`, Nielsen & WCAG 2.2).

## Fase 1 — Baseline Heurística, Backend Multi-Fonte (`sources.db`) & Preferências

- [ ] **TODO-12.01 (`DEC-006`):** Executar Avaliação Heurística de Nielsen baseline documentada para os 3 cenários críticos (fluxo mobile `375px < 30s`, filtragem booleana/reset e previsibilidade de badges clicáveis).
- [ ] **TODO-12.02 (`DEC-002`):** Implementar abstração polimórfica `ExternalSourceProvider` + registro de fontes (`eztv`, `yify`, `1337x`) e tabelas aditivas idempotentes (`external_sources`, `external_releases`) em `data/sources.db` preservando `EZTVShow`, `CatalogShow` e `CatalogRelease`.
- [ ] **TODO-12.03 (`DEC-002`):** Criar endpoints multi-fonte `/api/sources/summary`, `/api/sources/releases`, `/api/sources/catalog` e `/api/sources/sync`, mantendo `/api/catalog/*` e `/api/torrents/*` compatíveis retroativamente (`INV-03`).
- [ ] **TODO-12.04 (`DEC-003`):** Implementar `GET` e `PUT /api/explore/preferences` com persistência em `sync_state` (`data/mainstream.db`) e validação estrita via Pydantic (`schema_version: 1`, `badge_provider_action`, `badge_media_action`, `auto_apply_filters`, `show_all_genres`, `filter_panel_expanded`).

## Fase 2 — Navegação Unificada `Explorar` & Motor Híbrido de Filtragem

- [ ] **TODO-12.05 (`DEC-001`):** Consolidar abas `Descobrir` e `Explorar Universo` na aba única `Explorar` em `App.tsx` e `Navbar.tsx` (4 abas principais: `Explorar`, `Fontes de Dados`, `Biblioteca`, `Coleções` + acesso à Central Status/Config).
- [ ] **TODO-12.06 (`DEC-001`):** Implementar Modo Adaptativo em `ExplorerView.tsx`: exibir `HeroBanner` + Quick-Intent Bar + Roleta Contrastiva (3 títulos) + Carrosséis em estado ocioso, colapsando o Hero suavemente ao pesquisar ou aplicar filtros.
- [ ] **TODO-12.07 (`DEC-005`):** Implementar motor híbrido de filtragem: accordion iniciando com `showAllGenres=false` (top-10 gêneros), `debounce (350ms)` + `AbortController` em `api.ts`, barra de progresso linear não-destrutiva preservando o grid atual e botão `"Aplicar Filtros"` (respeitando toggle `"Auto-aplicar"`).

## Fase 3 — Aba `Fontes de Dados` & Central `Status, Sincronização & Config`

- [ ] **TODO-12.08 (`DEC-002`):** Refatorar `CatalogView.tsx` em `SourcesView` (`Fontes de Dados`) com filtros rápidos por indexador (`EZTV`, `YIFY/YTS`, `1337x`, etc.), telemetria de sincronização por provedor e busca paginada em `/api/sources/catalog`.
- [ ] **TODO-12.09 (`DEC-003`):** Adicionar botão `44×44px` (ícone de engrenagem + indicador semântico `verde`/`âmbar`/`vermelho`) no topo direito da `Navbar.tsx` abrindo `StatusConfigView` com controles Dual-SSOT (`mainstream.db` + `sources.db`) e painel de preferências interativas.
- [ ] **TODO-12.10 (`DEC-003`):** Implementar módulo `preferencesStorage.ts` com parsing defensivo de `localStorage`, defaults seguros (`RT-04`) e reconciliação assíncrona em background com `/api/explore/preferences`.

## Fase 4 — Redesign Interativo do `ShowCard`, `MediaBadge` & Modal Multi-Fonte

- [ ] **TODO-12.11 (`DEC-002`):** Estender `/api/explore` e `/api/discovery` (via `EngineScopedCache`) para retornar disponibilidade agregada agnóstica (`has_media`, `media_sources`, `sources_count`) mantendo `has_eztv` e `eztv_id` por retrocompatibilidade.
- [ ] **TODO-12.12 (`DEC-004`):** Refatorar `ShowCard.tsx` para empilhar **todos** os `ProviderBadge`s acima da `StatusBadge` no canto inferior esquerdo em cards `>= 190px` e aplicar salvaguarda responsiva `1 + N` em cards `< 190px` (`375px` mobile).
- [ ] **TODO-12.13 (`DEC-002`, `DEC-004`):** Substituir `EztvBadge.tsx` por `MediaBadge.tsx` posicionada **abaixo** da nota IMDb no canto superior direito e evoluir `TorrentModal.tsx` para modal multi-fonte agrupado por provedor (magnets e links externos).
- [ ] **TODO-12.14 (`DEC-004`):** Tornar `ProviderBadge` e `MediaBadge` botões clicáveis isolados (`e.stopPropagation()`, tooltip/`aria-label` dinâmicos conforme `DEC-003`), manter pôster clicável abrindo `ShowDetailModal` e substituir botões hover por botão expansível tátil `44×44px` (`Biblioteca`, `Fontes Media`, `Coleções`).

## Fase 5 — Acessibilidade WCAG 2.2, Verificação & Portão de Qualidade

- [ ] **TODO-12.15 (`DEC-006`):** Aplicar hardening WCAG 2.2 AA/AAA: `@media (prefers-reduced-motion: reduce)` em `index.css`, `<label>` explícito no campo de busca da `Navbar`, anéis `:focus-visible` uniformes, alvos `>= 44×44px` e contraste `>= 4.5:1`.
- [ ] **TODO-12.16 (`DEC-002`, `DEC-003`, `DEC-004`):** Escrever testes automatizados `pytest` (novas rotas `/api/sources/*`, `/api/explore/preferences`, `has_media` agregado e retrocompatibilidade `/api/catalog/*` + `/api/torrents/*`).
- [ ] **TODO-12.17 (`DEC-001`..`DEC-006`):** Executar suíte completa de validação (`make lint`, `make test`, `npx tsc --noEmit`, `make build-front`) e confirmar re-avaliação da Checklist Heurística de Nielsen + WCAG 2.2 sem regressões.
- [ ] **TODO-12.18 (`DEC-001`..`DEC-006`):** Reconciliar documentação canônica (PT-BR) e executar `adr-archive` para emissão do `ADR-012-ER.md` após 100% de conclusão.
