# Release Notes — TV Pirata 🏴‍☠️

Este documento consolida os marcos de valor de negócio, evolução arquitetural, métricas de verificação e guias de atualização para cada versão lançada do **TV Pirata**.

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
