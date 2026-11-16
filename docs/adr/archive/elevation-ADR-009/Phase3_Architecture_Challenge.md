# Phase 3: Architecture Challenge — ADR-009

- **Alt A (Original — Dual Engine/Session + Índice em Memória):** `DATABASE_URL` (`tv_pirata.db`) e `EZTV_DATABASE_URL` (`eztv_metadata.db`) independentes, com cruzamento $O(1)$ em memória por requisição.
- **Alt B (SQLite `ATTACH DATABASE`):** Acopla ao dialeto SQLite, dificulta `sqlite:///:memory:` isolado em testes unitários/integração.
- **Alt C (ETL periódico `eztv_metadata.db` -> `tv_pirata.db`):** Duplica 140k+ episódios e cria janela de inconsistência entre extração e exibição.

