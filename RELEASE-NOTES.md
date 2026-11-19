# Release Notes — TV Pirata 🏴‍☠️

Este documento consolida os marcos de valor de negócio, evolução arquitetural, métricas de verificação e guias de atualização para cada versão lançada do **TV Pirata**.

---

## 🚀 Alinhamento `sources-apis.md`, Curadoria `Torrent-Api-py` (12 Sites), Sincronia Bipartida em 2 Etapas & Sync Command Deck — ADR-014 (Branch `UI-UX`, 2026-11-19)

### 🌟 Destaques Executivos e Evolução Arquitetural (`ADR-014`)
1. **Especificações Oficiais YTS v2 (`movies-api.accel.li`) & EZTV (`eztvx.to`) (`DEC-001`, `DEC-002`):**
   - `YIFYSourceAdapter` migrado com migração idempotente para `https://movies-api.accel.li/api/v2/` consumindo os 4 endpoints oficiais (`list_movies.json`, `movie_details.json`, `movie_suggestions.json`, `movie_parental_guides.json`) e montando magnet links URL-safe (`quote_plus(dn)`) com os **10 trackers oficiais** (`build_official_magnet`).
   - `EZTVSourceAdapter` e `EZTVProvider` padronizados com `?imdb_id=<num_sem_tt>` e `limit=100`, parser RSS oficial (`https://myrss.org/eztv`) e diagnóstico `https://eztvstatus.org/`.
2. **Catálogo de 12 Provedores `Torrent-Api-py` + Quarteto Resiliente Default (`DEC-003`):**
   - Substituição do seed `1337x` pelo quarteto pré-configurado **`tgx` (TorrentGalaxy)**, **`nyaasi` (Nyaa.si)**, **`bitsearch` (BitSearch)** e **`glodls` (GloDLS)** sobre um catálogo completo de 12 indexadores com modo dual (`/api/v1/recent` + `/api/v1/search`) e *fast-skip* quando o sidecar `:8009` estiver offline.
3. **Sincronia Bipartida em 2 Etapas & Sync Command Deck (`DEC-004`, `DEC-005`, `DEC-006`):**
   - **Etapa 1 (Presença Estrutural + Poda):** Modos `incremental`, `baseline`, `library` (*Minha Biblioteca*) e `prune` (`POST /api/sources/prune` para remover torrents mortos com `0 seeds`) com Match Canônico automático contra `mainstream.db`.
   - **Etapa 2 (Hidratação Efêmera JIT no `TorrentModal.tsx`):** Padrão *Stale-While-Revalidate (SWR)* em `0ms`, roteamento por formato (`movie` vs `tv_show`), transação atômica `Replace-on-Success` e faixa colapsável **Inteligência YTS** (Guia Parental, Nota RT e 4 Sugestões Clicáveis).
   - **Batch Join Soberano & Sync Command Deck (`SourcesView.tsx`):** Cards de **Fontes de Dados** deduplicados por `imdb_id` e hidratados em lote por `IMDbCatalogShow` (`mainstream.db`), Deck com 5 Receitas de 1 clique, gaveta de Ajuste Fino, **Onda Card a Card** com progresso orbital e gatilho **`⚡ Buscar & Ingerir ao Vivo`**.
   - Suíte hermética ampliada para **73 testes aprovados** e `ADR-014` arquivada (`16/16` — [ADR-014-ER.md](file:///home/loupan/projetosVS/tv-pirata/docs/adr/ADR-014-ER.md)).

---

## 🚀 Sistema Extensível de Plugins para Fontes Externas — ADR-013 (Branch `UI-UX`, 2026-11-19)

### 🌟 Destaques Executivos e Evolução Arquitetural (`ADR-013`)
1. **Autodiscovery de Plugins (`pkgutil.iter_modules`) & Instâncias 1:N (`DEC-001`, `DEC-003`):**
   - Novo pacote [src/backend/providers/sources/](file:///home/loupan/projetosVS/tv-pirata/src/backend/providers/sources/__init__.py) com contrato `BaseSourceAdapter`, decorator `@register_source_adapter` e 5 adaptadores concretos: `eztv_adapter.py` (catálogo base), `yify_adapter.py` (YTS JSON API v2), `torrent_api_py_adapter.py` (sidecar 1:N `Ryuk-me/Torrent-Api-py` cobrindo `1337x`, `tgx`, `piratebay`, `nyaasi`, `bitsearch`, `limetorrent`, `yts`), `torznab_adapter.py` (conector XML Jackett/Prowlarr via stdlib `xml.etree.ElementTree`) e `unique_web_adapter.py` (fontes web únicas não-torrent).
   - CRUD completo de instâncias 1:N (`GET /api/sources/adapters`, `POST /api/sources`, `PATCH /api/sources/{key}`, `DELETE /api/sources/{key}`, `POST /api/sources/{key}/test`) com sanitização Zero-Trust (`validate_safe_url`, `mask_secret_config`, `merge_preserving_secrets`).
2. **Lazy-Cache 24h com `EntityResolutionService` & Alerta Manual de CAPTCHA/Challenge (`DEC-002`, `DEC-004`):**
   - Busca sob demanda (`live=auto|force`, `q_override`) que reutiliza cache local fresco (`< 24h`) e reconcilia resultados via `compute_title_match_confidence`: correspondências com `confidence >= 0.85` são persistidas em `ExternalRelease` (alimentando `has_media` e `media_sources`), enquanto `0.60 <= confidence < 0.85` são exibidas apenas como `approx_matches` efêmeros sem poluir `data/sources.db`.
   - Circuit breaker de 2 níveis (por instância e cooldown de 60s por host compartilhado) e banner `44×44px` de desafio manual (`challenge_url`) em [TorrentModal.tsx](file:///home/loupan/projetosVS/tv-pirata/src/frontend/src/components/TorrentModal.tsx) para fontes bloqueadas por Cloudflare/reCAPTCHA.
3. **Deshardcoding Total de Fontes & Gerenciador Visual (`DEC-005`, `DEC-006`):**
   - Facetas e filtros SQL dinâmicos em [discovery_engine.py](file:///home/loupan/projetosVS/tv-pirata/src/backend/repositories/discovery_engine.py) e [ExplorerView.tsx](file:///home/loupan/projetosVS/tv-pirata/src/frontend/src/components/ExplorerView.tsx), e gerenciador `+ Adicionar Fonte` / `Config` / `Testar` em [StatusConfigView.tsx](file:///home/loupan/projetosVS/tv-pirata/src/frontend/src/components/StatusConfigView.tsx).
   - Suíte hermética ampliada para **72 testes aprovados** ([test_source_plugins_contract.py](file:///home/loupan/projetosVS/tv-pirata/tests/integration/test_source_plugins_contract.py)) e `ADR-013` arquivada (`16/16` — [ADR-013-ER.md](file:///home/loupan/projetosVS/tv-pirata/docs/adr/ADR-013-ER.md)).

---

## 🚀 Consolidação UI/UX & Multi-Fonte — ADR-012 (Branch `UI-UX`, 2026-11-17)

### 🌟 Destaques Executivos e Evolução Arquitetural (`ADR-012`)
1. **Explorar Unificado em Modo Adaptativo (`DEC-001`, `DEC-005`):**
   - Fusão das antigas abas **Descobrir** e **Explorar Universo** na jornada única **Explorar** (`Navbar.tsx` com 4 abas principais + botão dedicado de Configurações): estado ocioso com `HeroBanner`, barra de Atalhos Rápidos, **Roleta de Descoberta** (3 escolhas contrastantes) e carrosséis curados, colapsando o Hero ao digitar ou ativar filtros.
   - Motor híbrido com accordion top-10 gêneros (`show_all_genres`), `debounce 350ms`, `RequestAbortChannel` (`AbortController`), barra de progresso linear não-destrutiva e botão explícito **Aplicar Filtros** (com toggle opcional **Auto-aplicar**).
2. **Camada Multi-Fonte `Fontes de Dados` & `MediaBadge` (`DEC-002`):**
   - Evolução de `Catálogo EZTV` para **Fontes de Dados** (`SourcesView.tsx`), respaldada por `sources_metadata` (`ExternalSourceRecord` e `ExternalRelease` em `data/sources.db`), `SourcesRegistryService` (`eztv`, `yify`, `1337x`) e endpoints `/api/sources/{summary,releases,catalog,sync}` com retrocompatibilidade `/api/catalog/*` e `/api/torrents/*`.
   - Substituição de `EztvBadge.tsx` por [MediaBadge.tsx](file:///home/loupan/projetosVS/tv-pirata/src/frontend/src/components/MediaBadge.tsx) (abaixo da nota IMDb) e generalização de `TorrentModal.tsx` para abas por provedor (magnets + links externos).
3. **Central `Status, Sincronização & Config` & Preferências Híbridas (`DEC-003`):**
   - Nova tela [StatusConfigView.tsx](file:///home/loupan/projetosVS/tv-pirata/src/frontend/src/components/StatusConfigView.tsx) acessível por botão `44×44px` + indicador de saúde na barra superior, concentrando controles Dual-SSOT (`mainstream.db` + `sources.db`) e preferências persistidas em `localStorage` + `GET`/`PUT /api/explore/preferences` (`sync_state`).
4. **`ShowCard` Interativo Responsivo & WCAG 2.2 AA (`DEC-004`, `DEC-006`):**
   - Empilhamento vertical de **todos** os `ProviderBadge`s acima da `StatusBadge` (`>= 190px`) com salvaguarda `1 + N` abaixo de `190px` (`375px` mobile), `MediaBadge` abaixo da nota IMDb, badges clicáveis configuráveis (`stopPropagation()` + `aria-label` dinâmico), botão rápido expansível `44×44px`, `:focus-visible` e `@media (prefers-reduced-motion: reduce)`.
   - Suíte hermética ampliada para **69 testes aprovados** (`test_sources_and_preferences_api.py`), `ruff check` limpo, `tsc --noEmit` + `vite build` compilados e `ADR-012` arquivada (`18/18` — [ADR-012-ER.md](file:///home/loupan/projetosVS/tv-pirata/docs/adr/ADR-012-ER.md)).

---

## 🚀 Release v0.7.0 — Consolidação Dual-SSOT (`mainstream.db` & `sources.db`), Busca Bilíngue FTS5, Taxonomia Canônica e Refatoração do Motor de Filtros (2026-11-17)

### 🌟 Destaques Executivos e Valor de Produto
A versão **v0.7.0** consolida o **TV Pirata** sobre uma arquitetura **Dual-SSOT** de escala universal (`ADR-011`): o catálogo principal passa a operar diretamente sobre **279.362 títulos** e **4.529.748 episódios** unificados (IMDb + TMDB + TVMaze + Biblioteca Pessoal) em [data/mainstream.db](file:///home/loupan/projetosVS/tv-pirata/data/mainstream.db), enquanto [data/sources.db](file:///home/loupan/projetosVS/tv-pirata/data/sources.db) isola as fontes externas P2P/EZTV (`860` séries e `140.571` episódios) 100% entrelaçadas ao catálogo canônico. Além disso, entrega busca bilíngue **PT-BR / EN-US** instantânea com ranking por similaridade, hidratação real de provedores de streaming via TMDB `/discover` e um painel multidimensional totalmente refatorado com contagens exatas em todas as categorias, formatos e fontes de dados.

### 🏗️ Principais Entregas Arquiteturais (`ADR-011`)
1. **Arquitetura Dual-SSOT & Motor SQL Pushdown (`279k+` Títulos em `< 6 ms`):**
   - Separação estrita entre **Base Canônica (`data/mainstream.db`)** e **Base de Recursos Externos (`data/sources.db`)**, com modelos dedicados `IMDbCatalogShow` e `IMDbEpisodeCatalog` isolados em `imdb_metadata`.
   - Reescrita de `DiscoveryEngineRepository` para execução 100% SQL Pushdown com índices compostos de cobertura (`idx_shows_filter_cover`, `idx_shows_score_cover`, `idx_shows_facets_cover`) e snapshot global pré-computado `global_facets_v2` em `sync_state` (`159,4 ms` end-to-end no `/api/explore/works`).
   - Cruzamento integral e upsert de **100%** das séries EZTV/CatalogShow de `sources.db` em `mainstream.db` (`878` obras marcadas com `has_eztv = 1`).
2. **Busca Bilíngue (`PT-BR` / `EN-US`) com `FTS5` e Ranking por Similaridade:**
   - Índice virtual `shows_fts` com tokenizer `unicode61 remove_diacritics 2`, permitindo consultas sem acentos (ex.: *"senhor dos aneis"*, *"um sonho de liberdade"*, *"Shawshank"*) nas páginas **Descobrir** e **Explorar Universo**.
   - Pontuação multi-camada (`score_title_pair_relevance` / `score_imdb_show_relevance`) priorizando correspondência exata, prefixo de franquia e similaridade contextual combinada à popularidade.
3. **Taxonomia Canônica Única, Streaming Real & Painel de Filtros Refatorado:**
   - Centralização em [canonical_taxonomy.py](file:///home/loupan/projetosVS/tv-pirata/src/backend/core/canonical_taxonomy.py): **31 categorias canônicas PT-BR** (corrigindo os antigos zeros em *Ficção Científica* `16.022`, *Suspense* `38.786`, *Crime & Investigação* `37.424`), **8 formatos** (incluindo *Documentário* `34.042`, *Animação* `13.803`, *Especial & Reality* `8.942`, *Curta-Metragem* `668`), **8 fontes de dados** (`EZTV P2P`, `Torrents Ativos`, `IMDb`, `TMDB`, `Sinopse PT-BR`, `Trailer YouTube`, `TVMaze`, `Minha Biblioteca`) e **25 provedores/redes de streaming**.
   - Coleta real via TMDB `/3/discover` (`BR`/`US`) com `12.373` títulos mapeados e `175.397` registros normalizados em `mainstream.db` (Netflix `3.888`, Prime Video `2.158`, Max `2.068`, Disney+ `1.872`, Globoplay `1.026`, Crunchyroll `3.912`).
   - Correspondência exata de tokens CSV (`_csv_token_in`), eliminando falsos positivos como `"Ação"` $\leftrightarrow$ `"Animação"`, `"Music"` $\leftrightarrow$ `"Musical"` e `"Max"` $\leftrightarrow$ `"Cinemax"`.
4. **Controles de Atualização Dual-SSOT & Limpeza de Filtros na UI:**
   - Novos endpoints `GET /api/explore/mainstream-stats` e `POST /api/explore/update-mainstream` (`delta`, `badges`, `hydrate`), integrados diretamente em `ExplorerView.tsx` e `CatalogView.tsx` ao lado dos controles de sincronização de `sources.db`.
   - Novo botão destacado **Limpar / Resetar Filtros** com contador de filtros ativos e limpeza instantânea de campos de busca em `ExplorerView.tsx`.

### 📊 Métricas da Release v0.7.0
- **Escala do Catálogo Canônico (`mainstream.db`):** `279.362` obras (`217.690` filmes, `49.760` séries, `11.912` minisséries) e `4.529.748` episódios catalogados.
- **Testes Automatizados:** `64 passed` (100% herméticos e offline, +suite integral Dual-SSOT em `tests/integration/test_mainstream_sources_ssot.py`).
- **ADRs Consolidadas e Arquivadas:** `11/11` (`ADR-001` a `ADR-011` — `100%` arquivadas com Certificados de Evidência `ER.md`).
- **Qualidade Estática:** `ruff check` (`All checks passed!`) e compilação React 19 + TypeScript (`tsc && vite build`) limpa em `src/backend/static/dist/`.

### 🔄 Guia de Atualização (v0.6.0 $\rightarrow$ v0.7.0)
```bash
# 1. Atualizar código e compilar assets do frontend
make build-front

# 2. (Opcional) Sincronizar cruzamento Dual-SSOT, streaming BR/US e facetas globais
.venv/bin/python scripts/sync_canonical_facets_and_providers.py

# 3. Iniciar o servidor integrado
make run
```

---

## 🚀 Release v0.6.0 — Audiovisual Discovery Core, Dual-Database EZTV & High-Performance Read Pipeline (2026-11-15)

### 🌟 Destaques Executivos e Valor de Produto
A versão **v0.6.0** materializa o reposicionamento estratégico do **TV Pirata** como uma **Plataforma de Descoberta Audiovisual (Discovery-First)** estruturada em 3 camadas (`ADR-008`), combinada com a separação física entre a base global de descoberta (`data/tv_pirata.db`) e a base dedicada de séries/episódios do provedor EZTV (`data/eztv_metadata.db`, `ADR-009`), além de uma otimização profunda de leitura e execução dual-SQLite (`ADR-010`) que reduziu em mais de **98%** a latência das consultas principais.

### 🏗️ Principais Entregas Arquiteturais (`ADR-008`, `ADR-009`, `ADR-010`)
1. **Domínio Canônico Multi-Formato & Resolução de Identidade (`ADR-008`):**
   - Introdução de 10 entidades SQLModel (`MediaWork`, `ExternalIdentifier`, `DataProvenance`, `PersonRecord`, `WorkCredit`, `GenreRecord`, `WorkGenreLink`, `StreamingAvailability`, `WorkRelation`, `ReleaseCalendarEvent`) desacopladas de arquivos locais ou torrents.
   - Reconciliação determinística por IDs externos e proteção anti-colisão para homônimos/remakes de anos distintos, preservando notas por fonte (`ratings_breakdown`) e procedência por atributo (`DataProvenance`).
   - Motor de filtragem booleana (`AND`/`OR`/`NOT`), facetas dinâmicas, descoberta de filmografias e colaborações recorrentes (`/api/explore/people/collaborations`), similaridade objetiva e calendário de estreias na aba **"Explorar Universo"** (`ExplorerView.tsx`).
2. **Separação Dual-Database (`tv_pirata.db` vs `eztv_metadata.db`), Entrelaçamento EZTV e Badges Universais (`ADR-009`):**
   - Isolamento de `EZTVShow` (`860` séries) e `EZTVEpisodeCatalog` (`140.571` episódios) em `src/backend/models/eztv_db.py` com sessões dedicadas `get_eztv_session()`.
   - Cruzamento automático de disponibilidade EZTV (`eztv_available`, `eztv_show_id`) em `/api/explore` e `/api/discovery`.
   - Novos componentes visuais `EztvBadge.tsx` e `ShowBadges.tsx` (`StatusBadge` para status da série e `ProviderBadge` para plataforma/emissora de streaming) presentes em todos os canais da SPA.
   - Crawler `scripts/eztv-metadata-catalog.py` com contorno resiliente a bloqueios Cloudflare (`403`) via fallback automático para a API JSON oficial (`/api/get-torrents`) e enriquecimento cruzado TVMaze + TMDB.
3. **Otimização SOTA+ de Desempenho de Leitura Dual-SQLite (`ADR-010`):**
   - Tuning automático de conexões SQLite (`PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-64000`, `mmap_size=268435456`).
   - Materialização de `episodes_count`, `max_season` e `max_episode` na tabela `shows`, eliminando varreduras `GROUP BY` sobre `140.571` episódios antes da paginação.
   - Índice virtual invertido `FTS5` (`shows_fts`) com triggers automáticos, pipeline single-pass em `get_curated_sections`, `EngineScopedCache` com fingerprint de versão e guarda `O(1)` (`_SEEDED_ENGINES`) no catálogo federado:
     - `list_shows(sort_by='seeds')`: `965,61 ms` $\rightarrow$ **`15,19 ms`** (-98,4%).
     - `get_curated_sections`: `692,07 ms` $\rightarrow$ **`4,74 ms`** (-99,3%).
     - `explore_works`: `~920,00 ms` $\rightarrow$ **`72,32 ms`** (-92,1%).

### 📊 Métricas da Release v0.6.0
- **Testes Automatizados:** `63 passed` (100% offline/herméticos, +16 novos testes cobrindo `ADR-008`, `ADR-009` e `ADR-010`).
- **ADRs Consolidadas e Arquivadas:** `10/10` (`ADR-001` a `ADR-010` — 100% das tarefas concluídas e auditadas com Certificados de Evidência `ER.md`).
- **Débitos Técnicos Ativos:** `0` (`8/8` débitos resolvidos e podados para `docs/governance/archive/tech-debt-archive.json`).
- **Breaking Changes:** Nenhuma (100% aditiva e retrocompatível).

### 🔄 Guia de Atualização (v0.5.0 $\rightarrow$ v0.6.0)
```bash
# 1. Atualizar código e compilar assets do frontend
make build-front

# 2. Iniciar o servidor (as 10 novas tabelas da Camada 1 são criadas automaticamente pelo init_db() no startup)
make run
```

---

## 🔔 Release v0.5.0 — Background Auto-Sync & Release Notifier (2026-11-12)

### 🌟 Destaques Executivos (`ADR-007`)
- **Sincronização Periódica Assíncrona (`BackgroundSyncService`):** Task nativa em `asyncio` gerenciada pelo `lifespan` do FastAPI com jitter de $\pm 10\%$, backoff exponencial e parada graciosa em $\le 3.0\text{s}$ (zero processos órfãos).
- **Reconciliação Automática e Notificações (`ReleaseNotificationRecord`):** Cruzamento automático entre novos lançamentos da EZTV e séries monitoradas na biblioteca do usuário (`watching` / `plan_to_watch`), gerando alertas idempotentes por `(show_id, season, episode)`.
- **UX de Alertas em Tempo Real:** Badges de contagem na `Navbar.tsx` e banners de novos episódios com atalho direto para download magnet na `LibraryView.tsx`.
- **Métricas:** Expansão da suíte para **47 testes automatizados**.

---

## 📡 Release v0.4.0 — Persistent EZTV Catalog & P2P Ingestion Engine (2026-11-12)

### 🌟 Destaques Executivos (`ADR-006`)
- **Catálogo P2P Persistente (`CatalogShow` & `CatalogRelease`):** Indexação local de torrents da EZTV enriquecidos com pôsteres, sinopses e notas via TVMaze/TMDB (`EZTVIndexerService`).
- **Roteador `/api/catalog` & CLI `scripts/sync_catalog.py`:** Paginação local ultrarrápida filtrada por `min_seeds` e aba dedicada **"Catálogo EZTV"** (`CatalogView.tsx`).
- **Métricas:** Expansão da suíte para **33 testes automatizados**.

---

## 🎬 Release v0.3.0 — Cinematic Web Frontend SPA (2026-11-12)

### 🌟 Destaques Executivos (`ADR-005`)
- **Single-Page Application React 19 + TypeScript + Tailwind CSS:** Design system **OLED-Safe Deep Slate** (`#090a0f`, `#131722`, `#d81f26`) com contraste WCAG 2.1 AAA.
- **Componentes Principais:** `HeroBanner`, `ShowCarousel`, `ShowDetailModal`, `TorrentModal`, `LibraryView` e `CollectionsView`, servidos diretamente pelo FastAPI em `/`.
- **Métricas:** Expansão da suíte para **24 testes automatizados**.

---

## 🗄️ Release v0.2.0 — Relational Persistence & FastAPI Server (2026-11-11)

### 🌟 Destaques Executivos (`ADR-004`)
- **Camada Relacional SQLModel (`src/backend/models/db.py`):** Persistência de `ShowRecord`, `SeasonRecord`, `EpisodeRecord`, `EpisodeWatchRecord`, `LocalMediaRecord`, `TagRecord` e `CollectionRecord`.
- **Servidor REST FastAPI:** Exposição dos roteadores `/api/discovery`, `/api/library`, `/api/watches`, `/api/torrents` e `/api/collections`.
- **Métricas:** Expansão da suíte para **22 testes automatizados**.

---

## 🏗️ Release v0.1.0 — Foundation Milestone (2026-11-11)

### 🌟 Destaques Executivos (`ADR-001`, `ADR-002`, `ADR-003`)
- **Contrato de Domínio Unificado (`UnifiedShow`, `TorrentRelease`):** Normalização Pydantic v2 com sanitização de HTML.
- **Motor de Descoberta com Fallback Resiliente (`ResilientDiscoveryService`):** Timeout de `2.0s` no TMDB com migração transparente para TVMaze e cliente assíncrono EZTV (`EZTVProvider`).
- **Métricas:** Suíte inicial de **13 testes herméticos** com `respx`.
