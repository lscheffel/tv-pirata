# ADR Index

> Índice gerado automaticamente pelo motor de auditoria da skill `adr-archive`.

| ADR | Título | Arquivada | Progresso | Implementação | Dependências | Janitor Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| ADR-001 | Arquitetura Fundamental do TV Pirata (Descoberta, Controle e SMB) | Sim | 6/6 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-002 | Provedores de Descoberta, Fallback Resiliente e Gestão de Mídia (Schema v1) | Sim | 7/7 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-003 | Implementação do Contrato Unificado, Provedores com Fallback e EZTV | Sim | 10/10 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-004 | Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI | Sim | 11/11 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-005 | Frontend Cinemático SPA (Vite + React + Tailwind), Design System OLED-Safe e Experiência de Streaming | Sim | 12/12 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-006 | Catálogo Local Persistente da EZTV, Motor de Ingestão/Indexação P2P e Descoberta Baseada em Mídia Real | Sim | 12/12 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-007 | Background Auto-Sync, Agendamento Assíncrono Periódico e Notificador de Novos Lançamentos para Séries da Biblioteca | Sim | 12/12 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-008 | Fundação do Audiovisual Discovery Core (Camada 1): Domínio Canônico Multi-Formato, Resolução de Identidade com Procedência, Federação de Fontes e Motor de Descoberta Avançada | Sim | 10/10 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-009 | Separação de Bases (tv_pirata.db vs eztv_metadata.db) + Entrelaçamento EZTV | Sim | 7/7 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-010 | ADR-010: Otimização de Desempenho de Leitura Dual-SQLite, Estatísticas Materializadas, Cache Escopado por Engine e FTS5 | Sim | 21/21 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-011 | ADR-011: Consolidação Dual-SSOT (`data/mainstream.db` vs `data/sources.db`), IMDb como Âncora Universal (279k+ Títulos / 4.5M+ Episódios) e Motor SQL Pushdown | Sim | 16/16 | CONSOLIDADA | - | ARCHIVED_OK |
| ADR-012 | Experiência Unificada de Exploração, Camada Multi-Fonte de Dados, Central Status/Sync/Config e ShowCard Interativo | Sim | 18/18 | CONSOLIDADA | ADR-008, ADR-009, ADR-010, ADR-011 | ARCHIVED_OK |
| ADR-013 | Sistema Extensível de Plugins para Fontes Externas (Adapters 1:N, Torrent-Api-py, Torznab, Lazy-Cache & Challenge Manual) | Sim | 16/16 | CONSOLIDADA | ADR-011, ADR-012 | ARCHIVED_OK |
| ADR-014 | Alinhamento Canônico com sources-apis.md (YTS movies-api.accel.li & EZTV), Curadoria Torrent-Api-py (12 Sites), Sincronia Bipartida em 2 Etapas e Sync Command Deck UI/UX | Sim | 16/16 | CONSOLIDADA | ADR-011, ADR-012, ADR-013 | ARCHIVED_OK |
| ADR-015 | Motor Unificado dos 3 Pilares de Hidratação com Checkpoints (--resume), Gatilho Inteligente de Maturidade (Bootstrap <-> Delta) e Cascata Hierárquica de 6 Degraus (IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes) | Sim | 16/16 | CONSOLIDADA | ADR-011, ADR-012, ADR-013, ADR-014 | ARCHIVED_OK |
| ADR-016 | Refatoração UI/UX das Configurações (Master-Detail IDE), Linguagem Humana e Telemetria Viva (Velocidade, ETA e Feed de Atividade) | Sim | 12/12 | CONSOLIDADA | ADR-012, ADR-013, ADR-014, ADR-015 | ARCHIVED_OK |
| ADR-017 | Paralelismo Bifurcado (Fan-out HTTP com Semáforos por Domínio -> Fan-in SQLite) & Correção de Exaustão 422 do Sidecar | Sim | 12/12 | CONSOLIDADA | ADR-014, ADR-015, ADR-016 | ARCHIVED_OK |
