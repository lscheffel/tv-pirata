---
elevation_target: ADR-015
phase: 2
title: "Auditoria Forense do Conjunto de Decisão ADR-015"
status: COMPLETED
language: PT-BR
---

# Fase 2 — Relatório de Auditoria Forense (`ADR-015`)

| ID | Severidade | Dimensão | Descrição do Achado | Mitigação no Conjunto Hardened (`Phase 7`) |
| :--- | :---: | :--- | :--- | :--- |
| `AUD-15.01` | `CRITICAL` | State Machine | `256.004` linhas em `mainstream.db` estavam marcadas como `details_fetched = 1` (possuem capa), mas `188.311` delas tinham `synopsis_ptbr` e `synopsis` vazias. | Incorporada **Fila Bipartida Prioritária (`DEC-005`)**: Sub-Fila 3.1 (`poster_url IS NULL`) e Sub-Fila 3.2 (`poster_url IS NOT NULL AND (synopsis_ptbr IS NULL OR synopsis IS NULL)`), priorizando obras com mídia ativa e maior `rating_votes`. |
| `AUD-15.02` | `MAJOR` | Completeness | `75` séries em `data/sources.db` (`EZTVShow`) estavam com `guide_synced = -1` (sem capa/sinopse), embora suas contrapartes já existissem em `mainstream.db` ou no JSON-LD do IMDb. | Incorporado **Passo 0 (`Cross-DB Self-Healing` `DEC-004`/`DEC-005`)** copiando metadados entre `mainstream.db` e `EZTVShow` e aplicando a Cascata de 6 Degraus nas séries remanescentes. |
| `AUD-15.03` | `MAJOR` | Scalability | `YIFYSourceAdapter.sync()` reiniciava sempre em `page=1` e fazia 50 `SELECT`s por página. | Incorporado cursor persistente `next_page` (`1..1572`) + `Batch SELECT/UPSERT` de presença compacta (`< 15ms/página`). |
| `AUD-15.04` | `MAJOR` | Coverage | Indexadores do Sidecar (`tgx`, `nyaasi`, `bitsearch`, `glodls`) retornavam poucos títulos por lerem apenas 1 página de `/recent`. | Incorporada paginação multi-categoria/multi-página + **`Canonical Catalog Anchor Sweep`** com cursor `catalog_sweep_offset` guiado pelas obras mais populares de `mainstream.db`. |
