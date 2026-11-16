# Phase 4: Comparative Evaluation Matrix — ADR-009

**Blast Radius ($BR$):**
$$BR = (4 \times 1.5) + (0 \times 2.0) + (0.5 \times 0.5) = 6.25 \quad (\text{Standard Tier})$$

| Critério | Alt A (Dual Session) | Alt B (`ATTACH`) | Alt C (ETL Cópia) |
| :--- | :---: | :---: | :---: |
| Correctness & Isolation | **9.5** | 6.5 | 7.0 |
| Testability (`pytest`) | **9.5** | 5.0 | 8.0 |
| Performance ($P_{95}$) | **9.0** | 8.5 | 8.5 |
| Complexity | **8.5** | 7.0 | 5.5 |
| Reversibility | **9.5** | 7.5 | 5.0 |
| **Score Ponderado** | **9.2** | **6.9** | **6.8** |

