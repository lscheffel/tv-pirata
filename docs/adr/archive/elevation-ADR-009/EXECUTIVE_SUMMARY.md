# Executive Summary — Elevação Arquitetural ADR-009

- **Decisão:** Separação física entre `data/tv_pirata.db` (`get_session`) e `data/eztv_metadata.db` (`get_eztv_session`) com entrelaçamento $O(1)$ em `/api/explore/*` e fonte primária dedicada em `/api/catalog/*`.
- **Blast Radius ($BR$):** `6.25` (Standard Tier).
- **Veredito:** `KEEP + AMPLIFY` (0 achados críticos/maiores; pronto para implementação incremental).

