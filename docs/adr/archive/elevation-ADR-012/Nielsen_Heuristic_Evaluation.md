---
elevation_target: ADR-012
task_id: TODO-12.01
title: "Avaliação Heurística de Nielsen — Baseline & Verificação Final"
status: VERIFIED_PASSED
language: PT-BR
---

# Avaliação Heurística de Nielsen (`TODO-12.01`)

## 1. Cenários Críticos Auditados (v0.7.0 Baseline vs. Meta `ADR-012`)

### Cenário A — Descoberta & Filtragem Rápida em Mobile (`375px`, Meta `< 30s`, `0` toques acidentais)
- **Estado Baseline (`v0.7.0`):**
  - *H8 (Estética e Design Minimalista):* `Navbar` exibe 5 abas (`Descobrir`, `Explorar Universo`, `Catálogo EZTV`, `Biblioteca`, `Coleções`) criando sobreposição cognitiva entre as duas primeiras.
  - *H1 (Visibilidade do Estado do Sistema):* Busca na `Navbar` troca toda a vista sem barra de progresso discreta não-destrutiva.
  - *H7 (Flexibilidade e Eficiência de Uso) / Touch:* Cartões `w-[160px]` exibem apenas 1 provedor (ocultando os demais), `p-1.5` dependentes de hover (`opacity-0 group-hover:opacity-100`), sem botão tátil `44×44px`.
- **Critério de Aceite `ADR-012`:** Abas consolidadas em `Explorar` (ocioso = Hero + Quick-Intent + Roleta 3 itens + Carrosséis; busca/filtro colapsa Hero); salvaguarda `1 + N` automática abaixo de `190px`; ações rápidas em botão expansível `44×44px`.

### Cenário B — Filtragem Booleana (`OR`/`AND`/`NOT`), Accordion e Reset
- **Estado Baseline (`v0.7.0`):**
  - *H8 / Sobrecarga Cognitiva:* Todos os gêneros e provedores são renderizados abertos simultaneamente empurrando os resultados abaixo da dobra.
  - *H5 (Prevenção de Erros):* Disparos reativos sem `AbortController` permitem *race condition* quando consultas SQL Pushdown sobre `279k+` obras completam fora de ordem.
- **Critério de Aceite `ADR-012`:** Accordion recolhido por padrão iniciando com `showAllGenres=false` (top-10 gêneros) memorizado via `preferencesStorage`; `debounce (350ms)` + `AbortController` em `api.ts`; modo híbrido com botão explícito `"Aplicar Filtros"` (e toggle opcional `"Auto-aplicar"`); barra linear não-destrutiva mantendo grid visível.

### Cenário C — Previsibilidade de Badges Clicáveis & Multi-Fonte
- **Estado Baseline (`v0.7.0`):**
  - *H4 (Consistência e Padrões):* `EztvBadge` acopla visualmente a Camada 2 exclusivamente à EZTV; apenas o 1º streaming é exibido ao lado da nota/status.
  - *H2 (Correspondência entre o Sistema e o Mundo Real) / H6 (Reconhecimento em vez de Memorização):* Badges não são clicáveis nem comunicam efeitos; não há central de preferências ou status Dual-SSOT dedicada.
- **Critério de Aceite `ADR-012`:** Empilhamento vertical de **todos** os provedores acima de `StatusBadge` (`>= 190px`), `MediaBadge` abaixo da nota IMDb, tooltips e `aria-label` dinâmicos refletindo `badge_provider_action` e `badge_media_action` configurados na Central `Status, Sincronização & Config` (`44×44px` + ponto de saúde).

---

## 2. Checklist WCAG 2.2 Baseline vs. Target

| Requisito WCAG 2.2 | Baseline `v0.7.0` | Target `ADR-012` |
| :--- | :---: | :--- |
| `<label>` na busca global (`Navbar.tsx`) | Ausente | `<label htmlFor="navbar-global-search" className="sr-only">` — **VERIFICADO** |
| `@media (prefers-reduced-motion: reduce)` (`index.css`) | Ausente | Declarado globalmente — **VERIFICADO** |
| Alvos táteis mínimos (`44×44px`) | Botões `p-1` / `p-1.5` | `min-w-[44px] min-h-[44px]` na Navbar, ShowCard, TorrentModal e StatusConfigView — **VERIFICADO** |
| `:focus-visible` uniforme de alto contraste | Parcial | Anel `#38bdf8` global em `index.css` — **VERIFICADO** |
| Contraste de texto secundário (`>= 4.5:1` sobre `#090a0f`/`#131722`) | Parcial (`slate-500`) | Textos funcionais elevados para `slate-300`/`slate-200` — **VERIFICADO** |
