# Phase 1: Modelo Independente do Problema — Catálogo Local EZTV e Motor P2P

## 1. Declaração Fundamental do Problema
O TV Pirata atua como central de descoberta e controle para consumo de mídia em homelab, mas sua camada de descoberta inicial sofre de uma desconexão material em relação à disponibilidade física da rede de distribuição. O usuário é apresentado a títulos abstratos via TMDB/TVMaze cuja disponibilidade de sementes (seeders) e releases no tracker EZTV é incerta ou inexistente no momento da busca.
Para eliminar essa assimetria, o sistema deve indexar, normalizar e persistir localmente o acervo da EZTV (mais de 1.1 milhão de torrents), associando os releases a seus respectivos identificadores canônicos (`imdb_id`) e enriquecendo-os com metadados visuais de alta fidelidade sem incorrer em rate-limiting abusivo ou degradação de performance.

## 2. Metas & Critérios de Sucesso
- **Meta 1 (Garantia de Mídia):** Cada título retornado pelo catálogo local do TV Pirata deve possuir pelo menos 1 release com link magnet e seeders válidos.
- **Meta 2 (Latência Sub-Milissegundo):** Consultas de busca, paginação e ordenação no acervo local devem responder em $<10\text{ms}$ no SQLite local.
- **Meta 3 (Resiliência a Falhas de Rede Externa):** A navegação no catálogo local deve operar de forma 100% autônoma e offline após a ingestão.

## 3. Invariantes & Restrições Inegociáveis
- **Invariante 1 (Chave Universal Canônica):** A relação entre o torrent EZTV e os metadados de catálogo deve ser rigidamente ancorada no `imdb_id` normalizado (prefixo `tt` seguido de dígitos), garantindo idempotência e integridade referencial.
- **Invariante 2 (Blindagem contra Rate-Limit):** O crawler de ingestão deve respeitar intervalos mínimos entre requisições e isolar falhas de páginas individuais sem interromper a transação global.
- **Invariante 3 (Deduplicação de Releases):** Releases duplicadas com mesmo hash ou id EZTV devem sofrer upsert idempotente, atualizando exclusivamente as contagens de `seeds` e `peers`.

