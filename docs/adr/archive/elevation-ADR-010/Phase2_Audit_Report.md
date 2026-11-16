# Fase 2: Relatório de Auditoria Forense da Quadra ADR-010

## 1. Verificação de Rastreabilidade e Cobertura

| Critério | Avaliação | Evidência |
| :--- | :---: | :--- |
| Cobertura integral dos 5 pontos levantados pelo usuário | **PASS** | `DEC-001` (PRAGMAs), `DEC-002` (Materialização `episodes_catalog`), `DEC-003`/`DEC-004` (`get_curated_sections` + cache), `DEC-005` (`_ensure_seeded` + `discovery_engine`), `DEC-006` (`FTS5`). |
| Baseline empírico documentado com métricas reais | **PASS** | `list_shows: 965,61 ms`, `sections: 692,07 ms`, `explore_works: 160,87 ms`, `stats: 38,34 ms`, `genres: 8,87 ms`. |
| Alinhamento com `AGENTS.md` (Invariante Anti-Stub e Dual-DB) | **PASS** | Implementação física real com triggers SQLite e cache nativo thread-safe. |

## 2. Riscos Técnicos Identificados na Auditoria Adversarial

1. **Risco A1 — Invalidação de Cache quando Testes Inserem Diretamente via ORM (`session.add`):**
   - Em `tests/integration/test_catalog_api.py`, um mesmo teste ou fixture pode consultar um endpoint, inserir uma série ou episódio na sessão e consultar novamente usando o **mesmo** `Engine` in-memory. Se a chave do cache usar apenas `id(engine)` e TTL temporal, a segunda leitura veria um snapshot obsoleto.
   - **Mitigação Exigida:** Incluir um *lightweight table version fingerprint* (`(count_shows, max_updated_at, count_episodes)` em `< 0,2 ms`) na chave do cache de `CatalogRepository` e `(count_media_works, count_eztv_shows, count_catalog_shows)` em `DiscoveryEngineRepository`.
2. **Risco A2 — Compatibilidade de `PRAGMA journal_mode=WAL` e `mmap_size` em Bancos `:memory:`:**
   - Em bancos `:memory:` (usados pelo `pytest`), `PRAGMA journal_mode=WAL` retorna `memory` (inócuo), mas deve ser tratado dentro de bloco `try/except` seguro no event listener do SQLAlchemy.
3. **Risco A3 — Escape de Caracteres Especiais na Query `FTS5 MATCH`:**
   - Pesquisas do usuário contendo caracteres como `-`, `:`, `"`, `*` ou `'` (ex.: `"Spider-Man: No Way"`, `"9-1-1"`, `"What's"`) causam `OperationalError: fts5: syntax error` se passadas cruas para `MATCH`.
   - **Mitigação Exigida:** Sanitizar o termo FTS5 extraindo tokens alfanuméricos (`re.findall(r"\w+", q)`) formatados como `"token"*` e manter fallback transparente para `ILIKE`.
