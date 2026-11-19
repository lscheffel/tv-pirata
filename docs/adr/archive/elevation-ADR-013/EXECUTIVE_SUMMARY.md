---
elevation_target: ADR-013
title: "Resumo Executivo da Elevação Arquitetural — ADR-013"
status: CERTIFIED
language: PT-BR
---

# Resumo Executivo — Elevação Arquitetural `ADR-013`

- **Alvo:** Conjunto `ADR-013` (*Sistema Extensível de Plugins para Fontes Externas*).
- **Design Doc Base:** [2026-11-19-plugins-fontes-externas-design.md](../../plans/2026-11-19-plugins-fontes-externas-design.md).
- **Complexidade & Risco:** `DCI = 7` (**Tier 2**) | `Blast Radius = 8.5` (**CRITICAL — One-Way Door**).
- **Veredito:** **`KEEP + AMPLIFY`** → **`Alt_C_Adapter_1N_Sidecar_LazyCache`** (**`9.38`** vs. `6.75` e `6.67`, margem `+2.63` via `matrix_scorer.py`).
- **Principais Pilares:** Autodiscovery `1:N` (`BaseSourceAdapter` ↔ `ExternalSourceRecord`), adapters HTTP enxutos (`eztv`, `yify`, `torrent_api_py`, `torznab`, `unique_web`) sem parsers HTML no core, *circuit breaker* em 2 níveis, *Lazy-Cache* 24h + threshold `>= 0.85`, diagnóstico CAPTCHA/Challenge com abertura manual segura (`44×44px`), proteção URI/segredos Zero-Trust, deshardcoding total na UI/Discovery e suíte contratual universal `pytest` (`16` tarefas em `ADR-013-TODO.md`).
