# Design Doc — ADR-015: Motor Unificado dos 3 Pilares de Hidratação com Checkpoints (`--resume`), Gatilho Inteligente de Maturidade (`Bootstrap` $\leftrightarrow$ `Delta`) e Cascata Hierárquica de 6 Degraus (`IMDb` $\rightarrow$ `TMDB` $\rightarrow$ `TVMaze` $\rightarrow$ `EZTV` $\rightarrow$ `YIFY` $\rightarrow$ `Outras Fontes`)

- **Data:** 2026-11-19
- **Status:** Validated & Approved (`Garimpo R1: 1B 2C 3A 4D 5B 6A 7C 8B 9C 10D` | `R2: 1A 2B 3C 4A 5B 6C 7D 8B 9A 10C` | `R3: schema v1`)
- **Target ADR:** `ADR-015` (`DCI = 8`, `Tier 2 — Quadra SOTA`, `BR = 8.5 CRITICAL`)

---

## 1. Visão Geral: Os 3 Pilares de Hidratação e o Gatilho Inteligente de Maturidade

O ciclo de vida de dados do **TV Pirata** passa a ser governado por um único orquestrador resumível (`HydrationOrchestratorService`) que opera sobre **3 Pilares**:

1. **Pilar 1 — População Estrutural Completa dos Catálogos (`Baseline c/ Resume` $\rightarrow$ `Auto-Delta Incremental + Poda`):**
   - **Gatilho Inteligente de Maturidade (`SmartBootstrapDetector`):**
     - **Instalação Limpa (Zero-State Distribution):** Se `data/mainstream.db` (`< 10.000` obras) ou uma fonte de `data/sources.db` ainda não completou sua carga estrutural, inicia automaticamente em **`MODO BOOTSTRAP RESUMÍVEL`**.
     - **Base Aquecida (Warm Database):** Quando uma camada/fonte atinge seu limiar estrutural (`mainstream.db >= 250.000` obras; `eztv >= 800` séries; ou `bootstrap_completed = True` no cursor da fonte), o motor chaveia automaticamente aquela fonte para **`MODO DELTA INCREMENTAL + PODA`**, concentrando o Bootstrap apenas nas fontes que ainda estão avançando seu cursor histórico (`YIFY / YTS` rumo aos `78.565` filmes e `Sidecar :8009` `tgx`, `nyaasi`, `bitsearch`, `glodls`).
   - **Cursores Persistentes & Presença Compacta (`Batch UPSERT`):**
     - `YIFY / YTS`: avança `next_page` (`1..1572`) em `https://movies-api.accel.li/api/v2/list_movies.json`, gravando 1 registro compacto de presença por `(source_key, imdb_id)` com qualidades agregadas (`"2160p,1080p"`) e `max_seeds`.
     - `Sidecar :8009` (`tgx`, `nyaasi`, `bitsearch`, `glodls`): combina varredura multi-página/multi-categoria (`Multi-Page Feed Crawl`) + varredura guiada pelas obras mais populares de `mainstream.db` (`Canonical Catalog Anchor Sweep` com cursor `catalog_sweep_offset`).

2. **Pilar 2 — Hidratação Semi-Efêmera Sob Demanda (`Just-in-Time` no Clique / `TorrentModal.tsx` e `Minha Biblioteca`):**
   - Não armazena milhões de magnet links estáticos durante o Pilar 1. No ato do clique no título (`ttXXXXXXX`), consulta ao vivo as fontes compatíveis, hidrata todos os torrents, magnets com os 10 trackers oficiais, seeds e peers (`Replace-on-Success`) e exibe a faixa de Inteligência YTS.

3. **Pilar 3 — Enriquecimento Canônico em Cascata Hierárquica de 6 Degraus (`Capas` + `Sinopses PT-BR e EN-US`):**
   - Opera sobre uma **Fila Bipartida Prioritária** (1º `Minha Biblioteca` e `75` séries órfãs da EZTV; 2º Obras com Mídia em `sources.db`; 3º Sub-Fila `Sem Capa` [`23.602` obras] e Sub-Fila `Sem Sinopse PT-BR/EN` [`188.311` obras] ordenadas por `rating_votes DESC`).
   - Consulta os provedores na seguinte **ordem hierárquica estrita de prioridade**:
     1. **`IMDb`** (`imdb.com/title/tt...` JSON-LD `<script type="application/ld+json">` & `og:image` + Backbone canônico);
     2. **`TMDB`** (`/find/{imdb_id}` + `pt-BR` + `en-US` + `watch/providers`);
     3. **`TVMaze`** (`/lookup/shows?imdb={imdb_id}`);
     4. **`EZTV`** (`Cross-DB Self-Healing` bidirecional entre `EZTVShow` em `sources.db` e `IMDbCatalogShow` em `mainstream.db`);
     5. **`YIFY / YTS`** (`movies-api.accel.li/api/v2/movie_details.json?imdb_id=tt...`);
     6. **`Outras Fontes Abertas`** (`Wikidata Batch SPARQL P345 + Wikipédia PT-BR / EN-US REST Summary` + `Jikan v4 / MyAnimeList`).
