---
adr_ref: ADR-017
phase: 1
title: "Phase 1 — Independent Problem Model"
language: PT-BR
---

# Phase 1: Modelo Independente do Problema (`ADR-017`)

## 1. Declaração do Problema
O motor de hidratação (`HydrationOrchestratorService` + `CascadingMetadataEnricher` + `SourcesRegistryService`) sofre de dois limitantes estruturais:
1. **Bloqueio de Paginação (`422`):** O endpoint `/api/v1/recent` do sidecar impõe `le=20` e lança HTTP `422` acima da página `20`, impedindo o avanço automático de `nyaasi` e `bitsearch` para `sweep_canonical_catalog_presence`.
2. **Latência Sequencial:** Requisições HTTP externas ocorrem uma após a outra enquanto conexões TLS são recriadas, desperdiçando vazão em APIs rápidas (`TMDB`, `YTS`) ao mesmo tempo em que `SQLite` não tolera escrita concorrente entre múltiplas `Session`s.

## 2. Invariantes & Restrições
- **Invariante SQLite Single-Writer:** Nenhuma corrotina paralela pode mutar `Session` ou chamar `commit()` durante o `asyncio.gather`.
- **Invariante Event-Loop:** Semáforos `asyncio.Semaphore` devem ser isolados por *event loop* (`WeakKeyDictionary`).
- **Invariante Anti-Ban:** Respeitar tetos por domínio (`tmdb<=8`, `yify/tgx/glodls<=4`, `nyaasi/bitsearch/imdb/tvmaze/jikan<=2`).
