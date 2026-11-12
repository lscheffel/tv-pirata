# Estado Atual do Workspace (STATE.md)

> **Persistent Agent Memory & Repository State**  
> Última auditoria e reconciliação: 2026-11-12

---

## 1. 📍 Contexto e Fase Ativa

- **Branch Atual:** `main`
- **Fase de Ciclo de Vida:** Catálogo Físico EZTV + Background Auto-Sync & Notificador Concluídos (v0.5.0)
- **Status do Build / Quality Gate:** PASSING (47/47 testes aprovados, Ruff aprovado, Vite build aprovado)

---

## 2. 🏛️ Ledger Consolidado de ADRs

| ID | Título | Status | Tarefas | Implementação | Registrado |
|:---|:---|:---:|:---:|:---:|:---:|
| **ADR-001** | [Arquitetura Fundamental do TV Pirata](./docs/adr/archive/ADR-001.md) | ACCEPTED | 6/6 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-002** | [Provedores de Descoberta, Fallback Resiliente e Gestão de Mídia](./docs/adr/archive/ADR-002.md) | ACCEPTED | 7/7 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-003** | [Implementação do Contrato Unificado e EZTV](./docs/adr/archive/ADR-003.md) | ACCEPTED | 10/10 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-004** | [Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI](./docs/adr/archive/ADR-004.md) | ACCEPTED | 11/11 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-005** | [Frontend Cinemático SPA (Vite + React + Tailwind), Design System OLED-Safe](./docs/adr/ADR-005.md) | ACCEPTED | 12/12 (100%) | CONSOLIDADA | 2026-11-12 |
| **ADR-006** | [Catálogo Local Persistente da EZTV e Motor de Ingestão P2P](./docs/adr/ADR-006.md) | ACCEPTED | 12/12 (100%) | CONSOLIDADA | 2026-11-12 |
| **ADR-007** | [Background Auto-Sync e Notificador de Novos Lançamentos](./docs/adr/ADR-007.md) | ACCEPTED | 12/12 (100%) | CONSOLIDADA | 2026-11-12 |

---

## 3. 💳 Registro de Débitos Técnicos (Tech Debt Registry)

| ID | Título | Severidade | Status | ADR Mitigadora |
|:---|:---|:---:|:---:|:---:|
| `TD-2026-001` | Ausência de cache em disco local para requisições de Trending | Baixa | RESOLVIDO | ADR-004 |
| `TD-2026-002` | Scanner heurístico de arquivos SMB e tabela local_media pendentes | Média | RESOLVIDO | ADR-004 |
| `TD-2026-003` | Ausência de persistência relacional física para biblioteca pessoal e histórico de assistidos | Alta | RESOLVIDO | ADR-004 |
| `TD-2026-004` | Ausência de servidor web FastAPI com rotas REST expostas para o frontend | Alta | RESOLVIDO | ADR-004 |
| `TD-2026-005` | Ausência de frontend web cinematográfico para homelab | Alta | RESOLVIDO | ADR-005 |
| `TD-2026-006` | Descoberta abstrata desprovida de garantia física de sementes P2P | Alta | RESOLVIDO | ADR-006 |
| `TD-2026-007` | Ausência de reconciliação assíncrona periódica em segundo plano | Média | RESOLVIDO | ADR-007 |

---

## 4. 🧭 Próximos Passos Imediatos

1. Arquivar ADR-005, ADR-006 e ADR-007 via skill `adr-archive`.
2. Integrador qBittorrent / Transmission Web API para disparo direto de downloads a partir da UI.
3. Scanner heurístico e mapeamento de arquivos em disco / SMB (`LocalMediaRecord`).
