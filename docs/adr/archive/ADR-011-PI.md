# ADR-011-PI: Plano de Implementação — Consolidação Dual-SSOT e Motor SQL Pushdown

1. **Fase 1:** Governança `ADR-011` + Elevação Arquitetural (`docs/adr/elevation-ADR-011/`).
2. **Fase 2:** Migração física atômica (`imdb_catalog.db` + `data/tv_pirata.db` $\rightarrow$ `data/mainstream.db`; `data/eztv_metadata.db` + P2P $\rightarrow$ `data/sources.db`), criação de índices compostos B-Tree e execução de `scripts/sync-eztv-bade.py`.
3. **Fase 3:** Modelos `IMDbCatalogShow`/`IMDbEpisodeCatalog`, atualização de `src/backend/core/database.py` e scripts CLI.
4. **Fase 4:** Reescrita SQL Pushdown em `DiscoveryEngineRepository` (`query_works`, `get_work_dossier`, `compute_similar_works`, `get_rankings_perspectives`) para 279k+ obras ($P_{95} < 25\text{ ms}$).
5. **Fase 5:** Testes integrados Dual-SSOT (`test_mainstream_sources_ssot.py`), `ruff`, `pytest` (63+ testes), `make build-front` e benchmark empírico final.
