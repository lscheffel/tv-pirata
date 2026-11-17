# ADR-011-TODO: Checklist de Execução — Consolidação Dual-SSOT (`mainstream.db` & `sources.db`)

- [x] **T1 — Migração Física Dual-SSOT sem Perda de Dados (`DEC-001`)**
  - [x] Consolidar `imdb_catalog.db` + tabelas pessoais/Camada 1 de `data/tv_pirata.db` em `data/mainstream.db` e `data/eztv_metadata.db` + `catalogshow`/`catalogrelease` em `data/sources.db` (com symlinks relativos `imdb_catalog.db -> data/mainstream.db` e `eztv_metadata.db -> data/sources.db`).
  - [x] Garantir colunas `tvmaze_id`, `status`, `air_day_time`, `streaming_providers`, `has_eztv`, `eztv_id`, `eztv_slug`, `eztv_match_type` e índices compostos covering (`idx_shows_filter_cover`, `idx_shows_score_cover`, `idx_shows_votes_rating`, `idx_shows_year_votes`, `idx_shows_type_votes`, `idx_shows_has_eztv`) em `data/mainstream.db.shows`.
- [x] **T2 — Atualização dos 4 Scripts CLI & Documentação (`DEC-003`, `DEC-005`)**
  - [x] Evoluir `scripts/sync-eztv-bade.py` para usar `data/mainstream.db` + `data/sources.db` e propagar `status`, `tvmaze_id`, `air_day_time` e `streaming_providers` além de `has_eztv`/`eztv_id`, executando o cruzamento real sobre os 279.117 títulos (`607` séries marcadas).
  - [x] Atualizar paths padrão em `scripts/imdb-metadata-catalog.py`, `scripts/eztv-metadata-catalog.py`, `scripts/sync_catalog.py` e `imdb-update-usage.md`.
- [x] **T3 — Camada de Persistência Dual-SSOT & Modelos SQLModel (`DEC-001`, `DEC-002`)**
  - [x] Adicionar `IMDbCatalogShow` e `IMDbEpisodeCatalog` isolados em `imdb_metadata` em `src/backend/models/catalog_domain.py`.
  - [x] Atualizar `src/backend/core/database.py` com `MAINSTREAM_DATABASE_URL` (`data/mainstream.db`), `SOURCES_DATABASE_URL` (`data/sources.db`), aliases retrocompatíveis e índices covering em `init_db()`.
  - [x] Atualizar `src/backend/api/torrents.py` e `src/backend/repositories/catalog.py` para priorizar `sources.db` com fallback defensivo.
- [x] **T4 — Motor SQL Pushdown para 279k+ Títulos (`DEC-004`)**
  - [x] Refatorar `DiscoveryEngineRepository` em `src/backend/repositories/discovery_engine.py` com motor SQL Pushdown sobre `IMDbCatalogShow` (`LIMIT`/`OFFSET`, filtros booleanos, `has_eztv`, busca, facetas cacheadas e dossiê completo com `episodes_catalog` sem full-table scan).
  - [x] Atualizar `src/backend/api/explore.py` para aceitar identificadores `ttXXXXXXX` e `imdb_num`.
- [x] **T5 — Testes Herméticos Dual-SSOT, Benchmark em 279k Títulos & Quality Gate**
  - [x] Criar `tests/integration/test_mainstream_sources_ssot.py` cobrindo queries SQL Pushdown, dossiê IMDb+TMDB+EZTV e `sources.db`.
  - [x] Executar `ruff check src/ tests/` (`All checks passed!`), `pytest -q` (`64 passed`), `make build-front` e benchmark empírico sobre os 279.117 títulos em `data/mainstream.db`.
