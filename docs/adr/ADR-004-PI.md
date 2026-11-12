---
id: ADR-004-PI
title: "Plano de Implementação: Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI"
adr_ref: ADR-004
created: "2026-11-11"
status: PENDENTE
---

# Plano de Implementação (PI) — ADR-004

## Fase 1: Camada de Dados e Modelos Relacionais
- Criação de `src/backend/core/database.py` e utilitário `init_db`.
- Implementação de `ShowRecord`, `SeasonRecord`, `EpisodeRecord`, `EpisodeWatchRecord`, `LocalMediaRecord`, `TagRecord`, `ShowTagLink`, `CollectionRecord` em `src/backend/models/db.py`.
- Criação de testes unitários para persistência, relacionamentos em cascata e constraints no SQLite.

## Fase 2: Repositório & Regras de Negócio de Watchlist
- Implementação de métodos transacionais:
  - Adição atômica de `UnifiedShow` para `ShowRecord` (expandindo temporadas e episódios).
  - Alternância de `is_watched` no episódio e atualização de `watched_at`.
  - Marcação de temporada inteira com cálculo de progresso percentual.
  - Atualização de status de arquivo local sem remoção de registros.

## Fase 3: Roteadores REST & Servidor Web FastAPI
- Implementação dos módulos de rota em `src/backend/api/`.
- Configuração de `main.py` com `FastAPI`, documentação automática `/docs` (Swagger) e middleware de CORS.
- Implementação de suíte de testes com `TestClient` simulando requisições HTTP reais contra SQLite em memória.
- Validação com `make lint` e `make test`.
