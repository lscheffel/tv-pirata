---
elevation_target: ADR-012
title: "Resumo Executivo da Elevação Arquitetural — ADR-012"
status: CERTIFIED
language: PT-BR
---

# Resumo Executivo — Elevação Arquitetural `ADR-012`

- **Alvo:** Conjunto `ADR-012` (*Experiência Unificada de Exploração, Camada Multi-Fonte de Dados, Central Status/Sync/Config e ShowCard Interativo*).
- **Complexidade & Risco:** `DCI = 7` (**Tier 2**) | `Blast Radius = 8.5` (**CRITICAL — One-Way Door**).
- **Veredito:** **`KEEP + AMPLIFY`** → Alternativa vencedora **`Alt_C_Hardened_MultiSource_Adaptive`** (`8.99` vs. `7.93` e `7.53`, margem `+1.06` via `matrix_scorer.py`).

## Principais Entregas Endurecidas no Conjunto Final (`docs/adr/ADR-012*.md`)

1. **Navegação & Descoberta Unificada (`DEC-001`):** Consolida `Descobrir` e `Explorar Universo` na aba `Explorar` em Modo Adaptativo (Hero + Quick-Intent Bar + Roleta 3 itens + Carrosséis em estado ocioso; colapso ao pesquisar/filtrar).
2. **Camada Multi-Fonte de Dados (`DEC-002`):** Substitui `Catálogo EZTV` por `Fontes de Dados` com contrato polimórfico aditivo em `data/sources.db` (`eztv`, `yify`, `1337x`, etc.), rotas `/api/sources/*` compatíveis retroativamente com `/api/catalog/*` e `/api/torrents/*`, substituição de `EztvBadge.tsx` por `MediaBadge.tsx` (abaixo da nota IMDb) e evolução de `TorrentModal.tsx`.
3. **Central `Status, Sincronização & Config` (`DEC-003`):** Botão `44×44px` + ponto de saúde no topo da `Navbar`, reunindo controles Dual-SSOT e preferências híbridas (`localStorage` + `GET`/`PUT /api/explore/preferences` em `sync_state`).
4. **`ShowCard` Interativo Seguro (`DEC-004`):** Todos os provedores empilhados acima de `StatusBadge` em `>= 190px`, salvaguarda automática `1 + N` abaixo de `190px` (`375px` mobile), `MediaBadge` abaixo da nota IMDb, badges clicáveis isoladas com `aria-label` dinâmico, clique no pôster abrindo `ShowDetailModal` e botão rápido expansível `44×44px`.
5. **Filtragem Híbrida & Acessibilidade (`DEC-005`, `DEC-006`):** `debounce 350ms` + `AbortController`, accordion top-10 gêneros inicial, barra linear não-destrutiva, `@media (prefers-reduced-motion: reduce)` e gate formal via Avaliação Heurística de Nielsen + WCAG 2.2 AA/AAA (`18` tarefas rastreadas em `ADR-012-TODO.md`).
