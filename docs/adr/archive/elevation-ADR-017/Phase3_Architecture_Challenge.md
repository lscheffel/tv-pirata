---
adr_ref: ADR-017
phase: 3
title: "Phase 3 — Architecture Challenge (Red/Blue Team)"
language: PT-BR
---

# Phase 3: Desafio Arquitetural Adversarial (`BR=7.75 CRITICAL`)

- **Red Team (Ataque à Concorrência):**
  - *"E se um provedor retornar `429` ou `Timeout` dentro do `asyncio.gather`?"* -> Sem `return_exceptions=True`, todo o lote falha e perde o trabalho dos demais provedores. Mitigado via `return_exceptions=True` + evento legível por fonte/obra.
  - *"E se `pytest` rodar testes consecutivos criando novos event loops?"* -> Semáforos globais no módulo causam `RuntimeError: is bound to a different event loop`. Mitigado com `WeakKeyDictionary[AbstractEventLoop, dict[str, asyncio.Semaphore]]`.
- **Alternativas Comparadas:**
  - `Alt_A_Sequential_Plus_MaxPageBump`: mantém execução sequencial (baixo ganho de throughput).
  - `Alt_B_Bifurcated_FanOut_DomainSem_FanIn`: **Fan-out HTTP paralelo com semáforos por domínio + Keep-Alive -> Fan-in SQLite único**.
  - `Alt_C_MultiProcess_WorkerPool_SQLiteLocks`: múltiplos processos/sessões escrevendo no SQLite em paralelo (risco de `database is locked`).
