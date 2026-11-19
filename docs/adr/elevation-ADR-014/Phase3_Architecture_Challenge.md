---
elevation_target: ADR-014
phase: 3
title: "Desafio Arquitetural & Exploração do Espaço de Design"
status: COMPLETED
language: PT-BR
---

# Fase 3 — Desafio Arquitetural (`ADR-014`)

## Alternativas Competidoras Formuladas

1. **`Alt_A_Monolithic_Static_Sync` (Baseline Anterior):**
   - Sincronia única `sync(pages=5)` sem distinção entre Baseline, Incremental, Library ou Prune; sem Batch Join com `mainstream.db`; `yts.mx` legado apenas com `list_movies.json` e 4 trackers; `1337x` como único default do `Torrent-Api-py`.
2. **`Alt_B_Pure_Stateless_Live_Proxy` (Zero Persistência em `sources.db`):**
   - Consultar todas as APIs externas exclusivamente em tempo real a cada busca/clique, sem Etapa 1 persistida em `sources.db`.
   - *Falha Crítica:* Impede a filtragem SQL Pushdown por `data_sources` e a exibição instantânea de `MediaBadge` nos `279.362` cards da aba `Explorar`.
3. **`Alt_C_Bipartite_Sovereign_SyncDeck` (Arquitetura Proposta & Amplificada):**
   - **Etapa 1 (Índice Estrutural Leve + Match Canônico + Poda de Obsoletos)** + **Etapa 2 (Hidratação JIT SWR com `Replace-on-Success`, Roteamento por Formato e Inteligência YTS)** + **Batch Join Soberano com `mainstream.db`** + **Sync Command Deck** com Onda Card a Card e Catálogo de 12 Provedores `Torrent-Api-py`.
