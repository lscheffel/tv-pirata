---
adr_ref: ADR-017
phase: 4
title: "Phase 4 — Comparative Evaluation Matrix"
language: PT-BR
---

# Phase 4: Matriz Comparativa (`matrix_scorer.py`)

- **Blast Radius ($BR$):** `7.75` (`CRITICAL` — `N_dependents=5`, `R_data=0`, `H_rollback=0.5`).
- **Resultados Ponderados (`matrix_scorer.py`):**
  1. **`Alt_B_Bifurcated_FanOut_DomainSem_FanIn`:** **`9.21`** *(Vencedora, margem `+2.45`)*
  2. `Alt_A_Sequential_Plus_MaxPageBump`: `6.76`
  3. `Alt_C_MultiProcess_WorkerPool_SQLiteLocks`: `6.15`
