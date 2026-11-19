---
elevation_target: ADR-013
phase: 5
title: "Registro de Amplificação de Solução (5 Dimensões)"
status: COMPLETED
language: PT-BR
---

# Fase 5 — Registro de Amplificação (5 Categorias Canônicas)

1. **Completude (`AMP-COMP-01`):** Remoção total de listas hardcoded em `canonical_taxonomy.py`, `discovery_engine.py` e `ExplorerView.tsx`, alimentando dinamicamente chips e contadores a partir de `external_sources` + agregação `"Com Mídia"`.
2. **Robustez (`AMP-ROB-01` / `AMP-ROB-02`):**
   - *Circuit breaker* em **2 níveis** (instância individual vs. host base do sidecar compartilhado).
   - Fallback offline transparente: releases expirados (`> 24h`) continuam utilizáveis se o refresh ao vivo falhar ou estiver em cooldown.
   - Isolamento de `import` durante `pkgutil` autodiscovery (`try/except` por módulo de plugin).
3. **Capacidade (`AMP-CAP-01` / `AMP-CAP-02`):**
   - Suporte polimórfico nativo ao **`Torrent-Api-py`** (expondo presets `1337x`, `tgx`, `nyaasi`, `piratebay` via `config_json`) e ao protocolo **`Torznab`** (`Prowlarr` / `Jackett`), além de template **`unique_web_source`**.
   - Refino manual de query dentro do `TorrentModal.tsx` quando o match automático for `0.60–0.84` ou zero.
4. **Arquitetura (`AMP-ARC-01` / `AMP-ARC-02`):**
   - Separação estrita **Adapter (`1`) ↔ Instância (`N`)**, preservando `eztv_metadata` intacta.
   - Sentinel preservation para campos `secret=True` em atualizações parciais (`PATCH /api/sources/{key}`), evitando sobrescrever API keys mascaradas (`RT13-02`).
5. **Operacional (`AMP-OPS-01` / `AMP-OPS-02`):**
   - Botão **"Testar Conexão"** (`POST /api/sources/{key}/test`) e CRUD **"+ Adicionar Fonte"** em `StatusConfigView.tsx` renderizado dinamicamente via JSON Schema do `config_schema` do adapter.
   - Banner explícito `44×44px` de CAPTCHA/Challenge no `TorrentModal.tsx` com `challenge_url` sanitizada (`http`/`https`) + botão **"Tentar Novamente"**.
