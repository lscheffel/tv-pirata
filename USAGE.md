# Guia de Uso e Operação (USAGE.md) — TV Pirata 🏴‍☠️

Este manual operacional detalha os fluxos de ponta a ponta, comandos de terminal verificáveis, parâmetros de configuração, chamadas REST (`curl`) e utilitários CLI da plataforma **TV Pirata (v0.6.0)**.

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

### 1.2. Variáveis de Ambiente Suportadas (`src/backend/core/config.py`)

| Variável | Valor Padrão | Descrição |
| :--- | :--- | :--- |
| `TMDB_API_KEY` | `""` (vazio) | Chave da API v3 ou Bearer Token v4 do TMDB. Se ausente ou inacessível, o sistema opera automaticamente via fallback público (TVMaze) e catálogo federado local. |
| `DATABASE_URL` | `sqlite:///data/tv_pirata.db` | URI de conexão do banco relacional principal (`MediaWork`, biblioteca, histórico e telemetria P2P). |
| `EZTV_DATABASE_URL` | `sqlite:///data/eztv_metadata.db` | URI de conexão do banco dedicado ao catálogo de séries e episódios da EZTV (`shows`, `episodes_catalog`, `shows_fts`). |
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

### 3.1. Filtragem Booleana Avançada e Facetas Dinâmicas
O endpoint `GET /api/explore/works` retorna simultaneamente a lista paginada de obras (`items`) e os contadores dinâmicos de facetas (`facets`: formatos, gêneros, plataformas de streaming, países e décadas).

```bash
# 1. Buscar Obras de Ficção Científica E Thriller (modo booleano AND), excluindo Terror (NOT), com nota >= 8.0
curl -s "http://127.0.0.1:8000/api/explore/works?genres_include=Sci-Fi,Thriller&genres_mode=AND&genres_exclude=Horror&rating_min=8.0&sort_by=rating" | python3 -m json.tool

# 2. Filtrar apenas Filmes (format=movie) lançados entre 2015 e 2026 disponíveis em streaming (ex: Max ou Apple TV+)
curl -s "http://127.0.0.1:8000/api/explore/works?format=movie&year_min=2015&year_max=2026&streaming=Max" | python3 -m json.tool

# 3. Filtrar por Diretor ou Ator e ocultar obras já concluídas na biblioteca pessoal
curl -s "http://127.0.0.1:8000/api/explore/works?director=Denis%20Villeneuve&exclude_watched=true" | python3 -m json.tool
```

**Parâmetros de Consulta (`GET /api/explore/works`):**
- `q`: Busca textual no título canônico, título original ou sinopse.
- `format`: `movie`, `tv_show`, `mini_series`, `documentary`, `animation`, `special`.
- `genres_include`: Lista separada por vírgula de gêneros obrigatórios/desejados.
- `genres_mode`: `OR` (padrão — qualquer gênero listado) ou `AND` (todos os gêneros listados).
- `genres_exclude`: Lista separada por vírgula de gêneros a excluir (`NOT`).
- `year_min` / `year_max`: Intervalo de ano de lançamento.
- `rating_min`: Nota mínima consolidada (`0.0` a `10.0`).
- `runtime_min` / `runtime_max`: Duração em minutos (para filmes ou episódios).
- `country` / `language` / `streaming`: Filtro por país (`US`, `KR`, `DE`, `BR`, `JP`, `GB`), idioma (`en`, `ko`, `de`, `pt`, `ja`) ou plataforma (`Netflix`, `Max`, `Apple TV+`, `Prime Video`, `MUBI`, `Disney+`).
- `director` / `actor` / `creator`: Filtro nominal por créditos associados à obra.
- `has_torrent`: `true` para restringir a obras com sementes P2P ativas.
- `exclude_watched`: `true` para excluir obras com status `completed` na biblioteca pessoal.
- `sort_by`: `rating`, `popularity`, `year`, `title`, `trending`.

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

### 4.4. Crawler Multi-Provedor Resiliente a Cloudflare (`scripts/eztv-metadata-catalog.py`)
Para construir e atualizar o banco dedicado de todas as séries e episódios da EZTV (`data/eztv_metadata.db`) com detecção automática de bloqueio Cloudflare, fallback para a API JSON oficial (`/api/get-torrents`) e enriquecimento cruzado (EZTV + TVMaze + TMDB):

```bash
# 1. Inspecionar diagnóstico completo e estatísticas do banco de metadados
.venv/bin/python scripts/eztv-metadata-catalog.py --stats

# 2. Sincronizar via modo automático (HTML ou fallback API JSON em caso de 403 Cloudflare) com 3º nível TVMaze/TMDB
.venv/bin/python scripts/eztv-metadata-catalog.py --source auto --api-pages 30 --deep 50 --with-level3 --workers 5 --order rating

# 3. Forçar descoberta diretamente pela API JSON oficial da EZTV (sem depender de /showlist/ HTML)
.venv/bin/python scripts/eztv-metadata-catalog.py --source api --api-pages 50 --api-start-page 1 --deep 100 --with-level3

# 4. Re-enriquecer séries existentes que ainda não possuem streaming_providers ou status consolidado
.venv/bin/python scripts/eztv-metadata-catalog.py --skip-level1 --refresh-stale --deep 200 --with-level3
```

---

## 5. 🧪 Pirâmide de Testes e Qualidade (`63 Testes`)

Todos os testes automatizados são **100% herméticos e offline**, utilizando `respx` para interceptação determinística de chamadas HTTP e `SQLite :memory:` com isolamento por `Engine`.

```bash
# 1. Executar toda a suíte (63 testes unitários e de integração)
make test

# 2. Executar testes da Arquitetura Dual-Database e Performance (ADR-009 & ADR-010)
.venv/bin/pytest tests/integration/test_dual_db_eztv.py tests/unit/test_db_performance.py -v

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
