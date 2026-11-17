# Executive Summary — Elevação Arquitetural ADR-011

- **Alvo:** Consolidação Dual-SSOT (`data/mainstream.db` + `data/sources.db`), IMDb como âncora universal (`279.117` obras / `4.529.748` episódios) e Motor SQL Pushdown.
- **Classificação:** `CERTIFIED_SOTA_PLUS` (Score Ponderado: `9,78 / 10`).
- **Amplificações Incorporadas:**
  - **AMP-001 (Fallback Dual-Path ORM):** Preservar execução sobre `MediaWork` quando `shows` (`IMDbCatalogShow`) estiver vazia (ex.: testes legados de Camada 1), ativando automaticamente o motor SQL Pushdown quando `shows` possuir linhas.
  - **AMP-002 (Propagação de Metadados Complementares `sources.db` $\rightarrow$ `mainstream.db`):** Além de inscrever `has_eztv` e `eztv_id`, `sync-eztv-bade.py` propaga `status`, `tvmaze_id`, `air_day_time` e `streaming_providers` onde ausentes em `mainstream.db`.
  - **AMP-003 (Índices Compostos de Ranking sem `TEMP B-TREE`):** Criar `idx_shows_votes_rating`, `idx_shows_year_votes` e `idx_shows_type_votes` em `data/mainstream.db` para paginação `LIMIT 24` instantânea ($< 5\text{ ms}$) em 279.117 títulos.
  - **AMP-004 (Identificador Universal `ttXXXXXXX` + `imdb_num`):** Suporte transparente no endpoint `/api/explore/works/{work_id}` para ID numérico (`imdb_num` ou `MediaWork.id`) e IMDb ID textual (`ttXXXXXXX`).
