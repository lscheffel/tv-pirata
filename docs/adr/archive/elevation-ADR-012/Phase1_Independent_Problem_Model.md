---
elevation_target: ADR-012
phase: 1
title: "Modelo Independente de Problema — UX Unificada, Multi-Fonte de Dados, Configurabilidade e ShowCard Interativo"
status: COMPLETED
language: PT-BR
---

# Fase 1 — Modelo Independente de Problema (First Principles)

## 1. Enquadramento do Problema (Sem Solução Prematura)

O **TV Pirata (`v0.7.0`)** consolidou uma fundação de dados Dual-SSOT (`data/mainstream.db` com `279.362` obras e `4.529.748` episódios via IMDb/TMDB/TVMaze + `data/sources.db` com `860` séries e `140.571` episódios da EZTV). Entretanto, a camada de apresentação e a abstração da Camada 2 (`sources.db`) ainda refletem decisões desenhadas antes da unificação do universo canônico:

1. **Fragmentação de Navegação e Sobreposição Cognitiva (`Descobrir` vs. `Explorar Universo`):**
   - `Navbar.tsx` expõe `discover`, `explore`, `catalog`, `library` e `collections` lado a lado.
   - Tanto `Descobrir` quanto `Explorar Universo` (`ExplorerView.tsx`) servem o fluxo de descoberta sobre o mesmo núcleo de dados, dividindo carrosséis curados/roleta da pesquisa facetada avançada e diluindo o ponto de entrada principal.

2. **Acoplamento Rígido da Camada de Recursos ao Provedor EZTV:**
   - `CatalogView.tsx`, `EztvBadge.tsx`, `TorrentModal.tsx` (`"Torrents EZTV: {show.title}"`), `CatalogRelease.eztv_id` (`src/backend/models/db.py`) e rotas `/api/catalog/*` + `/api/torrents/*` tratam a Camada 2 como sinônimo exclusivo de EZTV.
   - Novos indexadores planejados (`YIFY/YTS`, `1337x`, trackers/links externos) não possuem contrato polimórfico, tabela unificada por provedor de fonte, nem identidade visual agnóstica no cartaz (`Media` em vez de `EZTV`).

3. **Sobrecarga de Filtros e Falta de Controle Explícito/Debounce:**
   - O painel de filtros exibe simultaneamente dezenas de badges/botões (até `31` gêneros canônicos, `25` provedores, `6` formatos, `8` fontes de dados), gerando fadiga visual no primeiro contato, especialmente em viewports móveis (`375px`).
   - Faltam mecanismos coordenados de `debounce`, cancelamento de requisições concorrentes (`AbortController`) e distinção clara entre modo instantâneo e confirmação explícita em combinações booleanas (`OR` / `AND` / `NOT`).

4. **Densidade e Ambiguidade Visual no `ShowCard.tsx`:**
   - Em `ShowCard.tsx` (`w-[160px] sm:w-[190px] md:w-[220px]`, `aspect-[2/3]`), apenas o primeiro `ProviderBadge` é renderizado ao lado de `StatusBadge`, omitindo outros provedores simultâneos (ex.: título disponível em `Netflix`, `Prime Video` e `Max` ao mesmo tempo).
   - `EztvBadge` ocupa o canto superior esquerdo enquanto as badges inferiores não possuem ações configuráveis nem semântica uniforme de clique.
   - Botões de ação (`opacity-0 group-hover:opacity-100`, `p-1.5`) dependem de hover e ficam abaixo do alvo tátil mínimo recomendado (`44×44px`).

5. **Ausência de Central Dedicada de Status, Sincronização e Preferências:**
   - Controles de sincronização Dual-SSOT (`mainstream.db` e `sources.db`) estão misturados à barra de filtros de descoberta, e o usuário não possui local dedicado para configurar comportamentos interativos (ações de clique nas badges de provedor e de mídia, auto-aplicação de filtros).

6. **Dívidas de Acessibilidade (WCAG 2.2 AA/AAA) e Movimento:**
   - `Navbar.tsx` possui campo de busca sem `<label>` associado e botão limpar com `p-1`.
   - `src/frontend/src/index.css` não declara `@media (prefers-reduced-motion: reduce)`.
   - Contraste de rótulos secundários em cartões escuros (`#090a0f` / `#131722`) e estados `:focus-visible` precisam de padronização verificável (`>= 4.5:1`).

---

## 2. Restrições Invariantes

| ID | Restrição Arquitetural | Origem |
| :--- | :--- | :--- |
| `INV-01` | **Independência da Camada 1:** O catálogo canônico (`IMDbCatalogShow` / `MediaWork` em `data/mainstream.db`) jamais pode exigir torrent ou arquivo SMB local para existir ou aparecer na descoberta. | `AGENTS.md` §2.2 / `ADR-008` |
| `INV-02` | **Isolamento Dual-SSOT:** `IMDbCatalogShow` permanece em `data/mainstream.db` (`imdb_metadata`); provedores de mídia e catálogos de fontes permanecem em `data/sources.db` (`eztv_metadata` / metadados de fontes). | `ADR-011` |
| `INV-03` | **Zero Quebra Silenciosa de Contratos:** Rotas legadas (`/api/catalog/*`, `/api/torrents/*`, `has_eztv` / `eztv_id`) devem manter compatibilidade retroativa durante a transição para multi-fonte (`sources`, `has_media`). | `AGENTS.md` §2.1 |
| `INV-04` | **Alvos Táteis & Mobile-First (`375px`):** Controles clicáveis não podem colidir em cartões compactos nem violar área mínima de `44×44px` em ações primárias. | `WCAG 2.2` / Convergência R2 |
| `INV-05` | **Governança Linguística Dual:** UI e documentação humana em **PT-BR**; código, tipos, testes e docstrings em **EN-US**. | `AGENTS.md` §2.8 |

---

## 3. Fluxos Críticos Centrais

1. **Descoberta Rápida & Filtragem Booleana (`< 30s`):** Usuário abre o app diretamente na aba unificada `Explorar`, usa busca rápida ou intent bar (hero colapsa suavemente) ou expande filtros booleanos com top-10 gêneros, aplica e abre detalhes ou fonte sem perder resultados atuais durante carregamento.
2. **Inspeção & Ação em `ShowCard`:** Usuário visualiza provedores empilhados acima do status e badge `Media` abaixo da nota IMDb; clique no pôster abre `ShowDetailModal`; clique nas badges executa a ação configurada (`filtrar`, `abrir modal/fontes`, `abrir link/busca`) com previsibilidade; botão expansível `44×44px` expõe ações de Biblioteca / Fontes / Coleções sem depender de hover.
3. **Gestão Multi-Fonte & Saúde do Sistema:** Usuário navega para `Fontes de Dados` para filtrar/explorar indexadores (`EZTV`, `YIFY/YTS`, `1337x`, etc.) ou clica no botão `Status, Sincronização & Config` (`44×44px` + ponto de saúde na barra superior) para disparar sync Dual-SSOT e ajustar preferências persistidas híbridas (`localStorage` + backend `sync_state`).
