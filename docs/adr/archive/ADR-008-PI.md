# Plano de Implementação (PI): ADR-008 — Fundação do Audiovisual Discovery Core (Camada 1)

## 1. Faseamento de Execução Incremental

### Fase 1: Domínio Canônico Multi-Formato & Persistência Relacional (`T01`)
1. Criar `src/backend/models/catalog_domain.py` com todas as 10 entidades SQLModel da Camada 1.
2. Exportar em `src/backend/models/__init__.py` e garantir registro em `init_db()` (`src/backend/core/database.py`) sem afetar as tabelas existentes da Camada 2.

### Fase 2: Entity Resolution, Procedência & Federação (`T02`, `T03`)
1. Implementar `EntityResolutionService` (`src/backend/services/entity_resolution.py`) capaz de:
   - Resolver obras por IDs externos (`imdb`, `tmdb`, `tvmaze`, `wikidata`) com confiança `deterministic`;
   - Resolver obras por chave composta (`normalized_title`, `work_type`, `release_year`) com proteção explícita contra fusão destrutiva de remakes/homônimos;
   - Persistir entradas de `DataProvenance` sem sobrescrever silenciosamente metadados divergentes.
2. Implementar `FederatedCatalogService` (`src/backend/services/federated_catalog.py`):
   - Ingerir dataset curado multi-formato abrangendo Filmes (Sci-Fi, Suspense, Crime, Drama, Animação, Documentário, Clássicos e Estreias 2025/2026), Séries e Minisséries, com elenco, direção, franquias, disponibilidade em plataformas (`Netflix`, `Prime Video`, `Max`, `Apple TV+`, `Disney+`, `MUBI`) e eventos de calendário;
   - Sincronizar e enriquecer automaticamente registros preexistentes de `CatalogShow` e `ShowRecord` para dentro do catálogo canônico `MediaWork`;
   - Expor conectores federados complementares para busca/ingestão em TMDB (Filmes e TV) e TVMaze.

### Fase 3: Motor de Descoberta Avançada, Facetas, Relações & API REST (`T04`, `T05`)
1. Implementar `DiscoveryEngineRepository` (`src/backend/repositories/discovery_engine.py`):
   - Motor de filtragem booleana/relacional;
   - Cálculo de facetas dinâmicas sobre o conjunto filtrado;
   - Descoberta relacional por pessoa (filmografia completa + grafo de colaboradores frequentes + interseção de obras entre 2 pessoas);
   - Motor de similaridade objetiva (gêneros compartilhados, direção/elenco em comum, época, formato e afinidade temática).
2. Expor `/api/explore` em `src/backend/api/explore.py` e acoplar no `src/backend/main.py`.

### Fase 4: Testes Determinísticos & Frontend Cinematográfico (`T06`..`T10`)
1. Criar testes unitários e de integração herméticos (`test_entity_resolution.py`, `test_discovery_engine.py`, `test_explore_api.py`).
2. Construir `ExplorerView.tsx` no frontend React 19 permitindo alternar entre:
   - **Explorador Analítico & Facetado** (filtros AND/OR/NOT, streaming, ano, nota, duração, pessoa, não assistidos);
   - **Relações & Filmografias** (navegação por diretores, atores e colaborações);
   - **Agenda & Calendário de Estreias** (estreias de cinema, streaming, novas temporadas com grau de confiança);
   - **Dossiê Canônico da Obra** (procedência multi-fonte, onde assistir, elenco clicável, obras relacionadas/similares e ponte opcional para biblioteca/torrents).
3. Executar build Vite, linter Ruff e suíte Pytest completa.

---

## 2. Matriz de Verificação

| ID | Verificação | Método | Critério de Aceite |
| :--- | :--- | :--- | :--- |
| **V01** | Domínio Multi-Formato (`movie`, `tv_show`, `mini_series`, `documentary`, `animation`) | Unit Test | Persistência e consulta de filmes e séries sem dependência de temporadas ou torrents. |
| **V02** | Resolução de Identidade e Proteção de Remakes | Unit Test | Mesma obra de duas fontes funde em 1 `MediaWork` com 2 `DataProvenance`; remake de ano diferente gera 2 `MediaWork` distintos com `WorkRelation(remake)`. |
| **V03** | Advanced Filtering Engine (`AND`/`OR`/`NOT` + Streaming + Elenco + Não Assistidos) | Unit / Integration Test | Consultas compostas retornam resultados exatos e facetas contabilizadas corretamente. |
| **V04** | Relationship Discovery (Filmografia & Colaborações) | Integration Test | Consulta por diretor/ator retorna filmografia e obras em comum entre dois profissionais. |
| **V05** | Retrocompatibilidade Camada 2 | Pytest Suite | Todos os 47 testes preexistentes continuam passando sem modificações destrutivas. |

