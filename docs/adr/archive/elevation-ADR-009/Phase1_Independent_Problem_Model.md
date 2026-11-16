# Phase 1: Independent Problem Model — ADR-009

## Core Vector
- **Problema:** Separar fisicamente a base global multi-provedor (`data/tv_pirata.db`) da base dedicada do provedor EZTV (`data/eztv_metadata.db`, populada por `scripts/eztv-metadata-catalog.py`), mantendo o Catálogo EZTV (`/api/catalog/*`) alimentado por `eztv_metadata.db` e o Descobrir (`/api/explore/*`) enriquecido com disponibilidade EZTV.
- **Restrições Hard:**
  1. Preservar schema existente de `data/eztv_metadata.db` (`shows`, `episodes_catalog`) sem migração destrutiva.
  2. Não poluir `SQLModel.metadata` de `tv_pirata.db` com tabelas de `eztv_metadata.db`.
  3. Zero queries N+1 no cruzamento `/api/explore/works`.
  4. Testes `pytest` 100% herméticos via `app.dependency_overrides`.
- **Condições de Falha:** `OperationalError` se `eztv_metadata.db` estiver vazio; regressão nos endpoints `/api/catalog/*` usados por `CatalogView.tsx` e testes existentes.

