---
elevation_target: ADR-014
phase: 2
title: "Auditoria Forense do Conjunto de Decisão ADR-014"
status: COMPLETED
language: PT-BR
---

# Fase 2 — Relatório de Auditoria Forense (`ADR-014`)

## 1. Achados da Auditoria e Mitigações Incorporadas

| ID | Severidade | Dimensão | Descrição do Achado | Mitigação no Conjunto Hardened (`Phase 7`) |
| :--- | :---: | :--- | :--- | :--- |
| `AUD-14.01` | `CRITICAL` | Robustness | Se a Etapa 2 (JIT no Modal) deletar releases antes do retorno HTTP 200 da fonte, timeouts transitórios destruiriam o cache local do título. | Incorporada transação **`Replace-on-Success` (`RT14-01`)**: só substitui/poda releases antigos de `(source_key, imdb_id)` quando `diag.status == "ok"` e há payload válido. |
| `AUD-14.02` | `MAJOR` | Performance | Fazer queries unitárias `N+1` em `mainstream.db` para cada card listado em `GET /api/sources/catalog` degradaria a paginação. | Incorporado **Batch Sovereign Join (`RT14-02`)**: 1 única query indexada `WHERE imdb_id IN (...)` por página (`<= 24` itens, `< 3ms`). |
| `AUD-14.03` | `MAJOR` | Efficiency | Disparar JIT no YTS ao abrir uma série de TV ou no EZTV ao abrir um filme gera requisições HTTP inúteis. | Incorporado **Roteamento Inteligente por Formato (`RT14-03`)**: filtra provedores por `media_types` (`movie` vs `tv_show`). |
| `AUD-14.04` | `MINOR` | Compatibility | Bancos `data/sources.db` existentes já possuem a linha `yify` com `base_url="https://yts.mx/api/v2/list_movies.json"`. | Incorporada migração idempotente em `ensure_sources_registered()` atualizando `yify.base_url` para `https://movies-api.accel.li/api/v2/list_movies.json` e semeando `tgx`, `nyaasi`, `bitsearch`, `glodls`. |
