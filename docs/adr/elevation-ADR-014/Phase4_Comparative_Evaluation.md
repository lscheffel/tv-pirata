---
elevation_target: ADR-014
phase: 4
title: "Avaliação Comparativa, Cálculo de Blast Radius (BR) & Revisão Adversarial Red/Blue Team"
status: COMPLETED
language: PT-BR
---

# Fase 4 — Avaliação Comparativa & Blast Radius ($BR$)

## 1. Cálculo Determinístico de Blast Radius (`matrix_scorer.py`)

$$BR = (N_{\text{dependents}} \times 1.5) + (R_{\text{data}} \times 2.0) + (H_{\text{rollback}} \times 0.5) = (4 \times 1.5) + (1 \times 2.0) + (1.0 \times 0.5) = 8.5$$

**Saída verificada de `matrix_scorer.py`:**
```text
BR=8.5 | Category=CRITICAL | Gate=One-Way Door: Mandatory Multi-Agent Red Team / Blue Team adversarial review.
Sum weights: 1.0
Matrix: {'weighted_totals': {'Alt_A_Monolithic_Static_Sync': 5.51, 'Alt_B_Pure_Stateless_Live_Proxy': 6.84, 'Alt_C_Bipartite_Sovereign_SyncDeck': 9.47}, 'ranking': ['Alt_C_Bipartite_Sovereign_SyncDeck', 'Alt_B_Pure_Stateless_Live_Proxy', 'Alt_A_Monolithic_Static_Sync'], 'winner': 'Alt_C_Bipartite_Sovereign_SyncDeck', 'margin': 2.63}
```

## 2. Matriz Comparativa Ponderada (11 Critérios)

| Critério | Peso | `Alt A` (Monolítico) | `Alt B` (Stateless Proxy) | `Alt C` (Bipartido + Sync Deck) |
| :--- | :---: | :---: | :---: | :---: |
| **1. Fidelidade `sources-apis.md` (YTS `accel.li` + EZTV)** | 0.14 | 5.5 | 8.0 | **9.6** |
| **2. Sincronia Bipartida (Etapa 1 + Etapa 2 JIT)** | 0.14 | 4.5 | 5.0 | **9.5** |
| **3. Hidratação Soberana Camada 1 (`mainstream.db`)** | 0.12 | 5.0 | 6.5 | **9.5** |
| **4. Poda de Obsoletos / GC (`0 seeds`)** | 0.10 | 4.0 | 8.5 | **9.4** |
| **5. Resiliência SWR & `Replace-on-Success`** | 0.10 | 5.5 | 4.0 | **9.5** |
| **6. UX Sync Command Deck & Onda Card a Card** | 0.10 | 5.0 | 6.5 | **9.5** |
| **7. Cobertura `Torrent-Api-py` (12 Sites + `/recent`)** | 0.08 | 5.0 | 8.0 | **9.5** |
| **8. Roteamento por Formato (`movie` vs `tv_show`)** | 0.07 | 5.5 | 7.5 | **9.4** |
| **9. Testabilidade Hermética (`respx`)** | 0.05 | 8.0 | 7.0 | **9.5** |
| **10. Isolamento Dual-SSOT (`eztv_metadata`)** | 0.05 | 9.0 | 8.5 | **9.5** |
| **11. Reversibilidade** | 0.05 | 8.5 | 8.0 | **9.0** |
| **Total Ponderado (`matrix_scorer.py`)** | **1.00** | **5.51** | **6.84** | **9.47** |

## 3. Revisão Adversarial Red Team / Blue Team (`BR = 8.5` Gate)
- **`RT14-01` (Perda de Cache por Falha na Etapa 2):** Mitigado via transação `Replace-on-Success` condicional a `diag.status == "ok"`.
- **`RT14-02` (Latência N+1 no Join Entre Bancos):** Mitigado via Batch Lookup único `WHERE imdb_id IN (...)` por página (`<= 24` IDs).
- **`RT14-03` (Desperdício de Rede por Formato Incompatível):** Mitigado via filtro de `media_types` (`movie` pula `eztv`; `tv_show` pula `yify`).
- **`RT14-04` (Timeout em Onda quando Sidecar `:8009` está Offline):** Mitigado via cooldown compartilhado por host (`127.0.0.1:8009`) com *fast-skip* imediato (`0ms`) nos demais cards do sidecar.
