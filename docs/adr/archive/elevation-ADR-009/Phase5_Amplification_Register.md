# Phase 5: Amplification Register — ADR-009

1. **AMP-01 (Completeness — Metadata Isolation):** Usar `MetaData()` dedicado ou acesso SQL/SQLModel isolado para `EZTVShow`/`EZTVEpisodeCatalog`, impedindo que `SQLModel.metadata.create_all(tv_pirata_engine)` crie `shows` dentro de `tv_pirata.db`.
2. **AMP-02 (Robustness — Schema Bootstrap Idempotente):** `init_eztv_db()` executa `CREATE TABLE IF NOT EXISTS shows (...)` e `episodes_catalog (...)` para evitar falhas em ambientes sem `data/eztv_metadata.db` pré-populado.
3. **AMP-03 (Performance — Índice $O(1)$ sem N+1):** `DiscoveryEngineRepository` carrega apenas `(id, imdb_id, slug, name)` de `eztv_metadata.db` uma única vez por requisição em `build_eztv_lookup_index(eztv_session)`.
4. **AMP-04 (Compatibility — Telemetria P2P Híbrida):** `/api/catalog/shows` usa `eztv_metadata.db` como fonte primária e mescla `total_torrents`/`max_seeds` de `CatalogShow` (`tv_pirata.db`) por `imdb_id` quando presentes.

