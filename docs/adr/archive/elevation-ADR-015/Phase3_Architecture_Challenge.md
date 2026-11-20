---
elevation_target: ADR-015
phase: 3
title: "Desafio Arquitetural & Exploração do Espaço de Design"
status: COMPLETED
language: PT-BR
---

# Fase 3 — Desafio Arquitetural (`ADR-015`)

1. **`Alt_A_Disconnected_CLI_Scripts` (`4.95`):** Manter scripts manuais separados (`imdb-metadata-catalog.py`, `eztv-metadata-catalog.py`) e sync de página 1 na UI sem cursor persistente e sem cascata de 6 degraus.
2. **`Alt_B_Eager_Full_Payload_Monolith` (`6.00`):** Baixar todos os milhões de magnet links estáticos na Fase 1 dentro de chamadas HTTP síncronas bloqueantes.
3. **`Alt_C_Unified_3Pillar_Resumable_Waterfall` (`9.51` — Vencedora):** Orquestrador cooperativo dos **3 Pilares de Hidratação** com `SmartBootstrapDetector` (`BOOTSTRAP` $\leftrightarrow$ `DELTA`), cursores persistentes de presença compacta na Fase 1B (`next_page` + `catalog_sweep_offset`), JIT na Fase 2 e Cascata Hierárquica de 6 Degraus (`IMDb -> TMDB -> TVMaze -> EZTV -> YIFY -> Outras Fontes`) na Fase 3.
