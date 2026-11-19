# Guia de Uso e Operação (USAGE.md) — TV Pirata 🏴‍☠️

Este manual operacional detalha os fluxos de ponta a ponta, comandos de terminal verificáveis, parâmetros de configuração, chamadas REST (`curl`) e utilitários CLI da plataforma **TV Pirata (v0.7.0)**.

---

## 1. ⚙️ Configuração do Ambiente e Variáveis (`.env`)

### 1.1. Preparação Inicial
```bash
# 1. Entrar no diretório do repositório
cd /home/loupan/projetosVS/tv-pirata

# 2. Criar arquivo .env a partir do template seguro
cp .env.example .env

# 3. Instalar dependências Python no ambiente virtual (.venv)
uv pip install -e ".[dev]"
```

### 1.2. Variáveis de Ambiente Suportadas (`src/backend/core/config.py` / `database.py`)

| Variável | Valor Padrão | Descrição |
| :--- | :--- | :--- |
| `TMDB_API_KEY` | `""` (vazio) | Chave da API v3 ou Bearer Token v4 do TMDB. Habilita hidratação PT-BR, trailers e disponibilidade real de streaming (`watch/providers` e `/discover`). |
| `MAINSTREAM_DATABASE_URL` | `sqlite:///data/mainstream.db` | URI da **Base Canônica** (279k+ títulos IMDb, 4.5M+ episódios, metadados TMDB/TVMaze, biblioteca pessoal, `MediaWork`, `shows_fts` e `global_facets_v2`). Também aceita `DATABASE_URL` por retrocompatibilidade. |
| `SOURCES_DATABASE_URL` | `sqlite:///data/sources.db` | URI da **Base de Recursos Externos** dedicada ao acervo P2P/EZTV (`shows`, `episodes_catalog`, `catalogshow`, `catalogrelease`, `shows_fts`). Também aceita `EZTV_DATABASE_URL`. |
| `SMB_MOUNT_PATH` | `/mnt/storage/media` | Caminho local onde o compartilhamento SMB de mídia doméstica está montado. |
| `REQUEST_TIMEOUT` | `2.0` | Timeout máximo (em segundos) para chamadas ao provedor primário antes do disparo do fallback. |
| `AUTO_SYNC_ENABLED` | `true` | Ativa ou desativa o agendador periódico em segundo plano (`BackgroundSyncService`). |
| `AUTO_SYNC_INTERVAL_MINUTES` | `30` | Intervalo base (em minutos) entre ciclos automáticos de ingestão EZTV e reconciliação de alertas. |
| `AUTO_SYNC_PAGES` | `2` | Quantidade de páginas recentes da EZTV inspecionadas a cada ciclo automático. |

---

## 2. 🚀 Execução da Aplicação (Backend + SPA Frontend)

### 2.1. Modo Integrado (Produção / Homelab)
O FastAPI serve diretamente o bundle estático compilado do React 19 (`src/backend/static/dist/`) na rota raiz `/` e `/app`:

```bash
# 1. Compilar o frontend SPA (necessário apenas após alterações em src/frontend)
make build-front

# 2. Iniciar o servidor FastAPI em http://127.0.0.1:8000
make run
```

> **Regra de Encerramento:** Pressione `Ctrl+C` para encerrar o servidor. O `lifespan` do FastAPI cancelará cooperativamente a task assíncrona do `BackgroundSyncService` em até `3.0s` sem deixar processos órfãos.

### 2.2. Modo Desenvolvimento de UI (Vite HMR)
```bash
# Terminal 1: API Backend na porta 8000
make run

# Terminal 2: Servidor Vite com Hot Reloading na porta 5173
make dev-front
```

---

## 3. 🧭 Camada 1: Audiovisual Discovery Core (`/api/explore`)

A aba **"Explorar Universo"** (`ExplorerView.tsx`) e o roteador `/api/explore` fornecem descoberta multi-formato (Filmes, Séries, Minisséries, Documentários, Animações e Especiais) independente da existência de torrents ou arquivos locais.

### 3.1. Filtragem Booleana Avançada, Fontes de Dados e Facetas Dinâmicas
O endpoint `GET /api/explore/works` executa SQL Pushdown sobre `data/mainstream.db` e retorna simultaneamente a lista paginada de obras (`items`) e os contadores exatos/escalados de facetas (`facets`: `work_types`, `data_sources`, `genres`, `streaming_providers`, `statuses`, `countries` e `decades`).

```bash
# 1. Buscar Obras de Ficção Científica E Suspense (modo AND), excluindo Terror (NOT), com nota >= 8.0
curl -s "http://127.0.0.1:8000/api/explore/works?genres_all=Fic%C3%A7%C3%A3o%20Cient%C3%ADfica,Suspense&genres_not=Terror&min_rating=8.0&sort_by=rating" | python3 -m json.tool

# 2. Filtrar Documentários ou Filmes em Streaming (Netflix ou Max)
curl -s "http://127.0.0.1:8000/api/explore/works?work_types=documentary&streaming_providers=Netflix,Max" | python3 -m json.tool

# 3. Cruzar Base Canônica por Fonte de Dados (ex.: apenas obras com EZTV P2P + Sinopse PT-BR)
curl -s "http://127.0.0.1:8000/api/explore/works?data_sources=eztv,ptbr&sort_by=popularity" | python3 -m json.tool

# 4. Consultar estatísticas da Base Canônica e disparar atualização Delta pela API
curl -s "http://127.0.0.1:8000/api/explore/mainstream-stats" | python3 -m json.tool
curl -s -X POST "http://127.0.0.1:8000/api/explore/update-mainstream?mode=delta&limit=25" | python3 -m json.tool
```

**Parâmetros Principais (`GET /api/explore/works`):**
- `q`: Busca bilíngue PT-BR/EN-US (tolerante a acentos via `shows_fts`) ranqueada por correspondência exata/similaridade.
- `work_types`: `movie`, `tv_show`, `mini_series`, `tv_movie`, `documentary`, `animation`, `special`, `short`.
- `data_sources`: Interseção de fontes: `eztv`, `p2p_active`, `imdb`, `tmdb`, `ptbr`, `youtube_trailer`, `tvmaze`, `personal_library`.
- `genres_any` / `genres_all` / `genres_not`: Filtragem booleana (`OR`, `AND`, `NOT`) sobre as 31 categorias canônicas.
- `streaming_providers`: `Netflix`, `Prime Video`, `Max`, `Disney+`, `Globoplay`, `Apple TV+`, `Paramount+`, `Crunchyroll`, `MUBI`, `Looke`, `Claro tv+`, etc.
- `status`: `Running`, `Ended`, `Released`, `To Be Determined`, `Canceled`.
- `year_from` / `year_to` / `min_rating` / `max_rating` / `min_runtime` / `max_runtime`: Filtros quantitativos.
- `person_query` & `role_type` (`director`, `creator`, `actor`, `writer`): Filtro nominal e por função na obra.
- `only_with_p2p` / `exclude_watched` / `sort_by` (`rating`, `relevance`, `popularity`, `year_desc`, `year_asc`, `runtime`, `title`).

### 3.2. Dossiê Canônico da Obra, Procedência e Similaridade
```bash
# Consultar dossiê completo da obra (identificadores externos, notas por fonte, proveniência por atributo, elenco, streaming, relações e obras similares com justificativa)
curl -s "http://127.0.0.1:8000/api/explore/works/1" | python3 -m json.tool
```

### 3.3. Descoberta por Pessoas, Filmografias e Colaborações Recorrentes
```bash
# 1. Listar profissionais indexados (diretores, criadores, atores, roteiristas)
curl -s "http://127.0.0.1:8000/api/explore/people?q=Villeneuve" | python3 -m json.tool

# 2. Consultar filmografia completa de uma pessoa pelo ID
curl -s "http://127.0.0.1:8000/api/explore/people/1" | python3 -m json.tool

# 3. Descobrir obras em que duas pessoas trabalharam juntas (ex: IDs 1 e 2)
curl -s "http://127.0.0.1:8000/api/explore/people/collaborations?person_a_id=1&person_b_id=2" | python3 -m json.tool
```

### 3.4. Calendário Unificado de Lançamentos e Rankings Multi-Critério
```bash
# 1. Consultar calendário de estreias, novos episódios e temporadas
curl -s "http://127.0.0.1:8000/api/explore/calendar?limit=30" | python3 -m json.tool

# 2. Consultar rankings por critério (rating, popularity, trending, recent, acclaimed)
curl -s "http://127.0.0.1:8000/api/explore/rankings?criterion=acclaimed&limit=20" | python3 -m json.tool

# 3. Disparar federação manual do catálogo (seeding + ponte com EZTV e Biblioteca)
curl -s -X POST "http://127.0.0.1:8000/api/explore/federate" | python3 -m json.tool
```

---

## 4. 📡 Camada 2: Ecossistema Pessoal, Catálogo P2P e Notificações

### 4.1. Biblioteca Pessoal e Progresso de Episódios (`/api/library` & `/api/watches`)
```bash
# 1. Listar séries da biblioteca pessoal (opcional: ?status=watching)
curl -s "http://127.0.0.1:8000/api/library/shows" | python3 -m json.tool

# 2. Consultar progresso percentual de uma série salva (ex: show_id=1)
curl -s "http://127.0.0.1:8000/api/watches/shows/1/progress" | python3 -m json.tool

# 3. Alternar episódio como assistido / não assistido
curl -s -X POST "http://127.0.0.1:8000/api/watches/episodes/1/toggle" | python3 -m json.tool

# 4. Marcar temporada inteira como assistida
curl -s -X POST "http://127.0.0.1:8000/api/watches/seasons/1/watch-all" | python3 -m json.tool
```

### 4.2. Background Auto-Sync e Alertas de Novos Episódios (`/api/notifications`)
```bash
# 1. Consultar telemetria do agendador assíncrono (BackgroundSyncService)
curl -s "http://127.0.0.1:8000/api/notifications/scheduler/status" | python3 -m json.tool

# 2. Listar alertas de novos episódios disponíveis em P2P para séries da biblioteca
curl -s "http://127.0.0.1:8000/api/notifications?unread_only=true" | python3 -m json.tool

# 3. Disparar ciclo imediato de sincronização e reconciliação sob demanda
curl -s -X POST "http://127.0.0.1:8000/api/notifications/sync" | python3 -m json.tool

# 4. Marcar todas as notificações como lidas
curl -s -X POST "http://127.0.0.1:8000/api/notifications/read-all" | python3 -m json.tool
```

### 4.3. Sincronização do Catálogo P2P EZTV (`scripts/sync_catalog.py`)
Para popular ou expandir o catálogo de torrents com sementes verificadas no banco principal (`tv_pirata.db`):

```bash
# Sincronizar as 5 primeiras páginas (até 500 torrents recentes) via Makefile
make sync-catalog

# Ou executar o script CLI com paginação customizada
.venv/bin/python scripts/sync_catalog.py --pages 10 --start 1
```

### 4.4. Pipeline de Hidratação Canônica (`mainstream.db`) & Base de Recursos (`sources.db`)
Para manter a **Base Canônica (`data/mainstream.db`)** e a **Base de Recursos (`data/sources.db`)** sincronizadas via CLI:

```bash
# 1. Estatísticas e atualização delta/hidratação IMDb + TMDB (dumps + API /changes + watch/providers)
.venv/bin/python scripts/imdb-metadata-catalog.py --stats
.venv/bin/python scripts/imdb-metadata-catalog.py --update
.venv/bin/python scripts/imdb-metadata-catalog.py --resume --limit 5000

# 2. Crawler multi-provedor da base de recursos EZTV (data/sources.db)
.venv/bin/python scripts/eztv-metadata-catalog.py --stats
.venv/bin/python scripts/eztv-metadata-catalog.py --source auto --api-pages 30 --deep 50 --with-level3

# 3. Propagar badges e status (sources.db -> mainstream.db)
.venv/bin/python scripts/sync-eztv-bade.py

# 4. Hidratar streaming availability real (TMDB /discover BR/US), normalizar 31 gêneros e atualizar global_facets_v2
.venv/bin/python scripts/sync_canonical_facets_and_providers.py
```

---

## 5. 🧪 Pirâmide de Testes e Qualidade (`73 Testes`)

Todos os testes automatizados são **100% herméticos e offline**, utilizando `respx` para interceptação determinística de chamadas HTTP e `SQLite :memory:` com isolamento por `Engine`.

```bash
# 1. Executar toda a suíte (73 testes unitários e de integração)
make test

# 2. Executar testes de plugins 1:N, YTS accel.li v2, EZTV RSS, Sincronia Bipartida e CAPTCHA (ADR-013 / ADR-014)
.venv/bin/pytest tests/integration/test_source_plugins_contract.py -v

# 3. Executar testes multi-fonte, preferências e contratos ADR-012
.venv/bin/pytest tests/integration/test_sources_and_preferences_api.py -v

# 2. Executar testes Dual-SSOT, SQL Pushdown, Taxonomia e Busca Bilíngue (ADR-011)
.venv/bin/pytest tests/integration/test_mainstream_sources_ssot.py tests/integration/test_dual_db_eztv.py tests/unit/test_db_performance.py -v

# 3. Executar testes da Camada 1 (Audiovisual Discovery Core - ADR-008)
.venv/bin/pytest tests/unit/test_entity_resolution.py tests/unit/test_discovery_engine.py tests/integration/test_explore_api.py -v

# 4. Executar linter estático Ruff (regras E, F, I, limite de 100 colunas)
make lint

# 5. Executar o Quality Gate completo (Ruff + Pytest)
./scripts/quality_gate.sh
```

---

## 6. 🛠️ Solução de Problemas (Troubleshooting)

| Sintoma | Causa Provável | Solução |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'src'` | `PYTHONPATH` ausente ao invocar `pytest` ou scripts fora da raiz | Executar via `make test` ou prefixar com `PYTHONPATH=. .venv/bin/python ...` |
| `Primary provider (TMDB) failed... Falling back to TVMaze` | `TMDB_API_KEY` não configurada no `.env` ou timeout de rede (> 2.0s) | Comportamento esperado do `ResilientDiscoveryService`. Para usar o TMDB primário, preencha `TMDB_API_KEY` no `.env`. |
| Poucos títulos exibidos na aba "Início" recém-instalada | O catálogo P2P (`CatalogShow`) ainda não foi sincronizado com páginas suficientes | Acesse a aba **"Explorar Universo"** (já populada com o catálogo federado multi-formato) ou execute `make sync-catalog` para ingerir mais páginas da EZTV. |
| Alterações no frontend (`src/frontend/`) não aparecem em `:8000` | O FastAPI serve os artefatos estáticos compilados em `src/backend/static/dist/` | Execute `make build-front` após editar arquivos `.tsx` ou utilize `make dev-front` (`:5173`) durante o desenvolvimento. |
| `no such table` em novos testes de integração SQLite in-memory | Tabelas de `catalog_domain.py` ou `db.py` não importadas antes de `SQLModel.metadata.create_all` | Certifique-se de importar `src.backend.models` antes de invocar `SQLModel.metadata.create_all(engine)`. |
