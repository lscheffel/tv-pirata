---
elevation_target: ADR-014
phase: 1
title: "Reconstrução Independente do Problema a partir de Primeiros Princípios"
status: COMPLETED
language: PT-BR
---

# Fase 1 — Modelo Independente do Problema (`ADR-014`)

## 1. Declaração do Problema (First-Principles Problem Statement)
Em uma plataforma **Discovery-First** com arquitetura Dual-SSOT (`data/mainstream.db` soberano com `279.362` obras canônicas vs. `data/sources.db` com indexadores P2P/externos), os provedores externos fornecem dados **semi-efêmeros** (hashes, magnets, seeds, peers, links). O sistema precisa:
1. Cumprir estritamente as especificações oficiais documentadas em `sources-apis.md` (YTS v2 `https://movies-api.accel.li/api/v2/` com 4 endpoints e 10 trackers oficiais; EZTV `https://eztvx.to/api/get-torrents?limit=100` + lookup numérico `?imdb_id=<num>` + RSS `https://myrss.org/eztv` + `https://eztvstatus.org/`);
2. Cobrir todo o catálogo de 12 provedores do sidecar `Ryuk-me/Torrent-Api-py` (`tgx`, `nyaasi`, `bitsearch`, `glodls`, `magnetdl`, `limetorrent`, `torlock`, `kickass`, `zooqle`, `yts`, `1337x`, `piratebay`) com suporte dual (`/recent` + `/search`);
3. Operar sob **Sincronia Bipartida em 2 Etapas**:
   - **Etapa 1 (Presença Estrutural + Poda):** Descobrir e indexar quais títulos de `mainstream.db` possuem mídia ativa em cada fonte, podando releases mortos (`0 seeds`);
   - **Etapa 2 (Hidratação Efêmera JIT no Card/Modal):** Exibir o cache local em `0ms` (`Stale-While-Revalidate`) e hidratar payloads vivos sob demanda com transação atômica `Replace-on-Success`.

## 2. Invariantes Rígidos (Hard Invariants)
- **INV-14.01 (Soberania da Camada 1):** `data/mainstream.db` é a única fonte de verdade de metadados ricos (pôster, sinopse PT-BR, nota IMDb, gêneros, streamings). Cards em `Fontes de Dados` (`SourcesView.tsx`) devem ser enriquecidos via **Batch Join Soberano** com `mainstream.db`.
- **INV-14.02 (Isolamento `eztv_metadata`):** `eztv_metadata.tables` deve continuar contendo estritamente `{"shows", "episodes_catalog"}`.
- **INV-14.03 (Segurança `Replace-on-Success` na Etapa 2):** Falhas transitórias de rede na Etapa 2 nunca podem apagar os releases locais existentes da Etapa 1.
- **INV-14.04 (Zero Dependências Extras de Runtime):** O parsing de RSS (`myrss.org/eztv`) e a construção de magnets devem usar exclusivamente a stdlib (`xml.etree.ElementTree`, `urllib.parse.quote_plus`) e `httpx`.
