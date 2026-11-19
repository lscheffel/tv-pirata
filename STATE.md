# Estado Atual do Workspace (STATE.md)

> **Persistent Agent Memory & Repository State (SSOT)**  
> Última auditoria e reconciliação completa (6 Pilares SOTA): 2026-11-19

---

## 1. 📍 Contexto e Fase Ativa

- **Versão Atual:** `v0.7.0` (`+ ADR-012 & ADR-013 Consolidadas`)
- **Branch Ativa:** `UI-UX`
- **Posicionamento Arquitetural:** **Audiovisual Discovery Platform & Personal Media Ecosystem (Discovery-First)** estruturada em 3 camadas e arquitetura **Dual-SSOT** (`data/mainstream.db` + `data/sources.db`):
  - **Camada 1 — Base Canônica & Audiovisual Discovery Core (`data/mainstream.db`):** Catálogo universal `IMDbCatalogShow` (`279.362` obras e `4.529.748` episódios em `IMDbEpisodeCatalog`) + `MediaWork`, taxonomia canônica (`canonical_taxonomy.py`: 31 categorias, 25 streamings normalizados via TMDB `/discover`, 8 formatos, fontes multi-provedor dinâmicas), índice bilíngue `FTS5` PT-BR/EN-US (`shows_fts`), motor SQL Pushdown (`DiscoveryEngineRepository`), snapshot global `global_facets_v2`, preferências híbridas (`/api/explore/preferences`) e experiência unificada **Explorar** (`ExplorerView.tsx`, Modo Adaptativo + Roleta + Filtros Híbridos com `AbortController`).
  - **Camada 2 — Base de Recursos Externos Pluggable Multi-Provedor & Personal Media Ecosystem (`data/sources.db` + `data/mainstream.db`):** Sistema extensível de plugins (`src/backend/providers/sources/`: `eztv`, `yify`, `torrent_api_py`, `torznab`, `unique_web`) com autodiscovery (`pkgutil.iter_modules`), instâncias 1:N configuráveis em `ExternalSourceRecord` / `ExternalRelease` (`sources_metadata`) + base `EZTVShow` (`860` séries / `140.571` episódios, `CatalogShow`, `CatalogRelease`) em `data/sources.db`, Lazy-Cache 24h com `EntityResolutionService` (`>= 0.85` persistido vs `0.60–0.84` `approx_matches`) e alerta manual de CAPTCHA/Challenge (`challenge_url`), servidos por `/api/sources/*`, `SourcesView.tsx` (**Fontes de Dados**), `TorrentModal.tsx` e `StatusConfigView.tsx`, além de biblioteca pessoal (`ShowRecord`), progresso por episódio (`EpisodeWatchRecord`), disponibilidade SMB (`LocalMediaRecord`) e `BackgroundSyncService` + `ReleaseNotificationRecord`.
  - **Camada 3 — Personalization & Intelligence:** Motor de similaridade multi-critério com justificativa explícita, coleções inteligentes (`CollectionRecord`) e exclusão de títulos já assistidos.
- **Status do Build / Quality Gate:** **PASSING** (`72/72` testes aprovados, `ruff check` 100% limpo, `tsc --noEmit` limpo, bundle SPA Vite compilado em `src/backend/static/dist/`).

---

## 2. 🏛️ Ledger Consolidado de ADRs (`docs/adr/ADR-INDEX.md`)

| ID | Título | Arquivada | Progresso | Implementação | Janitor Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **ADR-001** | [Arquitetura Fundamental do TV Pirata (Descoberta, Controle e SMB)](./docs/adr/ADR-001-ER.md) | Sim | 6/6 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-002** | [Provedores de Descoberta, Fallback Resiliente e Gestão de Mídia (Schema v1)](./docs/adr/ADR-002-ER.md) | Sim | 7/7 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-003** | [Implementação do Contrato Unificado, Provedores com Fallback e EZTV](./docs/adr/ADR-003-ER.md) | Sim | 10/10 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-004** | [Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI](./docs/adr/ADR-004-ER.md) | Sim | 11/11 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-005** | [Frontend Cinemático SPA (Vite + React + Tailwind), Design System OLED-Safe](./docs/adr/ADR-005-ER.md) | Sim | 12/12 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-006** | [Catálogo Local Persistente da EZTV e Motor de Ingestão P2P](./docs/adr/ADR-006-ER.md) | Sim | 12/12 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-007** | [Background Auto-Sync, Agendamento Assíncrono e Notificador de Novos Lançamentos](./docs/adr/ADR-007-ER.md) | Sim | 12/12 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-008** | [Fundação do Audiovisual Discovery Core (Camada 1): Domínio Canônico, Procedência e Motor de Descoberta](./docs/adr/ADR-008-ER.md) | Sim | 10/10 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-009** | [Separação de Bases (tv_pirata.db vs eztv_metadata.db) + Entrelaçamento EZTV](./docs/adr/ADR-009-ER.md) | Sim | 7/7 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-010** | [Otimização de Desempenho de Leitura Dual-SQLite, Estatísticas Materializadas, Cache Escopado por Engine e FTS5](./docs/adr/ADR-010-ER.md) | Sim | 21/21 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-011** | [Consolidação Dual-SSOT (`data/mainstream.db` vs `data/sources.db`), IMDb Universal (`279k+` Títulos) e Motor SQL Pushdown](./docs/adr/ADR-011-ER.md) | Sim | 16/16 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-012** | [Experiência Unificada `Explorar`, Camada Multi-Fonte `Fontes de Dados`, Central `StatusConfigView` e `ShowCard` Interativo](./docs/adr/ADR-012-ER.md) | Sim | 18/18 (100%) | CONSOLIDADA | `ARCHIVED_OK` |
| **ADR-013** | [Sistema Extensível de Plugins para Fontes Externas (Adapters 1:N, Torrent-Api-py, Torznab, Lazy-Cache & Challenge Manual)](./docs/adr/ADR-013-ER.md) | Sim | 16/16 (100%) | CONSOLIDADA | `ARCHIVED_OK` |

---

## 3. 💳 Registro de Débitos Técnicos (`docs/governance/tech-debt-registry.json`)

- **Débitos Ativos:** `0` (Nenhum débito técnico aberto).
- **Débitos Resolvidos e Arquivados (`docs/governance/archive/tech-debt-archive.json`):** `8/8` (`TD-2026-001` a `TD-2026-008` — 100% mitigados e podados pelo `adr-archive`).

---

## 4. 📜 Histórico Recente de Sessões

- **2026-11-11 (`v0.1.0` $\rightarrow$ `v0.2.0`):** Bootstrap do repositório (`ADR-001`), modelos unificados e provedores com fallback TMDB/TVMaze + EZTV (`ADR-002`, `ADR-003`), persistência relacional SQLModel e servidor FastAPI (`ADR-004`).
- **2026-11-12 (`v0.3.0` $\rightarrow$ `v0.5.0`):** Implementação do Frontend Cinemático SPA React 19 OLED-Safe (`ADR-005`), Catálogo Persistente P2P EZTV (`ADR-006`) e Background Auto-Sync + Release Notifier (`ADR-007`).
- **2026-11-12 a 2026-11-15 (`v0.6.0`):**
  - Implementada `ADR-008` (Camada 1: Domínio Canônico Multi-Formato, `EntityResolutionService`, `FederatedCatalogService`, `DiscoveryEngineRepository`, `/api/explore` e `ExplorerView.tsx`).
  - Implementada `ADR-009` (Isolamento Dual-Database `data/tv_pirata.db` vs `data/eztv_metadata.db`, cruzamento de disponibilidade EZTV, sistema de badges permanentes `StatusBadge`, `ProviderBadge` e `EztvBadge`, e contorno Cloudflare `403` com enriquecimento multi-provedor em `scripts/eztv-metadata-catalog.py`).
  - Implementada `ADR-010` (Tuning `PRAGMA`s SQLite WAL/mmap, estatísticas de episódios materializadas em `shows`, índice virtual `FTS5` `shows_fts`, `EngineScopedCache` com fingerprint e pipeline single-pass de seções curadas, reduzindo a latência de leitura em mais de 98%).
  - Executado ciclo completo `adr-archive` (`ADR-005` a `ADR-010` arquivadas com `ER.md` e poda de débitos) e reconciliação dos 6 Pilares SOTA.
- **2026-11-17 (`v0.7.0`):**
  - Implementada e arquivada `ADR-011` (`16/16` tarefas concluídas com `ADR-011-ER.md`): consolidação Dual-SSOT (`data/mainstream.db` com `279.362` obras / `4.529.748` episódios + `data/sources.db` com `860` séries / `140.571` episódios), motor SQL Pushdown com índices de cobertura, busca bilíngue PT-BR/EN-US via `shows_fts` (`unicode61 remove_diacritics 2`) e ranking de similaridade.
  - Refatoração completa do sistema de filtragem e taxonomia canônica (`canonical_taxonomy.py` + `sync_canonical_facets_and_providers.py`): `31` categorias unificadas em PT-BR, `25` streamings hidratados via TMDB `/3/discover` (`BR`/`US`), `8` formatos, `8` fontes de dados, controles UI de atualização Dual-SSOT (`ExplorerView.tsx` + `CatalogView.tsx`) e botão de limpeza/reset de filtros.

---

## 5. 🧭 Próximos Passos Evolutivos Recomendados

1. **Conectores Adicionais da Camada 1 (Trakt / Wikidata / JustWatch):** Expandir conectores externos de disponibilidade regional de streaming e listas editoriais públicas.
2. **Camada 3 — Radar Pessoal de Descoberta:** Alertas proativos baseados em diretores, criadores e atores favoritos do usuário quando novas obras entram no calendário de lançamentos.
3. **Player/Streamer Web Integrado para Mídia Local SMB:** Transcodificação leve sob demanda ou reprodução direta de arquivos mapeados em `LocalMediaRecord`.
