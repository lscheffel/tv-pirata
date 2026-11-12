# Blueprint: ADR-007 — Background Auto-Sync, Agendamento Assíncrono e Notificador de Novos Lançamentos

## 1. Visão Arquitetural & Componentes

O subsistema de sincronização em segundo plano opera como um serviço embutido no ciclo de vida da aplicação FastAPI, acionado durante o evento de `lifespan`:

```mermaid
flowchart TD
    subgraph FastAPI Runtime
        LS[Lifespan Startup] --> W[BackgroundSyncWorker]
        W --> L[Polling Loop: asyncio.sleep]
        L --> SYNC[EZTV Ingester: Page 1]
        SYNC --> DB[(SQLite: data/tv_pirata.db)]
        DB --> MATCH[Matcher com ShowRecord]
        MATCH --> NOTIF[(ReleaseNotificationRecord)]
        LS_END[Lifespan Shutdown] --> CANCEL[Task.cancel + Teardown Gracioso]
    end

    subgraph Client Layer
        SPA[React SPA] -->|GET /api/notifications| API[Notification Router]
        API --> NOTIF
        SPA -->|Exibe Badge & Alertas| USER((Usuário))
    end
```

---

## 2. Diagrama de Sequência do Ciclo de Vida e Sincronização

```mermaid
sequenceDiagram
    autonumber
    participant App as FastAPI Lifespan
    participant Worker as BackgroundSyncWorker
    participant EZTV as EZTV Public API
    participant DB as SQLite DB
    participant UI as Frontend SPA

    App->>Worker: start() [asyncio.create_task]
    loop A cada SYNC_INTERVAL (60 min)
        Worker->>EZTV: GET /api/get-torrents?page=1&limit=100
        alt Sucesso HTTP 200
            EZTV-->>Worker: 100 Releases Recentes
            Worker->>DB: Upsert em CatalogRelease & CatalogShow
            Worker->>DB: SELECT * FROM ShowRecord (Séries Salvas)
            loop Para cada release correspondente
                Worker->>DB: Verifica duplicidade de notificação
                opt Release Inédito
                    Worker->>DB: INSERT INTO ReleaseNotificationRecord
                end
            end
            Worker->>DB: COMMIT
        else Timeout ou Falha HTTP
            Worker->>Worker: Log de aviso e acionamento de Backoff
        end
        Worker->>Worker: asyncio.sleep(interval)
    end
    Note over App,Worker: Evento de Encerramento (SIGINT / CTRL+C)
    App->>Worker: stop() [task.cancel()]
    Worker->>Worker: Trata asyncio.CancelledError
    Worker-->>App: Encerramento confirmado sem tarefas zumbis
```

---

## 3. Modelo Relacional e Esquema de Dados

### 3.1 Entidade `ReleaseNotificationRecord` (`src/backend/models/db.py`)

```python
class ReleaseNotificationRecord(SQLModel, table=True):
    """Eventos de notificação para episódios recém-disponibilizados de séries salvas."""

    id: Optional[int] = Field(default=None, primary_key=True)
    show_id: int = Field(foreign_key="showrecord.id", index=True)
    imdb_id: str = Field(index=True)
    show_title: str = Field(default="")
    season: int = Field(default=0, index=True)
    episode: int = Field(default=0, index=True)
    release_title: str = Field(default="")
    quality: str = Field(default="Unknown")
    seeds: int = Field(default=0)
    magnet_url: str = Field(default="")
    is_read: bool = Field(default=False, index=True)
    is_dismissed: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

    __table_args__ = (
        UniqueConstraint("show_id", "season", "episode", name="uq_notification_episode"),
    )

    show: Optional["ShowRecord"] = Relationship()
```

---

## 4. Contratos de API REST (`src/backend/api/notifications.py`)

### 4.1 Endpoints

1. `GET /api/notifications`:
   - **Query Params:** `unread_only: bool = True`, `limit: int = 50`.
   - **Retorno:** `list[ReleaseNotificationRecord]`.
2. `GET /api/notifications/count`:
   - **Retorno:** `{"unread_count": int}`.
3. `PATCH /api/notifications/{notification_id}/read`:
   - **Retorno:** `ReleaseNotificationRecord` com `is_read = True`.
4. `POST /api/notifications/dismiss-all`:
   - **Retorno:** `{"status": "success", "dismissed_count": int}`.
5. `GET /api/notifications/scheduler-status`:
   - **Retorno:** Telemetria do agendador (`status`, `last_run_at`, `next_run_eta_seconds`, `last_releases_found`, `last_notifications_created`).

---

## 5. Protocolo de Resiliência e Concorrência

1. **Ciclo de Vida Determinístico (Zero Processos Órfãos):**
   - O worker retém uma referência da `asyncio.Task`.
   - No teardown do `lifespan`, executa:
     ```python
     worker_task.cancel()
     try:
         await asyncio.wait_for(worker_task, timeout=5.0)
     except (asyncio.CancelledError, asyncio.TimeoutError):
         logger.info("Worker cancelado com sucesso.")
     ```
2. **Backoff Sob Instabilidade Externa:**
   - Se a requisição à EZTV falhar por timeout de rede ou erro HTTP 5xx, o worker não realiza novas tentativas imediatas; dobra o tempo de espera do ciclo seguinte (até o teto de 120 minutos) e retorna ao intervalo base assim que um ciclo for bem-sucedido.
3. **Isolamento Transacional:**
   - Cada ciclo instancia e fecha uma nova sessão do banco via `Session(engine)`, eliminando sessões abertas duradouras ou locks prolongados no SQLite.
