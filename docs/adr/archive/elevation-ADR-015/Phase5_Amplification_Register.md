---
elevation_target: ADR-015
phase: 5
title: "Registro de Amplificações Arquiteturais"
status: COMPLETED
language: PT-BR
---

# Fase 5 — Registro de Amplificações (`ADR-015`)

1. **`AMP-15.01` (`SmartBootstrapDetector` Zero-State vs Warm-State):** Detecta automaticamente se o app acabou de ser instalado com bancos zerados (`BOOTSTRAP`) ou se `IMDb` e `EZTV` já estão populados (`DELTA`), expondo gatilho de transição automática e manual.
2. **`AMP-15.02` (`Cross-DB Self-Healing` Bidirecional):** Cura instantaneamente as `75` séries órfãs da EZTV em `sources.db` cruzando com `mainstream.db` e a Cascata de 6 Degraus.
3. **`AMP-15.03` (`Canonical Catalog Anchor Sweep` para Sidecar `:8009`):** Supera o limite de 1 página dos feeds `/recent` usando as obras mais votadas de `mainstream.db` (Filmes, Séries e Animes) como âncoras de busca com cursor persistente `catalog_sweep_offset`.
4. **`AMP-15.04` (Extrator JSON-LD `<script type="application/ld+json">` do IMDb como Degrau 1):** Garante capa oficial e sinopse `EN-US` direto da fonte soberana quando ausentes no dump TSV inicial.
