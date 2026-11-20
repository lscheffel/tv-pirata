---
adr_ref: ADR-016
phase: 5
title: "Phase 5 — Amplification Register"
language: PT-BR
---

# Phase 5: Registro de Amplificações (`AMP-01`..`AMP-04`)

1. **`AMP-01` (Completude — Índice de Busca na Barra Lateral):** O campo `"Filtrar ajustes..."` indexa palavras-chave de todas as 4 categorias (`cache`, `agendador`, `selo`, `eta`, `sinopse`, `yts`, `eztv`), permitindo salto direto para o painel correto.
2. **`AMP-02` (Robustez — Telemetria em Memória Lock-Free para Leitura):** `current_stage`, `current_target`, `items_processed_in_run`, `rate_per_minute`, `eta_seconds` e `recent_events` (`deque(maxlen=15)`) são mantidos em memória no `HydrationOrchestratorService`, permitindo leitura instantânea (`0ms`) por `GET /api/explore/hydration/status` mesmo no meio de um passo longo sem contenção no SQLite.
3. **`AMP-03` (Operabilidade — Erros Legíveis & Polling Inteligente):** Mensagens de atividade traduzidas para português claro e polling de `1.0s` ativo somente enquanto `state === "RUNNING"` e aba visível.
4. **`AMP-04` (Arquitetura UI — Edição Focada de Fontes):** Edição e criação de fontes em painel dedicado/modal limpo em `SourcesProvidersPanel.tsx` em vez de formulários inline pesados.
