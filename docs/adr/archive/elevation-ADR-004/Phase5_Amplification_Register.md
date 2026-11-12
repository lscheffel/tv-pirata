# Phase 5: Registro de Amplificação Arquitetural — ADR-004

## 1. Amplificações Incorporadas ao Design

1. **Injeção de Dependência Hermética:**
   - Criação de dependência `get_session()` do FastAPI com `yield` e context manager atômico para rollback automático em caso de exceções HTTP.
2. **Upsert Idempotente de Séries:**
   - Ao importar uma série de `UnifiedShow` para `ShowRecord`, verificar existência por `tmdb_id`; se existir, atualiza metadados sem duplicar temporadas ou resetar os registros de assistidos existentes.
3. **Mecanismo de Query Dinâmica para Smart Collections:**
   - Tradutor leve em Python que transforma o JSON `filter_criteria` (ex: `{"user_status": "watching", "has_media": true}`) diretamente em expressões de filtro do SQLModel (`col(ShowRecord.user_status) == "watching"`).
4. **Tratamento de CORS e Healthcheck:**
   - Endpoint `/api/health` para monitoramento de integridade e middleware `CORSMiddleware` parametrizado por `.env`.

