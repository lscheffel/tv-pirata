---
adr_ref: ADR-016
phase: 3
title: "Phase 3 — Architecture Challenge"
language: PT-BR
---

# Phase 3: Desafio Arquitetural & Alternativas

- **`Alt_A_Cosmetic_Text_Only`:** Apenas renomear textos no `StatusConfigView.tsx` atual (`1.066+` linhas). Mantém o monólito vertical, os 4 botões conflitantes e a ausência de velocidade/ETA.
- **`Alt_B_MasterDetail_IDE_Live_Telemetry`:** Layout Master-Detail em 2 colunas (`SettingsSidebar` + 4 painéis coesos) + linguagem 100% humana + telemetria viva em memória no `HydrationOrchestratorService` (`current_target`, `rate_per_minute`, `eta_seconds`, `recent_events`) exposta em `/api/explore/hydration/status` com polling de `1.0s` apenas enquanto `RUNNING`.
- **`Alt_C_Heavy_WebSocket_SPA`:** Subir servidor WebSocket/pub-sub dedicado para logs em tempo real + router separado de configurações. Alto custo de complexidade para execução single-node local.
