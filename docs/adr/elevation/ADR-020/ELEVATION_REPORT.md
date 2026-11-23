---
adr_ref: ADR-020
elevation_version: "2.0.0"
blast_radius: 6.75
tier: "Standard (3.0 <= BR < 7.0)"
verdict: "KEEP + AMPLIFY"
updated: "2026-11-22"
---

# Relatório de Elevação Arquitetural — ADR-020

## 1. Modelo Independente do Problema & Blast Radius ($BR$)
- **$N_{\text{dependents}} = 3$**, **$R_{\text{data}} = 1$**, **$H_{\text{rollback}} = 0.5$** -> **$BR = 6.75$** (`Standard`).

## 2. Auditoria & Amplificações Incorporadas

| ID | Severidade | Achado | Amplificação Incorporada |
| :--- | :---: | :--- | :--- |
| `F-01` | **CRITICAL** | `run_mode="novidades"` não pode mutar `recent_exhausted` nem ficar em loop esperando fontes em `BOOTSTRAP`. | **`AMP-01`:** `novidades` roda exatamente 1 ciclo com `start_page=1` e encerra como `COMPLETED`; `varredura` só processa fontes em `sweep_enabled_sources` com `not bootstrap_completed`. |
| `F-02` | **MAJOR** | Ampliar corte `sweep_min_votes` (ex.: `1000 -> 100`) não teria efeito se `bootstrap_completed=True` permanecesse travado. | **`AMP-02`:** `update_config` reabre `bootstrap_completed=False` quando `catalog_sweep_offset < new_sweep_total`, mantendo o offset já varrido. |
| `F-03` | **MAJOR** | `nyaasi` filtra `genres LIKE '%Animation%'`, então seu denominador real difere do catálogo geral. | **`AMP-03`:** Calcular `nyaasi_sweep_totals` e `vote_tier_counts` na query agregada única de `compute_coverage`. |
| `F-04` | **MINOR** | Reorganizar `HydrationConsoleCard` não deve quebrar a prop `compact` usada em `SourcesView`. | **`AMP-04`:** Preservar `compact` e persistir `advancedOpen` em `localStorage` (`tvp_hydration_advanced_v1`). |

**Veredito Final:** **`KEEP + AMPLIFY` — Certificado para Implementação Imediata.**
