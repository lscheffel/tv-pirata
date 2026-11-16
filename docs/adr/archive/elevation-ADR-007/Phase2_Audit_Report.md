# Phase 2 — Decision Set Forensic Audit: ADR-007

## 1. Executive Audit Summary

O Decision Set proposto em ADR-007 (`ADR-007.md`, `ADR-007-BP.md`, `ADR-007-TODO.md`, `ADR-007-PI.md`) foi submetido a cross-examination forense contra o Modelo Independente do Problema (Fase 1).

* **Veredito Inicial:** **APROVADO COM AMPLIFICAÇÕES (QUALIDADE: 8.8/10)**.
* **Pontos Fortes:** Aderência estrita à política de zero dependências pesadas (`asyncio.create_task` nativo no lifespan), separação em camadas bem articulada e preocupação explícita com o cancelamento cooperativo.
* **Apontamentos de Auditoria Identificados:** 3 Observações e 1 Vulnerabilidade Menor.

---

## 2. Apontamentos Forenses por Dimensão

### OBS-01 (Robustez): Falta de Índice Único Composto no SQLite
* *Constatação:* O modelo `ReleaseNotificationRecord` no Blueprint possui índices individuais (`show_id`, `season`, `episode`), mas não define uma `UniqueConstraint("show_id", "season", "episode", name="uq_notification_episode")`.
* *Risco:* Em caso de corrida ou re-sincronização rápida, o banco dependeria unicamente de lógica em código para garantir a idempotência, arriscando duplicidade no banco relacional sob condições de concorrência.
* *Ação de Elevação:* Adicionar explicitamente `UniqueConstraint` nos metadados do SQLModel.

### OBS-02 (Resiliência): Intervalo Fixo vs Jitter Temporal
* *Constatação:* Um polling com intervalo fixo de 60 minutos exatos sem jitter pode colidir repetidamente com picos de carga ou bloqueios temporários de rota.
* *Ação de Elevação:* Introduzir jitter pseudo-aleatório ($\pm 10\%$) no tempo de espera do loop assíncrono para suavizar requisições.

### OBS-03 (Operabilidade): Ausência de Status de Saúde do Worker na API
* *Constatação:* O usuário e o frontend não têm como inspecionar se o agendador está vivo, quando foi a última checagem e qual o resultado do último ciclo.
* *Ação de Elevação:* Adicionar endpoint de telemetria `/api/notifications/status` com timestamp da última execução, status (`IDLE`, `SYNCING`, `BACKOFF`) e total de eventos gerados.

