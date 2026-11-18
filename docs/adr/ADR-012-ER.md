---
id: ADR-012-ER
type: er
title: "Evidence Record - ADR-012: Experiência Unificada de Exploração, Camada Multi-Fonte de Dados, Central Status/Sync/Config e ShowCard Interativo"
created: 2026-11-17
updated: 2026-11-17
adr_ref: ADR-012
implementation_status: CONSOLIDADA
tasks_completed: 18/18
completion_rate: 100%
verification_gate: PASSED
---

# Evidence Record — ADR-012: Experiência Unificada de Exploração, Camada Multi-Fonte de Dados, Central Status/Sync/Config e ShowCard Interativo

> **Documento de Evidência e Certificação Algorítmica de Conclusão**  
> Gerado automaticamente pelo Gatekeeper Janitor (`adr-archive / audit.py`).  
> Este artefato constitui a prova imutável e verificável de que o Decision Set da `ADR-012` foi 100% implementado e auditado.

---

## 1. Metadados de Execução e Certificação

| Campo | Valor |
|---|---|
| **ADR Referência** | [`ADR-012`](./ADR-012.md) |
| **Título da Decisão** | Experiência Unificada de Exploração, Camada Multi-Fonte de Dados, Central Status/Sync/Config e ShowCard Interativo |
| **Data de Início (Planejamento)** | 2026-11-17 |
| **Data de Conclusão (Auditoria)** | 2026-11-17 |
| **Taxa de Conclusão de Tarefas** | **100%** (18/18 tarefas concluídas) |
| **Branch Git** | `UI-UX` |
| **Commit SHA de Validação** | `9349c13` |
| **Gatekeeper Algorítmico** | `audit.py` (Janitor SOTA Engine) |
| **Status Final de Governança** | `CONSOLIDADA` ✅ |

---

## 2. Contexto Arquitetural & Decisão Implementada

### Diagnóstico e Motivação
Implementação governada dos requisitos estabelecidos na decisão arquitetural ADR-012.

### Solução Arquitetural Efetivada
Arquitetura prescrita em ADR-012 aplicada em conformidade com o Blueprint e Implementation Plan associados.

---

## 3. Matriz Completa de Tarefas Concluídas

Abaixo estão listadas todas as tarefas verificadas e atestadas no checklist de execução:

| ID | Descrição da Tarefa | Status de Execução | Validação |
|---|---|:---:|:---:|
| `T01` | **TODO-12.01 (`DEC-006`):** Executar Avaliação Heurística de Nielsen baseline documentada para os 3 cenários críticos (fluxo mobile `375px < 30s`, filtragem booleana/reset e previsibilidade de badges clicáveis). | ✅ Concluído | Aprovado no Gate |
| `T02` | **TODO-12.02 (`DEC-002`):** Implementar abstração polimórfica `ExternalSourceProvider` + registro de fontes (`eztv`, `yify`, `1337x`) e tabelas aditivas idempotentes (`external_sources`, `external_releases`) em `data/sources.db` preservando `EZTVShow`, `CatalogShow` e `CatalogRelease`. | ✅ Concluído | Aprovado no Gate |
| `T03` | **TODO-12.03 (`DEC-002`):** Criar endpoints multi-fonte `/api/sources/summary`, `/api/sources/releases`, `/api/sources/catalog` e `/api/sources/sync`, mantendo `/api/catalog/*` e `/api/torrents/*` compatíveis retroativamente (`INV-03`). | ✅ Concluído | Aprovado no Gate |
| `T04` | **TODO-12.04 (`DEC-003`):** Implementar `GET` e `PUT /api/explore/preferences` com persistência em `sync_state` (`data/mainstream.db`) e validação estrita via Pydantic (`schema_version: 1`, `badge_provider_action`, `badge_media_action`, `auto_apply_filters`, `show_all_genres`, `filter_panel_expanded`). | ✅ Concluído | Aprovado no Gate |
| `T05` | **TODO-12.05 (`DEC-001`):** Consolidar abas `Descobrir` e `Explorar Universo` na aba única `Explorar` em `App.tsx` e `Navbar.tsx` (4 abas principais: `Explorar`, `Fontes de Dados`, `Biblioteca`, `Coleções` + acesso à Central Status/Config). | ✅ Concluído | Aprovado no Gate |
| `T06` | **TODO-12.06 (`DEC-001`):** Implementar Modo Adaptativo em `ExplorerView.tsx`: exibir `HeroBanner` + Quick-Intent Bar + Roleta Contrastiva (3 títulos) + Carrosséis em estado ocioso, colapsando o Hero suavemente ao pesquisar ou aplicar filtros. | ✅ Concluído | Aprovado no Gate |
| `T07` | **TODO-12.07 (`DEC-005`):** Implementar motor híbrido de filtragem: accordion iniciando com `showAllGenres=false` (top-10 gêneros), `debounce (350ms)` + `AbortController` em `api.ts`, barra de progresso linear não-destrutiva preservando o grid atual e botão `"Aplicar Filtros"` (respeitando toggle `"Auto-aplicar"`). | ✅ Concluído | Aprovado no Gate |
| `T08` | **TODO-12.08 (`DEC-002`):** Refatorar `CatalogView.tsx` em `SourcesView` (`Fontes de Dados`) com filtros rápidos por indexador (`EZTV`, `YIFY/YTS`, `1337x`, etc.), telemetria de sincronização por provedor e busca paginada em `/api/sources/catalog`. | ✅ Concluído | Aprovado no Gate |
| `T09` | **TODO-12.09 (`DEC-003`):** Adicionar botão `44×44px` (ícone de engrenagem + indicador semântico `verde`/`âmbar`/`vermelho`) no topo direito da `Navbar.tsx` abrindo `StatusConfigView` com controles Dual-SSOT (`mainstream.db` + `sources.db`) e painel de preferências interativas. | ✅ Concluído | Aprovado no Gate |
| `T10` | **TODO-12.10 (`DEC-003`):** Implementar módulo `preferencesStorage.ts` com parsing defensivo de `localStorage`, defaults seguros (`RT-04`) e reconciliação assíncrona em background com `/api/explore/preferences`. | ✅ Concluído | Aprovado no Gate |
| `T11` | **TODO-12.11 (`DEC-002`):** Estender `/api/explore` e `/api/discovery` (via `EngineScopedCache`) para retornar disponibilidade agregada agnóstica (`has_media`, `media_sources`, `sources_count`) mantendo `has_eztv` e `eztv_id` por retrocompatibilidade. | ✅ Concluído | Aprovado no Gate |
| `T12` | **TODO-12.12 (`DEC-004`):** Refatorar `ShowCard.tsx` para empilhar **todos** os `ProviderBadge`s acima da `StatusBadge` no canto inferior esquerdo em cards `>= 190px` e aplicar salvaguarda responsiva `1 + N` em cards `< 190px` (`375px` mobile). | ✅ Concluído | Aprovado no Gate |
| `T13` | **TODO-12.13 (`DEC-002`, `DEC-004`):** Substituir `EztvBadge.tsx` por `MediaBadge.tsx` posicionada **abaixo** da nota IMDb no canto superior direito e evoluir `TorrentModal.tsx` para modal multi-fonte agrupado por provedor (magnets e links externos). | ✅ Concluído | Aprovado no Gate |
| `T14` | **TODO-12.14 (`DEC-004`):** Tornar `ProviderBadge` e `MediaBadge` botões clicáveis isolados (`e.stopPropagation()`, tooltip/`aria-label` dinâmicos conforme `DEC-003`), manter pôster clicável abrindo `ShowDetailModal` e substituir botões hover por botão expansível tátil `44×44px` (`Biblioteca`, `Fontes Media`, `Coleções`). | ✅ Concluído | Aprovado no Gate |
| `T15` | **TODO-12.15 (`DEC-006`):** Aplicar hardening WCAG 2.2 AA/AAA: `@media (prefers-reduced-motion: reduce)` em `index.css`, `<label>` explícito no campo de busca da `Navbar`, anéis `:focus-visible` uniformes, alvos `>= 44×44px` e contraste `>= 4.5:1`. | ✅ Concluído | Aprovado no Gate |
| `T16` | **TODO-12.16 (`DEC-002`, `DEC-003`, `DEC-004`):** Escrever testes automatizados `pytest` (novas rotas `/api/sources/*`, `/api/explore/preferences`, `has_media` agregado e retrocompatibilidade `/api/catalog/*` + `/api/torrents/*`). | ✅ Concluído | Aprovado no Gate |
| `T17` | **TODO-12.17 (`DEC-001`..`DEC-006`):** Executar suíte completa de validação (`make lint`, `make test`, `npx tsc --noEmit`, `make build-front`) e confirmar re-avaliação da Checklist Heurística de Nielsen + WCAG 2.2 sem regressões. | ✅ Concluído | Aprovado no Gate |
| `T18` | **TODO-12.18 (`DEC-001`..`DEC-006`):** Reconciliar documentação canônica (PT-BR) e executar `adr-archive` para emissão do `ADR-012-ER.md` após 100% de conclusão. | ✅ Concluído | Aprovado no Gate |

---

## 4. Verificação de Integridade e Validações Realizadas

| Dimensão de Validação | Método de Verificação | Veredito |
|---|---|:---:|
| **Conformidade de Escopo (DAG)** | Inspeção estrita contra TODO / PI | **PASSOU** ✅ |
| **Isolamento de Escopo** | Scope Isolation / Offloading para Registry | **PASSOU** ✅ |
| **Sincronização Documental** | Atualização de referências e status | **PASSOU** ✅ |
| **Rastreabilidade de Artefatos** | Decision Set completo (ADR, BP, TODO, PI) | **PASSOU** ✅ |

---

## 5. Gestão de Débitos Técnicos (Tech Debt Registry)

### Débitos Mitigados por esta ADR

- Nenhum débito pré-existente foi explicitamente vinculado a esta ADR.

### Débitos Incidentais Descarregados Durante a Execução

- Zero débitos secundários registrados durante o ciclo desta ADR.

---

## 6. Rastreabilidade e Arquivamento de Artefatos

Com a geração deste Evidence Record, os artefatos de trabalho da `ADR-012` foram promovidos e arquivados:

* **ADR Primária:** [`docs/adr/archive/ADR-012.md`](./archive/ADR-012.md)
* **Blueprint:** [`docs/adr/archive/ADR-012-BP.md`](./archive/ADR-012-BP.md)
* **Checklist TODO:** [`docs/adr/archive/ADR-012-TODO.md`](./archive/ADR-012-TODO.md)
* **Implementation Plan:** [`docs/adr/archive/ADR-012-PI.md`](./archive/ADR-012-PI.md)

---

## 7. Certificado Algorítmico de Fechamento

```text
[CERTIFICADO DE IMPLEMENTAÇÃO E GOVERNANÇA]
ADR: ADR-012
DATA: 2026-11-17
HASH DE VALIDAÇÃO: 8D6A3B43975FE30B
GATEKEEPER: adr-archive / audit.py v2.1.0
VEREDITO: DECISION SET CONSOLIDADO COM SUCESSO
```
