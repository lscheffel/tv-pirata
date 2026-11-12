# Phase 4 — Comparative Evaluation Matrix: ADR-007

## 1. Canonical 11-Dimension Weighted Evaluation Matrix

As alternativas formuladas na Fase 3 foram submetidas à matriz algorítmica de decisão ponderada:

| Critério Canônico | Peso | Alt A (In-Process asyncio) | Alt B (Thread Dedicada) | Alt C (OS Crontab/Timer) | Alt D (Celery/Redis) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **1. Correção & Invariantes** | 1.2 | 9.0 (10.8) | 8.0 (9.6) | 8.5 (10.2) | 9.5 (11.4) |
| **2. Complexidade Código/Ops** | 1.1 | 9.5 (10.45) | 6.5 (7.15) | 6.0 (6.6) | 3.0 (3.3) |
| **3. Robustez & Tolerância a Falhas** | 1.1 | 8.5 (9.35) | 7.5 (8.25) | 9.0 (9.9) | 9.0 (9.9) |
| **4. Testabilidade & Determinismo** | 1.0 | 9.5 (9.5) | 7.0 (7.0) | 6.5 (6.5) | 7.5 (7.5) |
| **5. Operabilidade & Observabilidade** | 0.9 | 8.5 (7.65) | 7.5 (6.75) | 6.0 (5.4) | 9.5 (8.55) |
| **6. Performance & Latência** | 0.9 | 9.0 (8.1) | 9.0 (8.1) | 8.0 (7.2) | 8.5 (7.65) |
| **7. Segurança & Blast Radius** | 0.8 | 9.0 (7.2) | 8.5 (6.8) | 9.0 (7.2) | 7.0 (5.6) |
| **8. Manutenibilidade do Código** | 1.0 | 9.0 (9.0) | 7.0 (7.0) | 7.0 (7.0) | 5.0 (5.0) |
| **9. Custo de Execução / Footprint** | 1.0 | 10.0 (10.0) | 8.5 (8.5) | 9.5 (9.5) | 3.0 (3.0) |
| **10. Reversibilidade da Decisão** | 0.9 | 9.5 (8.55) | 8.0 (7.2) | 7.5 (6.75) | 4.0 (3.6) |
| **11. Escalabilidade Proporcional** | 0.7 | 8.0 (5.6) | 8.5 (5.95) | 7.5 (5.25) | 10.0 (7.0) |
| **PONTUAÇÃO FINAL PONDERADA** | **10.6** | **94.2** | **79.3** | **81.5** | **72.5** |

---

## 2. Análise Comparativa Forense

* **Alt A (Vencedora Inconteste - 94.2 pts):** Apresenta o equilíbrio ideal entre simplicidade extrema, custo zero de infraestrutura e perfeita integração com o ecossistema assíncrono do FastAPI. A facilidade de simular tempo nos testes com mocks de `asyncio.sleep` torna a testabilidade superior a qualquer outra opção.
* **Alt B (79.3 pts):** Penalizada por risco de conflitos de concorrência com threads do SQLite e maior complexidade de sincronização e cancelamento gracioso.
* **Alt C (81.5 pts):** Excelente em isolamento, mas inviabiliza portabilidade transparente entre ambientes de desenvolvimento e sistemas operacionais diferentes sem scripts de instalação privilegiados.
* **Alt D (72.5 pts):** Overkill arquitetural flagrante para uma aplicação local mono-usuário.

