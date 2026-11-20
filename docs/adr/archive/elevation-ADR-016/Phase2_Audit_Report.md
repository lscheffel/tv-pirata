---
adr_ref: ADR-016
phase: 2
title: "Phase 2 — Decision Set Forensic Audit"
language: PT-BR
---

# Phase 2: Auditoria Forense do Decision Set (`ADR-016`)

| ID | Achado | Severidade | Recomendação |
| :--- | :--- | :---: | :--- |
| `AUD-01` | Se `get_status()` depender de commit no `sync_state` do SQLite a cada item dentro de `run_single_step`, pode ocorrer contenção de leitura/escrita ou atraso na exibição do item atual. | `MAJOR` | Manter `current_stage`, `current_target`, `rate_per_minute`, `eta_seconds` e `recent_events` em estrutura **em memória** atualizada instantaneamente durante o passo, reservando o SQLite apenas para checkpoints de página/lote. |
| `AUD-02` | O filtro `"Filtrar ajustes..."` na barra lateral precisa encontrar termos que vivem *dentro* dos painéis (ex.: `"cache"`, `"selo"`, `"agendador"`), não apenas os 4 nomes de categoria. | `MINOR` | Associar palavras-chave de busca a cada categoria e exibir atalhos diretos quando houver termo digitado. |
| `AUD-03` | Polling de `1.0s` pode continuar rodando se a aba do navegador estiver em segundo plano. | `OBSERVATION` | Pausar/reduzir polling quando `document.hidden` ou `state !== "RUNNING"`. |
