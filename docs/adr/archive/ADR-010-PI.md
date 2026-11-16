# ADR-010-PI: Plano de Implementação — Otimização Dual-SQLite, Estatísticas Materializadas, Cache Escopado e FTS5

## Visão Geral e Estratégia de Execução

A implementação do **ADR-010** segue uma sequência de 5 fases orientadas por testes (TDD), eliminando progressivamente os gargalos de I/O e CPU diagnosticados em `data/tv_pirata.db` e `data/eztv_metadata.db` sem alterar os contratos externos de API consumidos pela SPA React 19.

---

## Fase 1: Camada de Persistência Dual-SQLite (`PRAGMA`s, Colunas Materializadas e FTS5)
- **Objetivo:** Configurar `WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-64000` e `mmap_size=268435456` em todas as conexões SQLite (`DEC-001`), materializar `episodes_count`, `max_season` e `max_episode` em `shows` (`DEC-002`) e criar o índice virtual `shows_fts` (`DEC-006`).
- **Arquivos Afetados:**
  - `src/backend/models/eztv_db.py`
  - `src/backend/core/database.py`
- **Critério de Aceite:** `init_eztv_db()` popula `episodes_count`, `max_season`, `max_episode` para as 860 séries de `data/eztv_metadata.db` e cria `shows_fts` com triggers de sincronização automática.

---

## Fase 2: Motor de Cache Escopado por `Engine` e Otimização de `CatalogRepository`
- **Objetivo:** Eliminar o `GROUP BY` pré-paginação sobre `140.571` linhas de `episodes_catalog`, substituir as 7 chamadas sequenciais de `get_curated_sections` por um pipeline single-pass + cache escopado com fingerprint (`DEC-003`, `DEC-004`) e ativar busca via `shows_fts MATCH` (`DEC-006`).
- **Arquivos Afetados:**
  - `src/backend/core/cache.py`
  - `src/backend/repositories/catalog.py`
  - `src/backend/api/catalog.py`
- **Critério de Aceite:**
  - `CatalogRepository.list_shows(sort_by='seeds', page=1, page_size=20)` executa em $< 10\text{ ms}$ (contra `965,61 ms` no baseline).
  - `CatalogRepository.get_curated_sections(limit=20)` executa em $< 12\text{ ms}$ a frio e $< 1\text{ ms}$ a quente (contra `692,07 ms` no baseline).

---

## Fase 3: Guarda O(1) de `_ensure_seeded` e Snapshot no `DiscoveryEngineRepository`
- **Objetivo:** Remover `SELECT COUNT(mediawork.id)` do caminho quente de `/api/explore/*` via guarda `_SEEDED_ENGINES` por `id(engine)` (`DEC-005`) e cachear o grafo base de descoberta + `_build_eztv_lookup` com fingerprint de contagem (`DEC-003`, `DEC-005`).
- **Arquivos Afetados:**
  - `src/backend/services/federated_catalog.py`
  - `src/backend/main.py`
  - `src/backend/repositories/discovery_engine.py`
  - `src/backend/api/explore.py`
- **Critério de Aceite:** `DiscoveryEngineRepository.query_works(page=1, page_size=24)` executa em $< 20\text{ ms}$ a frio e $< 3\text{ ms}$ a quente (contra `160,87 ms` no baseline), mantendo `in_library` e `exclude_watched` 100% reativos em tempo real.

---

## Fase 4: Alinhamento do Pipeline CLI (`scripts/eztv-metadata-catalog.py`)
- **Objetivo:** Garantir que futuras execuções do script de coleta/enriquecimento mantenham `episodes_count`, `max_season`, `max_episode` e `shows_fts` sincronizados em `data/eztv_metadata.db`.
- **Arquivos Afetados:**
  - `scripts/eztv-metadata-catalog.py`
- **Critério de Aceite:** O script CLI atualiza as colunas materializadas e o índice `shows_fts` ao final de cada execução.

---

## Fase 5: Testes Automatizados de Performance e Benchmark Comparativo Final
- **Objetivo:** Validar hermeticamente `PRAGMA`s, estatísticas materializadas, `FTS5`, invalidação por fingerprint e SLAs de latência via `pytest`.
- **Arquivos Afetados:**
  - `tests/unit/test_db_performance.py`
  - `tests/integration/test_catalog_api.py`
  - `docs/adr/ADR-INDEX.md`
- **Critério de Aceite:** 100% dos testes passando (`pytest`), zero avisos no `ruff check` e comprovação empírica de ganho $> 95\%$ nas operações críticas.
