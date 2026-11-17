# Documentação Operacional e Referência CLI — `imdb-metadata-catalog.py`

Manual técnico completo de arquitetura, máquinas de estado, cache condicional e referência de argumentos para o pipeline de catalogação local em SQLite (`data/mainstream.db`).

---

## 1. Arquitetura do Pipeline em Camadas

O sistema opera sobre um único banco SQLite em modo **WAL (`Write-Ahead Logging`)** com **64 MB de cache em memória** e integridade referencial ativa (`PRAGMA foreign_keys=ON`), estruturado em três camadas independentes e resumíveis:

    CAMADA 1: BOOTSTRAP & DELTA OFICIAL (datasets.imdbws.com -> .imdb_cache/)
     • Validação HTTP HEAD (ETag / Last-Modified) antes de qualquer download
     • Assinatura SHA-256 em sync_state (pula leitura TSV se revisão idêntica)
     • Diff em memória: INSERT OR IGNORE de inéditos + UPDATE só de alterações
                                        |
                                        v
    CAMADA 2: HIDRATAÇÃO RESUMÍVEL (Fila tmdb_synced = 0 -> API TMDB v3 pt-BR)
     • Lookup /3/find/{imdb_id} + /3/{type}/{tmdb_id}?append_to_response=...
     • Extrai sinopse pt-BR, título BR, gêneros, elenco, direção, trailer YT
     • Commit imediato por item + interrupção segura (Ctrl+C) e --resume
                                        |
                                        v
    CAMADA 3: DELTA UPDATE LEVE (--update -> API /3/{type}/changes do TMDB)
     • Zero download de arquivos .tsv.gz (600+ MB)
     • Consulta apenas IDs criados/modificados desde last_tmdb_changes_date
     • Faz UPSERT direto de novidades com vínculo IMDb (ttXXXXXXX)

---

## 2. Configuração de Credenciais (`.env`)

O script possui um carregador nativo (`load_project_env`) que localiza automaticamente o arquivo `.env` na **raiz do projeto** (pai de `scripts/`), no diretório atual (`cwd`) ou dentro de `scripts/`, sem depender de pacotes externos.

### Variáveis Reconhecidas (Ordem de Prioridade)

1. **Token de Leitura JWT (Prioritário — enviado no header `Authorization: Bearer ...`)**:
   * `TMDB_READ_TOKEN`
   * `TMDB_READ_ACCESS_TOKEN`
   * `TMDB_ACCESS_TOKEN`
   * `TMDB_BEARER_TOKEN`
   * `TMDB_TOKEN`
   * `IMDB_READ_TOKEN` / `IMDB_READ_ACCESS_TOKEN` / `IMDB_ACCESS_TOKEN` / `IMDB_TOKEN`
   * `READ_ACCESS_TOKEN` / `BEARER_TOKEN`
2. **API Key v3 (Fallback — enviada como query param `?api_key=...`)**:
   * `TMDB_API_KEY` / `TMDB_KEY`
   * `IMDB_API_KEY` / `IMDB_KEY`
   * `API_KEY`

Exemplo mínimo do `.env` na raiz:

    TMDB_READ_TOKEN="eyJhbGciOiJIUzI1NiJ9..."
    TMDB_API_KEY="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"

---

## 3. Estrutura do Banco SQLite (`data/mainstream.db`)

### Tabela `shows` (Filmes, Telefilmes, Séries e Minisséries)

| Coluna | Tipo | Origem | Descrição |
| :--- | :--- | :--- | :--- |
| `imdb_id` | `TEXT (PK)` | IMDb | Identificador canônico (ex: `tt0944947`, `tt0111161`). |
| `imdb_num` | `INTEGER` | Derivado | Parte numérica do `imdb_id` para ordenação rápida por cadastro. |
| `tmdb_id` | `INTEGER` | TMDB | ID numérico interno no The Movie Database. |
| `title_type` | `TEXT` | IMDb | Categoria (`movie`, `tvMovie`, `tvSeries`, `tvMiniSeries`). |
| `primary_title` | `TEXT` | IMDb | Título comercial internacional principal. |
| `original_title` | `TEXT` | IMDb | Título no idioma original de produção. |
| `title_ptbr` | `TEXT` | IMDb AKAs / TMDB | Título oficial de exibição no Brasil (`region='BR'`, priorizando `imdbDisplay`). |
| `tagline` | `TEXT` | TMDB | Frase promocional localizada em `pt-BR`. |
| `is_adult` | `INTEGER` | IMDb | Flag booleana (`0` ou `1`). |
| `start_year` / `end_year` | `INTEGER` | IMDb / TMDB | Ano de lançamento e ano de encerramento (séries). |
| `runtime_minutes` | `INTEGER` | IMDb / TMDB | Duração média em minutos. |
| `genres` / `genres_ptbr` | `TEXT` | IMDb / TMDB | Gêneros em inglês (`genres`) e traduzidos para português (`genres_ptbr`). |
| `rating_score` | `REAL` | IMDb / TMDB | Nota média (escala `0.0` a `10.0`). |
| `rating_votes` | `INTEGER` | IMDb / TMDB | Quantidade total de votos contabilizados. |
| `poster_url` | `TEXT` | TMDB | URL completa em resolução original (`/t/p/original/...`). |
| `backdrop_url` | `TEXT` | TMDB | Imagem widescreen `16:9` em alta resolução (`/t/p/original/...`). |
| `trailer_url` | `TEXT` | TMDB | Link direto do YouTube (`https://www.youtube.com/watch?v=...`), priorizando trailer oficial `pt-BR` -> `pt` -> `en`. |
| `synopsis` / `synopsis_ptbr` | `TEXT` | TMDB | Sinopse localizada em português do Brasil. |
| `content_rating` | `TEXT` | TMDB | Classificação indicativa brasileira (`L`, `10`, `12`, `14`, `16`, `18`) com fallback para `US`. |
| `release_date` | `TEXT` | TMDB | Data exata de estreia (`YYYY-MM-DD`). |
| `countries` / `languages` | `TEXT` | TMDB | Países produtores e idiomas falados. |
| `network` | `TEXT` | TMDB | Emissora ou plataforma original (`Netflix`, `HBO`, `Apple TV+`, etc.). |
| `directors` / `creators` | `TEXT` | TMDB | Diretores (até 8) e criadores/roteiristas principais (até 8). |
| `cast_members` | `TEXT` | TMDB | Elenco principal (até 15 atores/atrizes). |
| `total_seasons` | `INTEGER` | TMDB | Quantidade total de temporadas (apenas séries). |
| `details_fetched` | `INTEGER` | Controle | `0` = Pendente, `1` = Hidratado. |
| `tmdb_synced` | `INTEGER` | Controle | Máquina de estados da fila TMDB (ver seção 4). |
| `updated_at` | `TIMESTAMP` | Sistema | Timestamp UTC da última gravação. |

### Tabela `episodes_catalog` (Árvore de Episódios)

| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `episode_imdb_id` | `TEXT (PK)` | ID do episódio no IMDb (ex: `tt1480055`). |
| `show_imdb_id` | `TEXT (FK)` | Chave estrangeira vinculada a `shows(imdb_id)` com `ON DELETE CASCADE`. |
| `season` / `episode` | `INTEGER` | Número da temporada e número do episódio. |
| `rating_score` / `rating_votes` | `REAL / INT` | Nota e votos individuais do episódio no dump `title.ratings`. |

### Tabela `sync_state` (Checkpoints e Assinaturas de Revisão)

Armazena pares `key -> value` usados para evitar retrabalho:

* `last_basics_import_sig`: Hash SHA-256 `(etag_basics, etag_ratings, min_votes, since_year, types)`.
* `last_akas_import_sig`: Hash SHA-256 `(etag_akas, total_alvos, since_year)`.
* `last_episodes_import_sig`: Hash SHA-256 `(etag_episodes, etag_ratings, min_votes, since_year)`.
* `last_tmdb_changes_date`: Data UTC (`YYYY-MM-DD`) do último cursor executado pelo `--update`.
* `last_resume_checkpoint`: Timestamp ISO do último lote concluído pelo `--resume`.

---

## 4. Máquinas de Estado e Cache Inteligente

### Estados de `tmdb_synced`

| Valor | Significado | Comportamento no `--resume` |
| :---: | :--- | :--- |
| **`0`** | **Pendente na fila** | Entra na fila de processamento do TMDB. |
| **`1`** | **Concluído com Sinopse PT-BR** | Ignorado (já hidratado com sucesso). |
| **`2`** | **Concluído sem Sinopse PT-BR** | Ignorado (existe no TMDB e teve capa/elenco/trailer salvos, mas o TMDB não possui `overview` em português). |
| **`-1`** | **Inexistente no TMDB** | Ignorado (o `imdb_id` não possui vínculo cadastrado no TMDB). |

### Cache Condicional via `HTTP HEAD` (`.imdb_cache/`)

Ao executar `--bootstrap`, cada arquivo remoto (`basics`, `ratings`, `akas`, `episodes`) gera um sidecar JSON (ex: `.imdb_cache/basics.tsv.gz.meta.json`) registrando `etag`, `last_modified` e `content_length`.

* **Se o `ETag` ou `Last-Modified` do servidor não mudou**: 0 bytes são baixados.
* **Se a assinatura do dump já foi processada no SQLite**: o parsing do arquivo `.tsv.gz` também é ignorado em menos de 1 segundo.

---

## 5. Referência Completa de Argumentos CLI

### A. Modos de Operação (Ações Principais)

| Flag | Alias | Descrição Detalhada |
| :--- | :--- | :--- |
| `--stats` | — | Exibe o painel de diagnóstico completo: detecção do `.env`, data do último `--update`, contagem de filmes/séries, percentual concluído da fila, cobertura de títulos BR, sinopses `pt-BR`, *backdrops*, trailers do YouTube e episódios vinculados. |
| `--bootstrap` | `--sync-datasets` | Executa a sincronização da Camada 1 usando os dumps oficiais do IMDb (`title.ratings`, `title.basics` e `title.akas` BR). Valida `ETag` via `HTTP HEAD` e aplica delta em memória. |
| `--resume` | — | Inicia ou retoma a Camada 2 (hidratação completa via API do TMDB) exclusivamente para registros com `tmdb_synced = 0`. Pode ser interrompido a qualquer momento com `Ctrl+C`. |
| `--update` | — | Executa a Camada 3 (atualização incremental leve via `/3/movie/changes` e `/3/tv/changes` do TMDB). **Não baixa arquivos `.tsv.gz`**. Captura novidades e alterações desde `last_tmdb_changes_date`. |

### B. Controle de Lotes, Cache e Episódios

| Flag | Padrão | Escopo | Descrição Detalhada |
| :--- | :---: | :---: | :--- |
| `--db CAMINHO` | `data/mainstream.db` | Global | Define o caminho do arquivo de banco de dados SQLite de destino. |
| `--limit N` | `0` (ilimitado) | `--resume` | Limita a execução atual do `--resume` a um lote de `N` títulos e encerra salvando o checkpoint. |
| `--days-back N` | `3` | `--update` | Janela retroativa de dias usada apenas na primeira execução do `--update` quando ainda não existe `last_tmdb_changes_date` no banco (limite máximo da API TMDB: `14` dias). |
| `--include-episodes` | `False` | `--bootstrap` | Baixa e vincula episódios inéditos (`title.episode.tsv.gz`) na tabela `episodes_catalog` para todas as séries cadastradas. |
| `--force-download` | `False` | `--bootstrap` | Ignora os metadados `ETag`/`Last-Modified` do cache local e a assinatura `sync_state`, forçando novo download e reprocessamento completo dos `.tsv.gz`. |

### C. Filtros de Seleção e Ordenação

| Flag | Valores / Padrão | Escopo | Descrição Detalhada |
| :--- | :---: | :---: | :--- |
| `--min-votes N` | `50` | `--bootstrap`, `--resume`, `--update` | Exige no mínimo `N` votos para importar ou processar um título. Use `--min-votes 0` para remover o filtro e incluir títulos sem avaliação. |
| `--since-year ANO` | `0` (todos) | `--bootstrap`, `--resume`, `--update` | Restringe a importação e as filas apenas para obras com `start_year >= ANO` (ex: `--since-year 2024`). |
| `--category TIPO` | `all`, `movies`, `series` (padrão: `all`) | `--resume` | Filtra a fila de hidratação apenas para filmes (`movie`, `tvMovie`), apenas para séries (`tvSeries`, `tvMiniSeries`) ou ambos. |
| `--order CRITERIO` | `newest`, `oldest`, `votes` (padrão: `newest`) | `--resume` | Define a prioridade da fila: `newest` (lançamentos mais recentes primeiro), `oldest` (mais antigos primeiro) ou `votes` (maior popularidade/votos primeiro). |

### D. Paralelismo e Taxa de Requisições

| Flag | Padrão | Descrição Detalhada |
| :--- | :---: | :--- |
| `--workers N` | `10` | Quantidade de threads simultâneas no `ThreadPoolExecutor`. Como cada título dispara 2 chamadas REST (`/find` + detalhes), `10` workers geram ~25-30 req/s (dentro do limite seguro da API do TMDB). |
| `--delay SEGUNDOS` | `0.15` | Pausa em segundos aplicada por worker após cada título concluído para evitar throttling (`HTTP 429`). |

---

## 6. Receitas Práticas de Uso (Playbook)

### 1. Diagnóstico Inicial e Conferência do `.env`

    python3 scripts/imdb-metadata-catalog.py --stats

### 2. Carga Base Inicial (Filmes + Séries >= 50 votos + Títulos BR + Episódios)

    python3 scripts/imdb-metadata-catalog.py --bootstrap --include-episodes

*(Se executado novamente no mesmo dia, levará menos de 1 segundo pois validará o `ETag` remoto e pulará download e leitura).*

### 3. Hidratação Inicial dos Metadados Ricos em Lotes Resumíveis

Para processar uma base grande (ex: 250.000 títulos) sem travar o terminal ou em janelas programadas:

    # Prioriza os lançamentos mais recentes em lotes de 15.000 títulos por vez:
    python3 scripts/imdb-metadata-catalog.py --resume --order newest --limit 15000 --workers 10

    # Ou prioriza os títulos mais populares/votados primeiro:
    python3 scripts/imdb-metadata-catalog.py --resume --order votes --limit 15000 --workers 10

### 4. Focar Apenas em Séries ou Apenas em Filmes

    python3 scripts/imdb-metadata-catalog.py --resume --category series --order newest --workers 10

### 5. Rotina Diária / Semanal de Atualização Leve (Zero Download de `.gz`)

    python3 scripts/imdb-metadata-catalog.py --update

### 6. Manutenção Mensal (Sincronizar Notas/Votos e Novos Episódios do Dump Oficial)

    python3 scripts/imdb-metadata-catalog.py --bootstrap --include-episodes && \
    python3 scripts/imdb-metadata-catalog.py --resume --order newest

---

## 7. Consultas SQL Úteis para Consumo Externo

### Buscar filmes ou séries prontos para exibição em interface (com fallback automático para título original)

    SELECT
        imdb_id,
        tmdb_id,
        title_type,
        COALESCE(NULLIF(title_ptbr, ''), primary_title) AS display_title,
        start_year,
        rating_score,
        rating_votes,
        genres_ptbr,
        content_rating,
        poster_url,
        backdrop_url,
        trailer_url,
        synopsis_ptbr
    FROM shows
    WHERE tmdb_synced IN (1, 2)
    ORDER BY start_year DESC, rating_votes DESC
    LIMIT 50;

### Verificar distribuição detalhada da fila de sincronização

    SELECT
        tmdb_synced,
        CASE tmdb_synced
            WHEN 0  THEN 'Pendente (--resume)'
            WHEN 1  THEN 'Concluído com Sinopse PT-BR'
            WHEN 2  THEN 'Concluído sem Sinopse PT-BR'
            WHEN -1 THEN 'Sem vínculo no TMDB'
        END AS status_desc,
        COUNT(*) AS total
    FROM shows
    GROUP BY tmdb_synced;
