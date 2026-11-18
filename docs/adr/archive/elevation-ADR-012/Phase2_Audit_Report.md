---
elevation_target: ADR-012
phase: 2
title: "Auditoria Forense da Proposta Inicial (Red-Flag Discovery)"
status: COMPLETED
language: PT-BR
---

# Fase 2 — Auditoria Forense da Proposta Inicial

Esta auditoria avalia a proposta bruta consolidada na convergência UX (`garimpo` + `ux-researcher-designer` + `ui-ux-pro-max`) antes da elevação arquitetural, identificando falhas estruturais, riscos de usabilidade mobile e dívidas de escalabilidade.

## 1. Achados Críticos (`CRITICAL`)

### `AUD-CRIT-01`: Colisão Tátil e Saturação Visual no `ShowCard` em Viewports Mobile (`375px`)
- **Evidência na Proposta Bruta:** Exibir **todos** os provedores de streaming empilhados verticalmente acima da `StatusBadge` + `MediaBadge` abaixo da nota + poster clicável + botão de ação sobre cartões `w-[160px]` (2 colunas em `375px`).
- **Risco:** Em uma grade de 2 colunas em `375px`, cada cartão tem ~`160–170px` de largura e ~`240–255px` de altura. Um título disponível em 4 ou 5 streamings empilhados cobre >`65%` da área esquerda do pôster e força cliques acidentais nas badges ao tentar tocar no pôster para abrir o `ShowDetailModal`.

### `AUD-CRIT-02`: Condições de Corrida (`Race Conditions`) em Filtros Reativos + SQL Pushdown
- **Evidência na Proposta Bruta:** A busca textual e toggles de filtro disparam consultas pesadas sobre `279.362` obras em `mainstream.db` + joins com `sources.db`.
- **Risco:** Sem `debounce` coordenado e sem `AbortController` na camada `api.ts`, uma sequência rápida de cliques/digitação pode permitir que uma resposta antiga sobrescreva uma resposta mais recente na UI, exibindo resultados inconsistentes com os filtros ativos.

### `AUD-CRIT-03`: Acoplamento Implícito a `CatalogRelease.eztv_id` na Generalização Multi-Fonte
- **Evidência na Proposta Bruta:** Renomear `Catálogo EZTV` para `Fontes de Dados` e suportar `EZTV`, `YIFY/YTS`, `1337x`, etc., sem redesenhar o contrato de `sources.db` (`eztv_id`, `TorrentModal` chamando apenas `/api/torrents/{imdb_id}`).
- **Risco:** Novos indexadores que não possuem `eztv_id` numérico ou que disponibilizam links/magnets por provedor distinto quebram o modelo relacional de `CatalogRelease` (`db.py#L168-L189`) e geram `has_media` falso-negativo ou erro de integridade.

---

## 2. Achados Maiores (`MAJOR`)

### `AUD-MAJ-01`: Imprevisibilidade Cognitiva de Badges Clicáveis Configuráveis
- **Descrição:** Se o clique em `ProviderBadge` ou `MediaBadge` muda de comportamento conforme preferência em `Status, Sincronização & Config` (`filtrar catálogo`, `abrir detalhes`, `abrir fontes/magnets`), o usuário pode não reconhecer o efeito antes do clique.
- **Mitigação Necessária:** Tooltip explícito, `aria-label` dinâmico refletindo a ação ativa configurada, e feedback visual claro de foco/cursor (`cursor-pointer`, `:focus-visible`).

### `AUD-MAJ-02`: Perda de Estado de Preferências entre Sessões ou Abas
- **Descrição:** Persistir preferências apenas em memória React reinicia configurações ao recarregar; persistir apenas no servidor bloqueia feedback instantâneo offline/inicial.
- **Mitigação Necessária:** Estratégia híbrida (`localStorage` como cache síncrono imediato + sincronização assíncrona com `GET`/`PUT /api/explore/preferences` em `data/mainstream.db`).

### `AUD-MAJ-03`: Sobrecarga na Expansão Inicial de Gêneros e Fontes
- **Descrição:** Exibir `31` gêneros + `25` provedores + `8` fontes abertos por padrão empurra o grid de resultados para fora da primeira dobra (*above the fold*) em notebooks e celulares.
- **Mitigação Necessária:** Accordion de filtros recolhido por padrão em buscas rápidas, iniciando com `showAllGenres=false` (top-10 gêneros) e estado memorizado em `localStorage`.

---

## 3. Achados Menores (`MINOR`)

### `AUD-MIN-01`: Ausência de Barra de Progresso Não-Destrutiva durante Refiltragem
- **Descrição:** Substituir toda a grade de resultados por skeletons a cada alteração de filtro causa *layout shift* e sensação de lentidão.
- **Mitigação Necessária:** Barra de progresso linear discreta no topo mantendo o grid atual visível (`opacity` sutil / `aria-busy="true"`) até a chegada da resposta atual.

### `AUD-MIN-02`: Lacunas de WCAG 2.2 em Controles Já Existentes
- **Descrição:** `Navbar.tsx` usa `<input>` de busca sem `<label>` (apenas placeholder) e botão limpar de tamanho `p-1`; `index.css` não respeita `prefers-reduced-motion`.
- **Mitigação Necessária:** Incluir auditoria heurística de Nielsen + checklist WCAG 2.2 obrigatório como critério de aceite da `ADR-012`.

---

## 4. Resumo de Gravidade Pré-Elevação

| Severidade | Quantidade | Bloqueia Aprovação Direta? |
| :--- | :---: | :---: |
| `CRITICAL` | 3 | **Sim** (Requer redesenho na Fase 3–5) |
| `MAJOR` | 3 | **Sim** (Requer contratos aditivos) |
| `MINOR` | 2 | Recomendado corrigir na Fase 5 |
