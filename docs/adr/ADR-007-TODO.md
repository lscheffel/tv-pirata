# TODO: ADR-007 — Background Auto-Sync, Agendamento Assíncrono e Notificador de Novos Lançamentos

- [x] `T01`: Criar o modelo relacional `ReleaseNotificationRecord` em `src/backend/models/db.py` e exportar em `src/backend/models/__init__.py`.
- [x] `T02`: Atualizar `init_db()` em `src/backend/core/database.py` para registrar a nova tabela no SQLite.
- [x] `T03`: Implementar repositório `NotificationRepository` em `src/backend/repositories/notification.py` com métodos de listagem, contagem e dispensa.
- [x] `T04`: Implementar o serviço de reconciliação de novos episódios no `EZTVIndexerService` ou classe auxiliar `NotificationMatcher`.
- [x] `T05`: Desenvolver o `BackgroundSyncService` em `src/backend/services/scheduler.py` com loop assíncrono nativo, tratamento de cancelamento e backoff.
- [x] `T06`: Integrar o `BackgroundSyncService` no evento de `lifespan` do FastAPI em `src/backend/main.py` garantindo inicialização limpa e teardown gracioso.
- [x] `T07`: Criar o router REST `/api/notifications` em `src/backend/api/notifications.py` e registrá-lo no `main.py`.
- [x] `T08`: Adicionar testes unitários para o `BackgroundSyncService` e cancelamento cooperativo em `tests/unit/test_scheduler.py`.
- [x] `T09`: Adicionar testes de integração para as rotas de notificação em `tests/integration/test_notifications_api.py`.
- [x] `T10`: Atualizar os contratos do frontend em `src/frontend/src/types.ts` e métodos em `src/frontend/src/services/api.ts`.
- [x] `T11`: Atualizar a interface (`Navbar.tsx` e `LibraryView.tsx`) para exibir badge de notificações não lidas e indicadores nos cards.
- [x] `T12`: Executar suíte de validação completa (`make test`, `make lint` e `./scripts/quality_gate.sh`) garantindo zero regressões.
