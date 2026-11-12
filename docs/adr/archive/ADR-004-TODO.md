---
id: ADR-004-TODO
title: "TODO: Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI"
adr_ref: ADR-004
created: "2026-11-11"
status: CONSOLIDATED
---

# Checklist de Implementação — ADR-004

- [x] Configurar conexão SQLite e gerador de sessão em `src/backend/core/database.py` (`DEC-017`).
- [x] Implementar entidades SQLModel em `src/backend/models/db.py` (`DEC-013`, `DEC-014`, `DEC-015`, `DEC-016`).
- [x] Implementar serviço de repositório `LibraryRepository` com operações atômicas de CRUD e cálculo de progresso.
- [x] Implementar serviço de rotas `/api/discovery` integrando `ResilientDiscoveryService`.
- [x] Implementar serviço de rotas `/api/library` para gerenciar séries salvas pelo usuário.
- [x] Implementar serviço de rotas `/api/watches` para marcação granular de episódios e temporadas.
- [x] Implementar serviço de rotas `/api/torrents` para listar links magnet da EZTV.
- [x] Implementar serviço de rotas `/api/collections` para tags e smart collections baseadas em JSON.
- [x] Montar a aplicação principal FastAPI em `src/backend/main.py` com CORS e tratamento global de erros (`DEC-018`).
- [x] Escrever suíte de testes de integração com `TestClient` cobrindo todas as rotas REST em memória (`tests/integration/test_api_endpoints.py`).
- [x] Executar e passar com 100% de aprovação no pre-commit Quality Gate (`make test` e `make lint`).
