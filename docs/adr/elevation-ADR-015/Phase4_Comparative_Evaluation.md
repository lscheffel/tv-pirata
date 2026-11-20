---
elevation_target: ADR-015
phase: 4
title: "Avaliação Comparativa, Cálculo de Blast Radius (BR) & Revisão Adversarial Red/Blue Team"
status: COMPLETED
language: PT-BR
---

# Fase 4 — Avaliação Comparativa & Blast Radius ($BR$)

## 1. Cálculo Determinístico de Blast Radius (`matrix_scorer.py`)

$$BR = (4 \times 1.5) + (1 \times 2.0) + (1.0 \times 0.5) = 8.5 \quad (\text{CRITICAL})$$

```text
BR=8.5 | Category=CRITICAL | Gate=One-Way Door: Mandatory Multi-Agent Red Team / Blue Team adversarial review.
Sum weights: 1.0
Matrix: {'weighted_totals': {'Alt_A_Disconnected_CLI_Scripts': 4.95, 'Alt_B_Eager_Full_Payload_Monolith': 6.0, 'Alt_C_Unified_3Pillar_Resumable_Waterfall': 9.51}, 'ranking': ['Alt_C_Unified_3Pillar_Resumable_Waterfall', 'Alt_B_Eager_Full_Payload_Monolith', 'Alt_A_Disconnected_CLI_Scripts'], 'winner': 'Alt_C_Unified_3Pillar_Resumable_Waterfall', 'margin': 3.51}
```

## 2. Revisão Adversarial Red Team / Blue Team (`BR = 8.5` Gate)
- **`RT15-01` (Contenção de Lock SQLite durante Hidratação Contínua):** Mitigado via lotes curtos (`<= 50` itens por transação) com `await asyncio.sleep()` entre lotes sob `PRAGMA journal_mode=WAL`.
- **`RT15-02` (Sobrescrita Indevida de Metadados de Maior Prioridade):** Mitigado pela regra de **Preenchimento Hierárquico Não-Destrutivo (`COALESCE`)** na ordem estrita `IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes`, onde cada degrau só preenche os atributos que ainda estiverem vazios (`poster_url`, `synopsis_ptbr`, `synopsis`, `trailer_url`, `streaming_providers`).
- **`RT15-03` (Rate-Limit / 429 em Fontes Abertas):** Mitigado por Batch SPARQL (`40` IDs por request na Wikidata), timeout rígido por degrau (`4.0s`) e fallback transparente para o próximo degrau.
