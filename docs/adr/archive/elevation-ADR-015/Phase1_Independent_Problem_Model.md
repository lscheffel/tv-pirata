---
elevation_target: ADR-015
phase: 1
title: "Reconstrução Independente do Problema a partir de Primeiros Princípios"
status: COMPLETED
language: PT-BR
---

# Fase 1 — Modelo Independente do Problema (`ADR-015`)

## 1. Declaração do Problema (First-Principles Problem Statement)
Uma plataforma audiovisual **Discovery-First** sobre arquitetura Dual-SSOT (`data/mainstream.db` com `279.362` obras canônicas e `data/sources.db` com indexadores externos pluggables) precisa operar de forma autônoma tanto em **instalações limpas (Zero-State Distribution)** quanto em **bases já populadas (Warm Database)** por meio de **3 Pilares de Hidratação com Checkpoints (`--resume`)**:
1. **Pilar 1 (População Estrutural Completa de Presença $\rightarrow$ Auto-Delta + Poda):** Descobrir e indexar exaustivamente quais obras do catálogo canônico possuem mídia em cada fonte (`EZTV`, `YTS 78.565 filmes`, `Sidecar :8009` `TGx`, `Nyaa`, `BitSearch`, `GloDLS`) via cursores persistentes (`next_page`, `catalog_sweep_offset`), chaveando automaticamente cada fonte concluída para **`Modo Delta Incremental + Poda`**.
2. **Pilar 2 (Hidratação Semi-Efêmera Just-in-Time no Clique):** Manter o índice da Fase 1 leve (`1 registro compacto de presença por título/fonte`) e hidratar torrents, magnets com 10 trackers oficiais, seeds e peers exclusivamente no clique do card (`TorrentModal.tsx`) ou para itens da `Minha Biblioteca`.
3. **Pilar 3 (Enriquecimento Canônico em Cascata Hierárquica de 6 Degraus):** Preencher capas (`poster_url`) e sinopses bilíngues (`synopsis_ptbr` e `synopsis` `EN-US`) faltantes cruzando os provedores na ordem hierárquica estrita: **`1. IMDb` $\rightarrow$ `2. TMDB` $\rightarrow$ `3. TVMaze` $\rightarrow$ `4. EZTV` $\rightarrow$ `5. YIFY/YTS` $\rightarrow$ `6. Outras Fontes Abertas (Wikidata Batch SPARQL P345 + Wikipédia PT/EN & Jikan v4)`**.

## 2. Invariantes Rígidos (Hard Invariants)
- **INV-15.01 (Gatilho Inteligente `BOOTSTRAP` $\leftrightarrow$ `DELTA`):** Nunca forçar re-bootstrap de catálogos já maduros (`IMDb >= 250k`, `EZTV >= 500`), mas iniciar automaticamente o bootstrap completo quando o banco estiver vazio na distribuição do app.
- **INV-15.02 (Hierarquia Canônica de 6 Degraus & Regra Bilíngue):** Preservar e preencher tanto `synopsis_ptbr` (PT-BR) quanto `synopsis` (EN-US) e `poster_url` respeitando a precedência `IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes`.
- **INV-15.03 (Zero Processos Órfãos & Checkpoints Atômicos):** O worker de background deve commitar em lotes curtos (`<= 50` registros) sob SQLite WAL e encerrar cooperativamente em `<= 3.0s` no shutdown do FastAPI.
