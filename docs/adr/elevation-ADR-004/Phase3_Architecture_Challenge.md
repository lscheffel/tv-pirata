# Phase 3: Desafio Arquitetural & Espaço de Design — ADR-004

## 1. Alternativas Competidoras Exploradas

### Alternativa A (Original - SQLModel Relacional com SQLite em Arquivo Único)
Modelagem normalizada com chaves estrangeiras (`ShowRecord` -> `SeasonRecord` -> `EpisodeRecord`), tabelas satélite (`EpisodeWatchRecord`, `LocalMediaRecord`) e injeção de sessão via `Session(engine)` do SQLModel.

### Alternativa B (Document Store em SQLite com Tabelas JSON)
Armazenar cada show como um documento JSON completo dentro de uma tabela `shows_json` do SQLite usando funções nativas do SQLite JSON1.
- *Desafio Adversarial:* Atualizar um único episódio como assistido exigiria reescrever ou mutar todo o documento JSON, gerando risco de concorrência e dificultando consultas agregadas globais (ex: "quantos episódios assisti este mês?").

### Alternativa C (ORM Tradicional com SQLAlchemy Core + Alembic)
Separar modelos SQLAlchemy imperativos e esquemas Pydantic independentes.
- *Desafio Adversarial:* Redundância de código (dupla declaração de todos os atributos) para uma aplicação de escopo pessoal doméstico, violando o princípio DRY sem ganho mensurável.

## 2. Veredito do Desafio
A **Alternativa A (SQLModel)** é a solução ideal: elimina duplicações entre validação e persistência e garante integridade referencial relacional estrita.
