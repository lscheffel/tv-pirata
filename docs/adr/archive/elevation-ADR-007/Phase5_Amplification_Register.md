# Phase 5 — Amplification Register: ADR-007

## 1. Amplificações Arquiteturais Aprovadas

Com base nas observações da Fase 2 e no confronto da Fase 4, a Solução Original (Alt A) é retida e amplificada com 5 garantias de endurecimento:

### AMP-01 (Completude & Integridade de Dados): Unique Constraint Composta
* **Adição:** No modelo `ReleaseNotificationRecord`, adicionar a restrição declarativa relacional:
  `__table_args__ = (UniqueConstraint("show_id", "season", "episode", name="uq_notification_episode"),)`
* **Garantia:** Impossibilidade matemática de registrar notificações repetidas para o mesmo episódio, mesmo sob reexecuções consecutivas ou concorrência assíncrona.

### AMP-02 (Resiliência & Anti-Colisão): Jitter Temporal no Polling
* **Adição:** No loop do `BackgroundSyncService`, aplicar jitter pseudo-aleatório no cálculo do próximo sono:
  `delay = base_interval * random.uniform(0.9, 1.1)`
* **Garantia:** Previne padrões periódicos fixos contra a API externa da EZTV e distribui suavemente a carga de rede.

### AMP-03 (Observabilidade Proporcional): Endpoint de Status do Agendador
* **Adição:** Rota `GET /api/notifications/scheduler-status` expondo:
  - `status`: `IDLE` | `RUNNING` | `BACKOFF` | `DISABLED`.
  - `last_run_at`: Timestamp ISO da última checagem.
  - `next_run_eta_seconds`: Segundos estimados para o próximo ciclo.
  - `last_releases_found`: Quantidade de releases analisados no último ciclo.
  - `last_notifications_created`: Novidades detectadas no último ciclo.
* **Garantia:** Visibilidade imediata do funcionamento interno para diagnósticos do usuário e UI.

### AMP-04 (Ergonomia & Governança de Configuração): Feature Toggle
* **Adição:** Parâmetro `ENABLE_AUTO_SYNC: bool = True` e `AUTO_SYNC_INTERVAL_MINUTES: int = 60` no ambiente.
* **Garantia:** Permite desativar instantaneamente o agendador em ambientes de teste de integração sem afetar o servidor.

### AMP-05 (Hardening de Teardown): Timeout Guard no Lifespan
* **Adição:** No encerramento do FastAPI, envolver o cancelamento da task em `asyncio.wait_for(task, timeout=3.0)` com captura segura de `CancelledError`.
* **Garantia:** Cumprimento absoluto do *Zero Orphaned Servers Policy*.

