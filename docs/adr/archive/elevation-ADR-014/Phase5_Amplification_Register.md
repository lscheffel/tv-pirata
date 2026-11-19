---
elevation_target: ADR-014
phase: 5
title: "Registro de Amplificações Arquiteturais"
status: COMPLETED
language: PT-BR
---

# Fase 5 — Registro de Amplificações (`ADR-014`)

1. **`AMP-14.01` (Completeness — Helper Universal `build_official_magnet`):** Além de construir os magnets do YTS (`movies-api.accel.li`) com `urllib.parse.quote_plus(dn)` e os 10 trackers oficiais de `sources-apis.md`, o helper também turbina qualquer magnet sem trackers retornado pelo `Torrent-Api-py` ou RSS da EZTV.
2. **`AMP-14.02` (Synergy — Batch Sovereign Join `sources.db` $\rightarrow$ `mainstream.db`):** Os cards da aba **Fontes de Dados** (`SourcesView.tsx`) deixam de depender de metadados parciais dos trackers e herdam automaticamente pôster, sinopse PT-BR, nota IMDb, status e plataformas de streaming da Camada 1 (`IMDbCatalogShow`), além de deduplicar por `imdb_id` no modo `"Todas as Fontes"`.
3. **`AMP-14.03` (Operability — 4 Modos de Ciclo de Vida na Etapa 1):** `POST /api/sources/sync` passa a suportar `incremental` (Delta + RSS + `/recent`), `baseline` (Top Seeds/Downloads + Qualidade + Nota), `library` (Sincronia Direcionada pela Biblioteca Pessoal) e `prune` (Garbage Collection de torrents mortos).
4. **`AMP-14.04` (UX Leverage — Faixa Inteligência YTS no `TorrentModal.tsx`):** Consome os 3 endpoints complementares de `movies-api.accel.li/api/v2/` (`movie_details.json`, `movie_suggestions.json`, `movie_parental_guides.json`) na Etapa 2 para exibir Guia Parental e 4 Sugestões Clicáveis dentro do modal.
