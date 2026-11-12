# Estado Atual do Workspace (STATE.md)

> **Persistent Agent Memory & Repository State**  
> Última auditoria e reconciliação: 2026-11-11

---

## 1. 📍 Contexto e Fase Ativa

- **Branch Atual:** `main`
- **Fase de Ciclo de Vida:** Planejamento e Elevação de Persistência & API REST (ADR-004 SOTA Emergencial Ativa)
- **Status do Build / Quality Gate:** PASSING (13/13 testes aprovados, Ruff aprovado)

---

## 2. 🏛️ Ledger Consolidado de ADRs

| ID | Título | Status | Tarefas | Implementação | Registrado |
|:---|:---|:---:|:---:|:---:|:---:|
| **ADR-001** | [Arquitetura Fundamental do TV Pirata](./docs/adr/archive/ADR-001.md) | ACCEPTED | 6/6 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-002** | [Provedores de Descoberta, Fallback Resiliente e Gestão de Mídia](./docs/adr/archive/ADR-002.md) | ACCEPTED | 7/7 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-003** | [Implementação do Contrato Unificado e EZTV](./docs/adr/archive/ADR-003.md) | ACCEPTED | 10/10 (100%) | CONSOLIDADA | 2026-11-11 |
| **ADR-004** | [Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI](./docs/adr/ADR-004.md) | PROPOSED | 0/11 (0%) | PENDENTE | 2026-11-11 |

---

## 3. 💳 Registro de Débitos Técnicos (Tech Debt Registry)

| ID | Título | Severidade | Status | ADR Mitigadora |
|:---|:---|:---:|:---:|:---:|
| `TD-2026-001` | Ausência de cache em disco local para requisições de Trending | Baixa | IN_PROGRESS | ADR-004 |
| `TD-2026-002` | Scanner heurístico de arquivos SMB (scene_parser.py) e tabela local_media pendentes | Média | IN_PROGRESS | ADR-004 |
| `TD-2026-003` | Ausência de persistência relacional física para biblioteca pessoal e histórico de assistidos | Alta | IN_PROGRESS | ADR-004 |
| `TD-2026-004` | Ausência de servidor web FastAPI com rotas REST expostas para o frontend | Alta | IN_PROGRESS | ADR-004 |

---

## 4. 🧭 Próximos Passos Imediatos (Execução da ADR-004)

1. Implementar `src/backend/core/database.py` com engine SQLite e sessão atômica (`get_session`).
2. Implementar os modelos relacionais SQLModel em `src/backend/models/db.py` (`ShowRecord`, `SeasonRecord`, `EpisodeRecord`, `EpisodeWatchRecord`, `LocalMediaRecord`, `TagRecord`, `CollectionRecord`).
3. Criar os roteadores REST do FastAPI em `src/backend/api/` e montar `src/backend/main.py`.
4. Desenvolver a suíte de testes de integração com `TestClient` para as rotas e regras de negócio.
