# Phase 5: Registro de Amplificações (Hardening)

Com base nas conclusões da matriz comparativa e da auditoria forense, as seguintes amplificações são incorporadas à ADR-006:

1. **Amplificação 1 (Ingestão em Pipeline Desacoplado):**
   O indexador grava todas as releases da página consumida em lote com um único `commit` de banco, gerando a série bruta com o título deduzido via regex. O enriquecimento visual via TVMaze/TMDB opera de forma incremental e assíncrona, com cache local no SQLite para nunca reconsultar um `imdb_id` já enriquecido.

2. **Amplificação 2 (Classificação por Saúde P2P):**
   Adição de índices de ordenação `max_seeds` e `total_torrents` na tabela `CatalogShow`, assegurando que a ordenação padrão por "Mais Ativas / Mais Semeadas" responda instantaneamente com zero full-table scans.

3. **Amplificação 3 (CLI & Telemetria em Tempo Real):**
   O endpoint `POST /api/catalog/sync` e o comando `make sync-catalog pages=N` emitem telemetria detalhada de execução: quantidade de páginas lidas, novas releases inseridas, séries criadas e releases atualizadas.

