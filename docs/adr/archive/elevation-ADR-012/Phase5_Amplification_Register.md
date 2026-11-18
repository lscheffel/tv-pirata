---
elevation_target: ADR-012
phase: 5
title: "Registro de Amplificação de Solução (5 Dimensões)"
status: COMPLETED
language: PT-BR
---

# Fase 5 — Registro de Amplificação (5 Categorias Canônicas)

Para elevar `Alt_C_Hardened_MultiSource_Adaptive` ao padrão SOTA de produção antes da geração da Quadra final (Fase 7), aplicamos amplificações verificáveis nas 5 categorias exigidas pela metodologia.

## 1. Completude (`Completeness`)
- **`AMP-COMP-01` — Inventário Completo de Navegação e Remoção de Rotas Mortas:** Substituição de `discover` + `explore` por `Explorar` e `catalog` por `Fontes de Dados`, mantendo redirecionamento ou alias seguro de estado inicial para não quebrar bookmarks/atalhos internos.
- **`AMP-COMP-02` — Cobertura Total da Taxonomia de Fontes:** Todas as fontes em `CANONICAL_DATA_SOURCES` (`canonical_taxonomy.py`) e futuros provedores de mídia em `sources.db` (`eztv`, `yify`, `1337x`, etc.) passam a alimentar tanto o filtro de fontes em `Explorar` quanto a aba `Fontes de Dados` e o cálculo unificado de `MediaBadge`.

## 2. Robustez (`Robustness`)
- **`AMP-ROB-01` — Cancelamento Determinístico (`AbortController`):** Cada disparo de `/api/explore` ou `/api/sources/*` cancela a requisição pendente anterior do mesmo canal e ignora `AbortError`, evitando condições de corrida em redes lentas ou digitação rápida (`350ms` debounce).
- **`AMP-ROB-02` — Barra de Progresso Não-Destrutiva:** Durante refiltragem, o grid atual permanece montado com barra de progresso linear no topo e `aria-busy="true"`, preservando contexto visual e posição de leitura.
- **`AMP-ROB-03` — Salvaguarda Responsiva `1 + N` (`< 190px`):** Evita que cartões compactos em `375px` tenham o pôster obstruído por 4–5 badges empilhadas; o empilhamento completo é mantido em `>= 190px` (`sm`/`md`) conforme decisão 5A/5-A alt.

## 3. Capacidade (`Capability`)
- **`AMP-CAP-01` — Contrato Polimórfico de Indexadores (`ExternalSourceProvider`):** Abstrai parsing, normalização, saúde e sincronização de fontes externas em `sources.db`, tornando o onboarding de `YIFY/YTS`, `1337x` ou novos indexadores puramente aditivo via registro de provedores.
- **`AMP-CAP-02` — Ações Configuráveis em Badges & Botão Expansível `44×44px`:** Permite mapear independentemente cliques em `ProviderBadge` (ex.: `filter_provider`, `open_details`, `copy_provider_name`) e `MediaBadge` (ex.: `open_sources_modal`, `filter_has_media`, `open_details`), além de acesso tátil de `44×44px` para Biblioteca, Fontes e Coleções.

## 4. Arquitetura (`Architectural`)
- **`AMP-ARC-01` — Persistência Híbrida de Preferências (`localStorage` + `sync_state`):** Evita estado efêmero de UI sem exigir autenticação multi-usuário complexa; sincroniza preferências globais do ambiente pessoal (`mainstream.db`) com cache instantâneo em navegador.
- **`AMP-ARC-02` — Desacoplamento UI/Transporte via `MediaBadge.tsx` + `SourcesModal`:** Generaliza `EztvBadge.tsx` -> `MediaBadge.tsx` e `TorrentModal.tsx` -> modal multi-fonte agrupado por provedor (`EZTV`, `YIFY`, `1337x`), mantendo compatibilidade de tipos em `types.ts`.

## 5. Operacional (`Operational`)
- **`AMP-OPS-01` — Central Única `Status, Sincronização & Config`:** Concentra saúde Dual-SSOT (`mainstream.db` + `sources.db`), disparo manual de atualizações, telemetria por indexador e preferências interativas atrás de um único botão `44×44px` com indicador semântico (`verde`/`âmbar`/`vermelho`) no topo da `Navbar`.
- **`AMP-OPS-02` — Gate de Verificação WCAG 2.2 + Heurísticas de Nielsen:** Obriga validação objetiva de contraste (`>= 4.5:1`), `prefers-reduced-motion`, `<label>` em buscas, `:focus-visible` e 3 cenários cronometrados de usabilidade antes de marcar `ADR-012` como concluída.
