# TV Pirata 🏴‍☠️

[![Version](https://img.shields.io/badge/version-v0.7.0-red.svg)](#)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)
[![Python](https://img.shields.io/badge/python-3.14+-blue.svg)](#)
[![Frontend](https://img.shields.io/badge/frontend-React%2019%20%2B%20Tailwind-38bdf8.svg)](#)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20%2B%20SQLModel-009688.svg)](#)
[![Tests](https://img.shields.io/badge/tests-77%20passing-brightgreen.svg)](#)
[![Governance](https://img.shields.io/badge/governance-SynPraxis%20SOTA-purple.svg)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

> **Audiovisual Discovery Platform & Personal Media Ecosystem (Discovery-First).**  
> *Motor de descoberta audiovisual multi-formato (Filmes, Séries, Minisséries, Documentários, Animações e Especiais), resolução de identidade multi-fonte com procedência por atributo, filtragem booleana (`AND`/`OR`/`NOT`), descoberta relacional por filmografia e colaborações, calendário unificado de estreias e ecossistema pessoal de biblioteca, rastreamento de episódios, catálogo P2P EZTV e notificações automáticas em segundo plano.*

---

## 1. 🎯 Visão Geral e Posicionamento Estratégico

O **TV Pirata** evoluiu de um gerenciador de mídia tradicional para uma **Plataforma de Descoberta Audiovisual (Discovery-First)** desenhada para eliminar o custo de exploração fragmentada entre múltiplos serviços de streaming (Netflix, Prime Video, Max, Apple TV+, Disney+, MUBI) e catálogos P2P/locais.

A plataforma é estruturada em uma **Arquitetura de 3 Camadas**:

| Camada | Escopo e Responsabilidades | Módulos Principais |
| :--- | :--- | :--- |
| **Camada 1 — Audiovisual Discovery Core** | Domínio canônico universal (`IMDbCatalogShow` com `279.362` obras e `4.529.748` episódios + `MediaWork` em `data/mainstream.db`), taxonomia canônica unificada (`canonical_taxonomy.py`: 31 categorias PT-BR, 25 streamings normalizados, 8 formatos, fontes multi-provedor), experiência unificada **Explorar** (Modo Adaptativo + Roleta + Filtros Híbridos com `AbortController`), busca bilíngue PT-BR/EN-US via `FTS5` (`shows_fts` sem acentos) com ranking exato/similaridade, motor SQL Pushdown (`DiscoveryEngineRepository`), facetas exatas materializadas (`global_facets_v2`), preferências híbridas (`/api/explore/preferences`) e sinalização agnóstica de disponibilidade (`has_media`, `media_sources`, `sources_count`, `has_eztv`). | `canonical_taxonomy.py`, `catalog_domain.py`, `entity_resolution.py`, `federated_catalog.py`, `discovery_engine.py`, `preferences.py`, `explore.py`, `ExplorerView.tsx`, `ShowBadges.tsx`, `MediaBadge.tsx`, `ShowCard.tsx`, `StatusConfigView.tsx` |
| **Camada 2 — External Sources & Personal Media Ecosystem** | Arquitetura Dual-SSOT (`data/mainstream.db` + `data/sources.db`), sistema extensível de plugins 1:N (`src/backend/providers/sources/`: `eztv`, `yify`, `torrent_api_py`, `torznab`, `unique_web`) isolados em `sources_metadata` (`ExternalSourceRecord`, `ExternalRelease`) + `EZTVShow` `860` séries / `140.571` episódios, `CatalogShow`, `CatalogRelease` com Lazy-Cache 24h e alerta manual de CAPTCHA, servidos por `/api/sources/*` e `SourcesView.tsx` (**Fontes de Dados**), biblioteca pessoal (`ShowRecord`), progresso por episódio (`EpisodeWatchRecord`), disponibilidade SMB (`LocalMediaRecord`), modal multi-fonte (`TorrentModal.tsx`) e alertas assíncronos em segundo plano (`BackgroundSyncService`). | `providers/sources/*`, `db.py`, `eztv_db.py`, `sources_db.py`, `sources_registry.py`, `sources.py`, `cache.py`, `library.py`, `catalog.py`, `notification.py`, `catalog_indexer.py`, `scheduler.py`, `LibraryView.tsx`, `SourcesView.tsx`, `TorrentModal.tsx` |
| **Camada 3 — Personalization & Intelligence** | Motor objetivo de similaridade multi-critério (interseção de gêneros, diretores/criadores, elenco, formato e proximidade temporal com justificativa explícita), coleções inteligentes (`CollectionRecord` + `filter_criteria`) e exclusão de títulos já assistidos. | `discovery_engine.py`, `collections.py`, `CollectionsView.tsx` |

---

## 2. 🏗️ Arquitetura do Sistema (3 Camadas)

```mermaid
flowchart TD
    subgraph UI["Frontend Cinemático SPA (React 19 + TypeScript + Tailwind OLED-Safe)"]
        Nav["Navbar (4 Abas + Botao 44x44 Status/Sync/Config)"]
        ExpView["ExplorerView (Explorar Unificado - Modo Adaptativo)"]
        CatView["SourcesView (Fontes de Dados: EZTV, YIFY, 1337x)"]
        CfgView["StatusConfigView (Dual-SSOT + Preferencias)"]
        LibView["LibraryView (Minha Biblioteca & Watch Progress)"]
        ColView["CollectionsView (Colecoes Inteligentes & Tags)"]
    end

    subgraph API["FastAPI REST Server (/api)"]
        R_Exp["/api/explore (Obras, Facetas, Preferencias, Pessoas, Agenda)"]
        R_Disc["/api/discovery (Busca & Trending Online)"]
        R_Cat["/api/sources, /api/catalog & /api/torrents (Multi-Fonte & Magnets)"]
        R_Lib["/api/library & /api/watches (Biblioteca & Episódios)"]
        R_Notif["/api/notifications (Alertas & Status do Scheduler)"]
        R_Col["/api/collections (Smart Collections & Tags)"]
    end

    subgraph Core["Camada 1: Audiovisual Discovery Core"]
        Fed["FederatedCatalogService"]
        ER["EntityResolutionService (Tier 1 IDs / Tier 2 Composto + Provenance)"]
        DE["DiscoveryEngineRepository (Filtros AND/OR/NOT, Facetas, Similaridade)"]
    end

    subgraph Ecosystem["Camada 2: Personal Media Ecosystem"]
        Sched["BackgroundSyncService (Lifespan asyncio.Task + Jitter/Backoff)"]
        Idx["EZTVIndexerService (Ingestão + Reconciliação)"]
        ResDisc["ResilientDiscoveryService (TMDB 2.0s -> Fallback TVMaze)"]
    end

    subgraph Storage["Persistência Dual-SSOT (SQLite / SQLModel + WAL + FTS5)"]
        DB_L1[("Base Canônica (data/mainstream.db): shows (279k+ IMDb/TMDB/TVMaze), episodes_catalog (4.5M+), mediawork, biblioteca pessoal, shows_fts, global_facets_v2")]
        DB_L2[("Base de Recursos Externos (data/sources.db): shows EZTV (860), episodes_catalog (140k+), catalogshow, catalogrelease, shows_fts")]
    end

    UI -->|"HTTP / JSON"| API
    R_Exp --> DE
    R_Exp --> Fed
    Fed --> ER
    DE --> DB_L1
    ER --> DB_L1

    R_Disc --> ResDisc
    R_Cat --> Idx
    R_Lib --> DB_L2
    R_Notif --> Sched
    R_Col --> DB_L2
    Sched --> Idx
    Idx --> DB_L2
```

---

## 3. ✨ Matriz de Capacidades por Módulo

### 3.1. Camada 1 — Audiovisual Discovery Core (`ADR-008`)
- **Domínio Canônico Multi-Formato (`MediaWork`):** Suporta `movie`, `tv_show`, `mini_series`, `documentary`, `animation` e `special` independentemente de arquivos locais ou torrents.
- **Resolução de Identidade Multi-Fonte (`EntityResolutionService`):**
  - **Tier 1 (`deterministic`, confiança `1.0`):** Reconciliação exata por `imdb_id`, `tmdb_id`, `tvmaze_id`, `trakt_id`, `wikidata_id` ou `eztv_id`.
  - **Tier 2 (`high`, confiança `0.90`):** Reconciliação composta (`normalized_title` + `format` + `release_year` exato) com proteção anti-colisão para homônimos e remakes de anos distintos (ex.: *Dune* 1984 vs *Dune* 2021).
- **Rastreabilidade de Procedência (`DataProvenance`) e Notas por Fonte (`ratings_breakdown`):** Preserva a fonte de cada atributo (`title`, `synopsis`, `poster_url`, `runtime_minutes`, `genres`) e exibe as notas individuais de cada plataforma (`imdb`, `tmdb`, `tvmaze`, `rotten_tomatoes`, `metacritic`) sem médias opacas.
- **Motor de Filtragem Booleana e Facetas (`DiscoveryEngineRepository`):**
  - Inclusão de gêneros em modo **`OR`** (qualquer gênero selecionado) ou **`AND`** (interseção estrita de todos os gêneros selecionados) + exclusão explícita (**`NOT`**).
  - Filtros combináveis por formato, janela de anos (`year_min`..`year_max`), nota mínima (`rating_min`), duração (`runtime_min`..`runtime_max`), país, idioma original, plataforma de streaming, diretor, ator, criador, disponibilidade em torrent P2P e ocultação de obras já assistidas (`exclude_watched`).
  - Contadores dinâmicos de facetas recalculados em tempo real para o subconjunto filtrado.
- **Descoberta Relacional e Similaridade:**
  - Filmografia completa de diretores, criadores, roteiristas e atores (`/api/explore/people/{id}`).
  - Interseção de colaborações recorrentes entre dois profissionais (`/api/explore/people/collaborations`).
  - Cálculo determinístico de obras similares com justificativa transparente (`shared_reasons`) e relações explícitas (`remake_of`, `spin_off_of`, `sequel_to`, `adapted_from`).
- **Calendário Unificado de Lançamentos:** Eventos de estreia mundial, episódios inéditos, lançamentos em streaming e finais de temporada (`/api/explore/calendar`).

### 3.2. Arquitetura Dual-SSOT, Motor SQL Pushdown & Taxonomia Canônica (`ADR-009`, `ADR-010`, `ADR-011`)
- **Separação Dual-SSOT (`ADR-011`):**
  - **Base Canônica (`data/mainstream.db`):** Consolida o catálogo universal IMDb (`279.362` obras e `4.529.748` episódios em `shows`/`episodes_catalog`), metadados PT-BR/EN-US TMDB/TVMaze, modelos relacionais `MediaWork` e a biblioteca pessoal (`ShowRecord`, `EpisodeWatchRecord`, `LocalMediaRecord`, `CollectionRecord`). Inclui índices de cobertura (`idx_shows_filter_cover`, `idx_shows_score_cover`, `idx_shows_facets_cover`), tabela virtual `FTS5` bilíngue (`shows_fts` com `unicode61 remove_diacritics 2`) e controles de atualização incremental direto na interface (`/api/explore/update-mainstream`).
  - **Base de Recursos Externos (`data/sources.db`):** Concentra o acervo P2P da EZTV (`860` séries em `shows`, `140.571` episódios em `episodes_catalog`, `catalogshow` e `catalogrelease`), 100% cruzado e refletido em `mainstream.db` com `has_eztv = 1` (`878` obras marcadas) e badges visuais (`EztvBadge`, `StatusBadge`, `ProviderBadge`).
- **Taxonomia Canônica & Disponibilidade Real de Streaming (`canonical_taxonomy.py`):**
  - Unifica `genres` e `genres_ptbr` em **31 categorias canônicas PT-BR**, **8 formatos audiovisuais** (`Filme`, `Série de TV`, `Minissérie`, `Telefilme`, `Documentário`, `Animação`, `Especial & Reality`, `Curta-Metragem`), **8 fontes de dados** (`EZTV P2P`, `Torrents c/ Seeds Ativos`, `IMDb Universal`, `TMDB Hidratado`, `Sinopse PT-BR`, `Com Trailer YouTube`, `TVMaze Séries`, `Minha Biblioteca`) e **25 serviços/redes de streaming** hidratados via TMDB `/3/discover` (`BR`/`US`) com correspondência exata de tokens CSV (`_csv_token_in`) e snapshot global em `sync_state` (`global_facets_v2`).
- **Busca Bilíngue (PT-BR & EN-US) com Ranking de Similaridade:** Consultas em `/api/discovery/search` e `/api/explore/works` toleram ausência de acentos (ex.: *senhor dos aneis*) e ordenam correspondências exatas e por similaridade (`score_title_pair_relevance`) no topo.
- **Engenharia de Alta Performance Dual-SQLite (`ADR-010`):**
  - Tuning automático via listener SQLAlchemy (`PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `temp_store=MEMORY`, `cache_size=-64000`, `mmap_size=268435456`) e `EngineScopedCache` com fingerprint de versão de tabela.
- **Provedores Online, Auto-Sync e Crawlers Resilientes:** `ResilientDiscoveryService` (`TMDB 2.0s -> TVMaze`), `BackgroundSyncService` no `lifespan`, e pipeline CLI completo (`scripts/imdb-metadata-catalog.py`, `scripts/sync-eztv-bade.py`, `scripts/sync_canonical_facets_and_providers.py`, `scripts/eztv-metadata-catalog.py`).

---

## 4. 📁 Estrutura Canônica do Repositório

```text
tv-pirata/
├── src/
│   ├── backend/                        # API REST Assíncrona (FastAPI + SQLModel)
│   │   ├── api/                        # Roteadores REST (/api/*)
│   │   │   ├── explore.py              # Camada 1: /api/explore (Obras, Facetas, Pessoas, Calendário)
│   │   │   ├── discovery.py            # /api/discovery (Trending e Busca Resiliente TMDB/TVMaze)
│   │   │   ├── catalog.py              # Camada 2: /api/catalog (Catálogo P2P Persistente EZTV)
│   │   │   ├── library.py              # Camada 2: /api/library (CRUD da Biblioteca Pessoal)
│   │   │   ├── watches.py              # Camada 2: /api/watches (Progresso de Episódios/Temporadas)
│   │   │   ├── notifications.py        # Camada 2: /api/notifications (Alertas & Status do Scheduler)
│   │   │   ├── torrents.py             # Camada 2: /api/torrents (Lookup de Magnets por IMDb ID)
│   │   │   └── collections.py          # Camada 3: /api/collections (Tags & Smart Collections)
│   │   ├── core/
│   │   │   ├── cache.py                # EngineScopedCache thread-safe com fingerprint (ADR-010)
│   │   │   ├── canonical_taxonomy.py   # SSOT: 31 categorias, 25 streamings, 8 formatos, 8 fontes
│   │   │   ├── config.py               # Configurações tipadas (Pydantic Settings)
│   │   │   └── database.py             # Engines Dual-SSOT (mainstream.db + sources.db), PRAGMAs e FTS5
│   │   ├── models/
│   │   │   ├── catalog_domain.py       # Camada 1: 10 entidades SQLModel (MediaWork, DataProvenance, etc.)
│   │   │   ├── db.py                   # Camada 2/3: 11 entidades SQLModel (ShowRecord, CatalogShow, etc.)
│   │   │   ├── eztv_db.py              # Camada 2: Modelos isolados EZTVShow e EZTVEpisodeCatalog (ADR-009)
│   │   │   └── unified.py              # Contratos Pydantic v2 (UnifiedShow, TorrentRelease)
│   │   ├── providers/
│   │   │   ├── base.py                 # Protocolo abstrato BaseMetadataProvider
│   │   │   ├── tmdb.py                 # Cliente assíncrono TMDB API v3
│   │   │   ├── tvmaze.py               # Cliente assíncrono TVMaze (Fallback público)
│   │   │   ├── eztv.py                 # Cliente assíncrono EZTV Torrents API
│   │   │   └── discovery_service.py    # Orquestrador ResilientDiscoveryService
│   │   ├── repositories/
│   │   │   ├── discovery_engine.py     # Camada 1: Filtragem booleana, facetas, filmografia e similaridade
│   │   │   ├── catalog.py              # Camada 2: Consultas paginadas do acervo EZTV
│   │   │   ├── library.py              # Camada 2/3: Upsert transacional, watches e smart collections
│   │   │   └── notification.py         # Camada 2: Gestão de alertas de novos episódios
│   │   ├── services/
│   │   │   ├── entity_resolution.py    # Camada 1: Reconciliação Tier 1/Tier 2 e DataProvenance
│   │   │   ├── federated_catalog.py    # Camada 1: Federação multi-fonte e ponte com Camada 2
│   │   │   ├── curated_catalog_seed.json # Dataset canônico multi-formato (Filmes, Séries, Docs, Animes)
│   │   │   ├── catalog_indexer.py      # Camada 2: Indexador EZTV e reconciliação de lançamentos
│   │   │   └── scheduler.py            # Camada 2: BackgroundSyncService (asyncio Lifespan)
│   │   ├── static/                     # Favicons e bundle compilado da SPA (static/dist)
│   │   └── main.py                     # Entrypoint FastAPI, Lifespan e entrega da SPA
│   └── frontend/                       # Single-Page Application (React 19 + TypeScript + Vite)
│       ├── src/
│       │   ├── components/
│       │   │   ├── Navbar.tsx          # Navegação global, busca debounced e badge de notificações
│       │   │   ├── ExplorerView.tsx    # Camada 1: "Explorar Universo" (Filtros AND/OR/NOT, Dossiê, Pessoas)
│       │   │   ├── HeroBanner.tsx      # Destaque cinematográfico principal
│       │   │   ├── ShowCarousel.tsx    # Carrosséis horizontais com scroll-snap
│       │   │   ├── CatalogView.tsx     # Camada 2: Explorador do acervo P2P EZTV
│       │   │   ├── LibraryView.tsx     # Camada 2: Biblioteca pessoal e alertas de novos episódios
│       │   │   ├── CollectionsView.tsx # Camada 3: Coleções inteligentes e tags
│       │   │   ├── ShowDetailModal.tsx # Modal de temporadas, episódios e status SMB
│       │   │   ├── TorrentModal.tsx    # Modal de releases 4K/1080p/720p e links magnet
│       │   │   ├── EztvBadge.tsx       # Badge vetorial de disponibilidade no catálogo EZTV (ADR-009)
│       │   │   └── ShowBadges.tsx      # Badges permanentes de Status e Provedor de Streaming
│       │   ├── services/api.ts         # Cliente HTTP tipado para todas as rotas /api/*
│       │   ├── types.ts                # Interfaces TypeScript espelhando os contratos do backend
│       │   └── App.tsx                 # Roteamento de abas e estado global da SPA
│       └── package.json
├── scripts/
│   ├── quality_gate.sh                      # Gate determinístico pré-commit (Ruff + Pytest)
│   ├── imdb-metadata-catalog.py             # Hidratação IMDb + TMDB (dumps TSV + /changes + watch/providers)
│   ├── sync-eztv-bade.py                    # Propagação de badges & status sources.db -> mainstream.db
│   ├── sync_canonical_facets_and_providers.py # Harvest TMDB /discover, normalização e global_facets_v2
│   ├── sync_catalog.py                      # CLI para ingestão de páginas de releases da EZTV
│   └── eztv-metadata-catalog.py             # Crawler concorrente EZTV Showlist + Ficha + TVMaze
├── tests/
│   ├── fixtures/                            # Payloads JSON determinísticos (TMDB, TVMaze, EZTV)
│   ├── unit/                                # Testes unitários (modelos, entity resolution, discovery engine, scheduler)
│   └── integration/                         # Testes REST (/api/explore, /api/catalog, Dual-SSOT mainstream/sources)
├── docs/
│   ├── adr/                                 # Architecture Decision Records (ADR-001 a ADR-011 + ADR-INDEX.md)
│   ├── governance/                     # Registro estruturado de débitos técnicos (tech-debt-registry.json)
│   ├── reports/                        # Relatórios de auditoria e arquivamento de ADRs
│   └── DOCUMENTATION_AUDIT_REPORT.md   # Relatório de conformidade dos 6 Pilares SOTA
├── README.md                           # Pilar 1: Visão geral executiva e arquitetura
├── CHANGELOG.md                        # Pilar 2: Histórico cronológico SemVer (Keep a Changelog)
├── USAGE.md                            # Pilar 3: Manual prático de operação, CLI e exemplos de API
├── RELEASE-NOTES.md                    # Pilar 4: Notas de versão executivas e guia de atualização
├── STATE.md                            # Pilar 5: Memória persistente de estado do agente
└── AGENTS.md / GEMINI.md               # Pilar 6: Governança e invariantes de engenharia (SSOT)
```

---

## 5. 🚀 Primeiros Passos (Quick Start)

### Pré-requisitos
- **Python 3.10+** (ambiente homologado com Python 3.14 via `uv`)
- **Node.js 20+ / npm** (apenas caso deseje recompilar ou desenvolver o frontend SPA; o bundle de produção já é versionado em `src/backend/static/dist/`)

### Instalação e Execução Rápida
```bash
# 1. Copiar o template de variáveis de ambiente
cp .env.example .env

# 2. Instalar dependências Python (produção + desenvolvimento/testes)
uv pip install -e ".[dev]"

# 3. (Opcional) Compilar o bundle de produção do frontend React 19
make build-front

# 4. Iniciar o servidor integrado FastAPI + SPA em http://127.0.0.1:8000
make run
```

Acesse no navegador:
- **Aplicação Web Cinemática (SPA):** `http://127.0.0.1:8000/`
- **Documentação Interativa OpenAPI (Swagger):** `http://127.0.0.1:8000/docs`

---

## 6. 🛠️ Matriz de Comandos (`Makefile`)

| Comando | Descrição |
| :--- | :--- |
| `make run` | Inicia o servidor integrado FastAPI + SPA em `http://127.0.0.1:8000` com auto-reload |
| `make build-front` | Compila a SPA React 19 + TypeScript + Tailwind para `src/backend/static/dist/` |
| `make dev-front` | Inicia o servidor Vite com Hot Module Replacement (HMR) em `http://127.0.0.1:5173` |
| `make sync-catalog` | Sincroniza e enriquece as páginas mais recentes de torrents da EZTV no banco local |
| `make hydrate` | Executa o Motor Unificado dos 3 Pilares com checkpoint retomável (`scripts/hydrate_ecosystem.py --resume`) |
| `make test` | Executa a suíte completa de **77 testes automatizados** (100% offline/herméticos) |
| `make lint` | Executa análise estática de código Python via `ruff check src/ tests/` |
| `make format` | Formata automaticamente o código-fonte com `ruff format src/ tests/` |
| `make setup-hooks` | Instala o `scripts/quality_gate.sh` como hook `pre-commit` do Git |
| `make clean` | Remove caches temporários (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `dist`) |

---

## 7. 🏛️ Governança Arquitetural (ADRs)

Todas as decisões estruturais estão documentadas e auditadas em [docs/adr/ADR-INDEX.md](./docs/adr/ADR-INDEX.md) com Certificados de Evidência (`ADR-001-ER.md` a `ADR-011-ER.md`):
- **ADR-001 a ADR-004 (Consolidadas/Arquivadas):** Fundação SMB, provedores TMDB/TVMaze com fallback de 2.0s, integração EZTV e persistência SQLModel + FastAPI.
- **ADR-005 (Consolidada/Arquivada):** Frontend Cinemático SPA (React 19 + Tailwind CSS) com Design System OLED-Safe (`#090a0f`).
- **ADR-006 (Consolidada/Arquivada):** Catálogo Local Persistente da EZTV e Motor de Ingestão P2P.
- **ADR-007 (Consolidada/Arquivada):** Background Auto-Sync, Agendamento Assíncrono (`lifespan`) e Notificador de Novos Lançamentos.
- **ADR-008 (Consolidada/Arquivada):** Fundação do Audiovisual Discovery Core (Camada 1): Domínio Canônico Multi-Formato, Resolução de Identidade com Procedência e Motor de Descoberta.
- **ADR-009 (Consolidada/Arquivada):** Separação de Bases (`tv_pirata.db` vs `eztv_metadata.db`), Entrelaçamento EZTV e Sistema Universal de Badges (`StatusBadge`, `ProviderBadge`, `EztvBadge`).
- **ADR-010 (Consolidada/Arquivada):** Otimização de Desempenho de Leitura Dual-SQLite (`PRAGMA`s WAL/mmap), Estatísticas Materializadas, `EngineScopedCache` com Fingerprint e Índice Virtual `FTS5`.
- **ADR-011 (Consolidada/Arquivada):** Consolidação Dual-SSOT (`data/mainstream.db` + `data/sources.db`), IMDb como Âncora Universal (`279k+` Títulos / `4.5M+` Episódios), Busca Bilíngue `FTS5`, Taxonomia Canônica (`31` Categorias / `25` Streamings / `8` Fontes) e Motor SQL Pushdown.
- **ADR-012 (Consolidada/Arquivada):** Experiência Unificada **Explorar** (Modo Adaptativo + Roleta + Filtros Híbridos com `AbortController`), camada multi-provedor **Fontes de Dados**, `MediaBadge`, Central `StatusConfigView` com preferências híbridas (`/api/explore/preferences`), `ShowCard` com empilhamento completo/`1+N` e WCAG 2.2 AA.
- **ADR-013 & ADR-014 (Consolidadas/Arquivadas):** Sistema Extensível de Plugins 1:N (`Torrent-Api-py` 12 sites + Sidecar `:8009`, `Torznab`, `UniqueWeb`), alinhamento `sources-apis.md` (YTS `movies-api.accel.li` + EZTV RSS), Sincronia Bipartida em 2 Etapas e **Sync Command Deck**.
- **ADR-015 (Consolidada/Arquivada):** Motor Unificado dos 3 Pilares de Hidratação c/ Checkpoint `--resume`, Gatilho Inteligente de Maturidade (`BOOTSTRAP` $\leftrightarrow$ `DELTA`), Compact Presence + Catalog Sweep (`YTS` & Sidecar `:8009`), Auto-Cura Cross-DB e Cascata Hierárquica de 6 Degraus (`IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Wikidata/Wikipédia/Jikan v4`).
