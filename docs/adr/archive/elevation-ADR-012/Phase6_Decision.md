---
elevation_target: ADR-012
phase: 6
title: "Decisão de Elevação Arquitetural (Veredito)"
status: COMPLETED
verdict: "KEEP + AMPLIFY"
selected_alternative: Alt_C_Hardened_MultiSource_Adaptive
language: PT-BR
---

# Fase 6 — Decisão da Elevação Arquitetural

## 1. Veredito Formal

- **Veredito:** **`KEEP + AMPLIFY`**
- **Alternativa Selecionada:** **`Alt_C_Hardened_MultiSource_Adaptive`** (Pontuação ponderada **`8.99 / 10.00`**, margem de **`+1.06`** sobre `Alt_B_Card_Bipartido_SPA_Only` com `7.93` e **`+1.46`** sobre `Alt_A_Proposta_Original` com `7.53`).
- **Classificação de Risco (`BR`):** **`8.5` (`CRITICAL` — One-Way Door)**, com todos os 4 vetores levantados pelo Red Team mitigados por desenho na Fase 4 e amplificados na Fase 5.

## 2. Justificativa Executiva

1. **Preserva integralmente a visão de produto escolhida pelo usuário (Convergência R2):**
   - `Navbar` consolidada em **Explorar** (unificando `Descobrir` + `Explorar Universo` em Modo Adaptativo) e **Fontes de Dados** (substituindo `Catálogo EZTV` com suporte multi-provedor), além de `Biblioteca` e `Coleções`, mais botão `44×44px` com ponto de saúde para **Status, Sincronização & Config**.
   - `ShowCard` mantendo badges de provedores empilhadas acima de `StatusBadge`, `MediaBadge` abaixo da nota IMDb, badges clicáveis configuráveis, clique no pôster abrindo `ShowDetailModal`, e botão expansível de ações rápidas.
2. **Elimina os 3 bloqueadores críticos identificados na Auditoria Forense:**
   - Resolve `AUD-CRIT-01` via condensação responsiva `1 + N` abaixo de `190px` (`375px` mobile), mantendo o empilhamento completo em cards `>= 190px`.
   - Resolve `AUD-CRIT-02` via `debounce (350ms)` + `AbortController` + barra de progresso não-destrutiva + botão explícito `"Aplicar Filtros"` (com toggle opcional `"Auto-aplicar"`).
   - Resolve `AUD-CRIT-03` generalizando `sources.db` e `/api/sources/*` sem acoplamento a `eztv_id` e mantendo compatibilidade retroativa com `/api/catalog/*` e `/api/torrents/*`.
3. **Alcança Governança SOTA completa:**
   - Incorpora Avaliação Heurística de Nielsen + checklist WCAG 2.2 AA/AAA + `@media (prefers-reduced-motion: reduce)` diretamente no `ADR-012-TODO.md` e nos critérios de aceite da Fase 7.

## 3. Diretriz para a Fase 7 (Hardened Decision Set)

Promover a Quadra SOTA endurecida (`ADR-012.md`, `ADR-012-BP.md`, `ADR-012-TODO.md`, `ADR-012-PI.md`) dentro de `Phase7_Hardened_Decision_Set/` e espelhá-la na raiz `docs/adr/` com status `ACCEPTED` e `implementation_status: PENDENTE` (todas as tarefas rigorosamente desmarcadas `[ ]` para rastreamento futuro pelo workflow de implementação e `adr-archive`).
