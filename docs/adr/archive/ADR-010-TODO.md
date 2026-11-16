# ADR-010-TODO: Checklist de Execução — Otimização Dual-SQLite, Estatísticas Materializadas, Cache Escopado e FTS5

- [x] **T1 — Tuning de Conexão SQLite (`PRAGMA`s) e Migração Materializada + FTS5 (`DEC-001`, `DEC-002`, `DEC-006`)**
  - [x] Registrar `@event.listens_for(Engine, "connect")` em `src/backend/core/database.py` aplicando `journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-64000`, `mmap_size=268435456` e `busy_timeout=5000`.
  - [x] Adicionar `episodes_count`, `max_season` e `max_episode` ao modelo `EZTVShow` em `src/backend/models/eztv_db.py`.
  - [x] Atualizar `init_eztv_db()` em `src/backend/core/database.py` para adicionar as colunas `episodes_count`, `max_season`, `max_episode`, criar índices compostos B-Tree (`idx_episodes_show_season_ep`, `idx_shows_rating_id`), executar backfill idempotente a partir de `episodes_catalog` e criar/sincronizar a tabela virtual `shows_fts` (`FTS5`) com triggers `AFTER INSERT/UPDATE/DELETE`.

- [x] **T2 — Motor de Cache em Memória Escopado por `Engine` + Fingerprint (`DEC-003`)**
  - [x] Criar `src/backend/core/cache.py` implementando `EngineScopedCache` (`catalog_cache`, `discovery_cache`) thread-safe com escopo `(id(engine), ...)` e invalidação explícita.

- [x] **T3 — Otimização de `CatalogRepository` (`DEC-002`, `DEC-003`, `DEC-004`, `DEC-006`)**
  - [x] Eliminar a chamada a `_build_episode_stats_map` sobre todos os `all_ids` antes da paginação em `CatalogRepository.list_shows`; usar diretamente `show.episodes_count`, `show.max_season` e `show.max_episode` (com fallback apenas para itens com `episodes_count == 0`).
  - [x] Integrar busca acelerada via `shows_fts MATCH` em `CatalogRepository.list_shows` quando `search` for informado, com fallback seguro para substring.
  - [x] Refatorar `CatalogRepository.get_curated_sections` para pipeline single-pass em memória + cache escopado com fingerprint `(count_shows, max_updated_at, sum_episodes)`.
  - [x] Otimizar `CatalogRepository.get_genres_with_counts` e `CatalogRepository.get_stats` utilizando as colunas materializadas e cache escopado com fingerprint.
  - [x] Invalidar `catalog_cache` e `discovery_cache` nas rotas de mutação de `src/backend/api/catalog.py` (`/sync`, `/enrich-pending`).

- [x] **T4 — Remoção de `_ensure_seeded` do Caminho Quente e Otimização de `DiscoveryEngineRepository` (`DEC-003`, `DEC-005`)**
  - [x] Proteger `ensure_federated_catalog_seeded` em `src/backend/services/federated_catalog.py` com guarda em memória `_SEEDED_ENGINES: set[int]` por `id(session.get_bind())` e chamá-la no `lifespan` de `src/backend/main.py`.
  - [x] Refatorar `DiscoveryEngineRepository` em `src/backend/repositories/discovery_engine.py` para cachear o snapshot base de obras desacopladas (`MediaWork.model_validate`), créditos, disponibilidade, gêneros normalizados, blobs textuais e `build_eztv_lookup_index`, além de eliminar N+1 queries em `compute_similar_works`.

- [x] **T5 — Sincronização de Estatísticas Materializadas no Script CLI (`DEC-002`, `DEC-006`)**
  - [x] Atualizar `scripts/eztv-metadata-catalog.py` para criar as colunas `episodes_count`, `max_season`, `max_episode` e recalculá-las automaticamente após gravação de episódios.

- [x] **T6 — Testes Automatizados de Performance, FTS5 e Isolamento de Cache**
  - [x] Adicionar testes em `tests/unit/test_db_performance.py` validando `PRAGMA`s SQLite, estatísticas materializadas em `shows`, busca via `FTS5`, invalidação automática por fingerprint e guarda `_SEEDED_ENGINES`.

- [x] **T7 — Verificação de Qualidade e Reconciliação Documental (`AGENTS.md`, `ADR-INDEX.md`)**
  - [x] Executar `ruff check src/ tests/`, `pytest -q` e benchmark comparativo final comprovando a redução de latência.
