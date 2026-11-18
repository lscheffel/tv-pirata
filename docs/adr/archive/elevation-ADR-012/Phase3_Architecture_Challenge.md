---
elevation_target: ADR-012
phase: 3
title: "Desafio Arquitetural & Exploração do Espaço de Design"
status: COMPLETED
language: PT-BR
---

# Fase 3 — Desafio Arquitetural & Exploração de Alternativas

## 1. Síntese das Alternativas Arquiteturais Avaliadas

Para resolver os 3 achados `CRITICAL` e 3 achados `MAJOR` identificados na Fase 2 sem sacrificar a identidade visual nem as decisões de produto da convergência R2, modelamos três arquiteturas candidatas sobre os eixos: **Navegação/Exploração**, **Camada 2 Multi-Fonte (`sources.db`)**, **`ShowCard` Mobile/Desktop**, **Motor de Filtragem** e **Persistência de Preferências**.

---

### Alternativa A (`Alt_A_Proposta_Original`): Implementação Direta da Convergência R2
- **Topologia:** Unifica `Explorar`, renomeia `Fontes de Dados` mantendo estrutura centrada em `CatalogRelease.eztv_id`, renderiza todas as badges de streaming empilhadas em qualquer largura de `ShowCard`, aplica filtros diretamente sem `AbortController` unificado, e salva preferências apenas em `localStorage`.
- **Pontos Fortes:** Baixo atrito inicial de implementação; atende literalmente às escolhas visuais no desktop (`>= 190px`).
- **Fragilidades:** Falha em `AUD-CRIT-01` (saturação tátil em `375px`), `AUD-CRIT-02` (race condition em consultas rápidas) e `AUD-CRIT-03` (acoplamento a `eztv_id` bloqueia `YIFY/YTS` e `1337x`).

---

### Alternativa B (`Alt_B_Card_Bipartido_SPA_Only`): Card Bipartido SPA-Only com Metadados Separados do Pôster
- **Topologia:** Move todas as badges e botões de ação para fora do pôster (`2/3` imagem limpa + rodapé denso bipartido com badges e ações), cria filtros em 2 estágios no frontend, mas mantém configuração exclusivamente no cliente (`SPA-Only`) sem persistência no `mainstream.db` nem abstração de provedores de fontes no backend.
- **Pontos Fortes:** Elimina colisões táteis dentro do pôster em qualquer viewport; reduz ruído visual sobre a arte do cartaz.
- **Fragilidades:** Contraria a decisão explícita de manter badges clicáveis sobre o cartaz (provedores empilhados acima de status e `Media` abaixo da nota IMDb); não resolve a extensão do backend multi-fonte (`sources.db`) nem sincroniza preferências no Dual-SSOT.

---

### Alternativa C (`Alt_C_Hardened_MultiSource_Adaptive`): Arquitetura Híbrida Endurecida Multi-Fonte & Adaptativa (Candidata Elevada)
- **Topologia:** Combina o layout de pôster aprovado (provedores empilhados acima de `StatusBadge` + `MediaBadge` abaixo da nota IMDb + botão expansível `44×44px`) com:
  1. **Salvaguarda Responsiva `1 + N` em `< 190px` (`375px` mobile):** Exibe todos os provedores empilhados em `>= 190px` (`sm`/`md`) e condensa automaticamente para badge principal + `+N` expandível em cartões estreitos `< 190px`, zerando `AUD-CRIT-01`.
  2. **Generalização Real Multi-Fonte em `sources.db`:** Introduz contrato polimórfico `ExternalSourceRelease` + registro de indexadores (`eztv`, `yify`, `1337x`, etc.) com rotas `/api/sources/*` aditivas mantendo `/api/catalog/*` e `/api/torrents/*` compatíveis retroativamente (`INV-03`).
  3. **Motor Híbrido Reativo + Seguro:** `debounce (350ms)` + `AbortController` na camada `api.ts` + barra de progresso linear no topo preservando resultados atuais + painel booleano com modo explícito `"Aplicar Filtros"` (e toggle opcional `"Auto-aplicar"`), accordion `showAllGenres=false` (top-10) memorizado.
  4. **Preferências Híbridas (`localStorage` + `GET`/`PUT /api/explore/preferences`):** Cache instantâneo local com sincronização em background em `data/mainstream.db` (`sync_state`), garantindo previsibilidade de badges clicáveis via tooltip/`aria-label` dinâmico.
  5. **Hardening WCAG 2.2 AA/AAA + Heurísticas de Nielsen:** Gate formal de usabilidade e acessibilidade (`prefers-reduced-motion`, `<label>`, `:focus-visible`, contraste `>= 4.5:1`).

---

## 2. Desafios por Dimensão

| Dimensão | Risco Principal | Como `Alt C` Resolve |
| :--- | :--- | :--- |
| **Camada 1 vs. Camada 2** | Vazamento de P2P para `mainstream.db` | `sources.db` isola todas as fontes (`eztv`, `yify`, `1337x`); `mainstream.db` expõe apenas flags agregadas (`has_media`, `sources_count`, `media_sources`). |
| **Ergonomia em `375px`** | Toque acidental sobre 4–5 badges | Regra adaptativa: empilhamento total em `>= 190px` e resumo `1 + N` em `< 190px`. |
| **Concorrência de Consultas** | Sobrescrita de grid por resposta lenta | `AbortController` por chave de query + `350ms` debounce + barra de progresso não-destrutiva. |
| **Previsibilidade de Cliques** | Badge fazer algo inesperado | Rótulo de tooltip e `aria-label` dinâmicos refletindo a configuração selecionada pelo usuário. |
