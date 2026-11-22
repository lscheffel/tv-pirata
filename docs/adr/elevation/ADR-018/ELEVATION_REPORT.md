---
adr_ref: ADR-018
elevation_version: "2.0.0"
blast_radius: 6.75
tier: "Standard (3.0 <= BR < 7.0)"
verdict: "KEEP + AMPLIFY"
updated: "2026-11-22"
---

# Relatório de Elevação Arquitetural — ADR-018

## 1. Modelo Independente do Problema & Blast Radius ($BR$)
- **$N_{\text{dependents}} = 3$** (`HydrationOrchestratorService`, `/api/explore`, `HydrationConsoleCard.tsx`)
- **$R_{\text{data}} = 1$** (extensão aditiva de `sync_state` + escrita em `data/mainstream.db`)
- **$H_{\text{rollback}} = 0.5$**
- **$BR = (3 \times 1.5) + (1 \times 2.0) + (0.5 \times 0.5) = 6.75$** (`Standard`)

## 2. Auditoria Forense & Desafios Adversariais

| ID | Severidade | Achado Adversarial | Amplificação Incorporada |
| :--- | :---: | :--- | :--- |
| `F-01` | **CRITICAL** | `IMDbCanonicalSyncService` (Bloco 2) escrevendo em `data/mainstream.db` concorrentemente com `HydrationOrchestratorService._worker_loop` causaria `database is locked` durante upsert TSV ou rebuild `shows_fts`. | **`AMP-01`:** Pausar cooperativamente o `HydrationOrchestratorService` durante as fases de escrita (`importing_*`, `rebuilding_fts`) e retomar automaticamente ao finalizar (se estava `RUNNING`), além de executar `IMDb` sync em thread isolada via `asyncio.to_thread`. |
| `F-02` | **MAJOR** | `COUNT(*)` repetido em `episodes_catalog` (`4.529.748` linhas) a cada ciclo do orquestrador desperdiça I/O sem necessidade, pois episódios só mudam no sync IMDb. | **`AMP-02`:** Consolidar métricas de `shows` (`tmdb_id`, `tvmaze_id`, `posters`, `synopsis`, `pending_details`) em **uma única query agregada `SUM(CASE ...)`**, e cachear `total_episodes` (atualizado no boot e ao fim de `IMDbCanonicalSyncService`). |
| `F-03` | **MAJOR** | Focar `TMDB` no modo `missing_synopsis_ptbr` sem cursor de progresso reprocessaria infinitamente as mesmas obras que não possuem sinopse PT-BR nas APIs. | **`AMP-03`:** Adicionar `ptbr_recheck_offset: int = 0` em `HydrationPipelineStatus` para avançar sequencialmente (`WHERE id > offset ORDER BY id`) e auto-limpar `target_provider = None` ao finalizar. |
| `F-04` | **MINOR** | Regra `consecutive_zero_recent_pages >= 2` poderia disparar `sweep` completo em modo `DELTA` quando não há lançamentos novos nas 2 primeiras páginas. | **`AMP-04`:** Restringir a transição automática `recent -> sweep` exclusivamente a `sc.mode == "BOOTSTRAP"`. |

## 3. Matriz Comparativa & Veredito

| Critério | Original (`ADR-018` v1) | Elevada (`KEEP + AMPLIFY`) |
| :--- | :---: | :---: |
| Corretude & Concorrência SQLite | 7/10 | **10/10** (`AMP-01` lock cooperativo) |
| Performance ($P_{95}$) | 8/10 | **10/10** (`AMP-02` query única + cache `episodes`) |
| Determinismo de Re-enriquecimento | 7/10 | **10/10** (`AMP-03` cursor `ptbr_recheck_offset`) |
| Segurança de Transição (`DELTA` vs `BOOTSTRAP`) | 8/10 | **10/10** (`AMP-04` guarda de modo) |

**Veredito Final:** **`KEEP + AMPLIFY` — Decision Set Certificado para Implementação.**
