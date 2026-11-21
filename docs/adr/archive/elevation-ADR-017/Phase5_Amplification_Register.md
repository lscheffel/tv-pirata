---
adr_ref: ADR-017
phase: 5
title: "Phase 5 — Amplification Register"
language: PT-BR
---

# Phase 5: Registro de Amplificações (`AMP-01`..`AMP-04`)

1. **`AMP-01` (Robustez — Fronteira Estrita `Prepare -> Fan-out HTTP -> Fan-in DB`):** Nenhuma chamada a `Session` ocorre dentro de `asyncio.gather`, eliminando qualquer risco de contenção ou erro de transação entre as lanes `Fontes` e `Metadados`.
2. **`AMP-02` (Performance — Propagação Opcional de `AsyncClient` Keep-Alive):** Assinaturas `client: Optional[httpx.AsyncClient] = None` permitem reuso de pool TLS sem quebrar chamadas legadas ou mocks `respx`.
3. **`AMP-03` (Operabilidade — Sidecar `--workers 4` em CLI):** `make run-sidecar` sobe com `--workers 4` em processo dedicado, enquanto `EmbeddedSidecarManager` permanece non-blocking in-process.
4. **`AMP-04` (Completude — Guarda de Duplicatas em `recent`):** `mode="baseline"` com `start_page > 1` e `releases_indexed == 0` transiciona automaticamente para `sweep` mesmo quando o provedor retorna HTTP 200 com itens repetidos.
