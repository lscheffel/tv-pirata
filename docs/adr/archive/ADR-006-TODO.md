# TODO: ADR-006 — Catálogo Local EZTV e Motor de Ingestão P2P

- [x] `T01`: Modelar entidades relacionais `CatalogShow` e `CatalogRelease` em `src/backend/models/db.py`.
- [x] `T02`: Atualizar `init_db()` em `src/backend/core/database.py` garantindo migração e criação das tabelas no SQLite.
- [x] `T03`: Implementar método de busca por IMDB ID (`lookup_by_imdb`) no `TVMazeProvider` e `TMDBProvider`.
- [x] `T04`: Implementar `EZTVIndexerService` em `src/backend/services/catalog_indexer.py` para ingestão paginada e upsert atômico de releases.
- [x] `T05`: Implementar heurística de extração de nome de série e enriquecimento automático via IMDB ID.
- [x] `T06`: Implementar repositório `CatalogRepository` em `src/backend/repositories/catalog.py` com queries otimizadas por seeds, data e texto.
- [x] `T07`: Criar roteador REST `/api/catalog` em `src/backend/api/catalog.py` com endpoints `shows`, `shows/{imdb_id}`, `stats` e `sync`.
- [x] `T08`: Registrar roteador no `main.py` e adicionar endpoints de documentação Swagger.
- [x] `T09`: Adicionar target `make sync-catalog` no `Makefile` e script CLI para execução manual.
- [x] `T10`: Atualizar frontend com visualização do Catálogo EZTV e estatísticas do acervo local.
- [x] `T11`: Escrever suíte de testes unitários e de integração para o indexador e rotas de catálogo.
- [x] `T12`: Validar suíte completa com `make test` e `make lint` aprovados sem advertências.
