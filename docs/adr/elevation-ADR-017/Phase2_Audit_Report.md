---
adr_ref: ADR-017
phase: 2
title: "Phase 2 — Decision Set Forensic Audit"
language: PT-BR
---

# Phase 2: Auditoria Forense (`ADR-017`)

| ID | Achado | Severidade | Mitigação / Amplificação |
| :--- | :--- | :---: | :--- |
| `AUD-01` | Em `run_single_step` (`scope == "all"`), se `Sources` e `Metadata` rodarem juntos, `cross_db_self_heal` (que lê `EZTVShow` em `sources_session`) e `sync_source` (que escreve `ExternalRelease` em `sources_session`) competiriam pela mesma `sources_session`. | `CRITICAL` | **`AMP-01` (Arquitetura 3-Fases Estrita):** Executar `Prepare DB` antes do `gather` (leitura de fila/configs), `Fan-out HTTP` puro dentro do `gather`, e `Fan-in DB` sequencial após o `gather`. |
| `AUD-02` | Se `httpx.AsyncClient` for fechado ou recriado por erro dentro de uma corrotina, ou se um sub-adaptador ignorar `client`, perde-se Keep-Alive. | `MAJOR` | **`AMP-02` (Client Opcional Propagado):** Injetar `client: Optional[httpx.AsyncClient] = None` opcional em `YIFYSourceAdapter`, `TorrentApiPySourceAdapter` e `CascadingMetadataEnricher`. |
| `AUD-03` | `EmbeddedSidecarManager` roda `uvicorn.Server` in-process no mesmo loop (suporta `async` concorrente nativo com `workers=1`, pois `workers=4` só se aplica a processo CLI `uvicorn --workers 4`). | `MINOR` | **`AMP-03` (Clarificação CLI vs In-Process):** Aplicar `--workers 4` em `make run-sidecar` no `Makefile`, mantendo `EmbeddedSidecarManager` assíncrono in-process protegido pelo semáforo `sidecar=4`. |
