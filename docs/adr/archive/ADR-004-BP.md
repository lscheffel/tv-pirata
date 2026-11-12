---
id: ADR-004-BP
title: "Blueprint: Persistência Relacional SQLModel, Gestão de Biblioteca e Servidor Web FastAPI"
adr_ref: ADR-004
created: "2026-11-11"
status: PROPOSED
---

# Blueprint Arquitetural — ADR-004

## 1. Diagrama de Relacionamento de Entidades (ERD Completo SQLModel)

```mermaid
erDiagram
    SHOW_RECORD {
        int id PK
        int tmdb_id UK
        int tvmaze_id
        string imdb_id
        string title
        string original_title
        string overview
        string poster_url
        string backdrop_url
        float rating
        string first_air_date
        string status
        string user_status
        datetime created_at
        datetime updated_at
    }
    SEASON_RECORD {
        int id PK
        int show_id FK
        int season_number
        string name
        string overview
        string poster_url
        int episode_count
    }
    EPISODE_RECORD {
        int id PK
        int season_id FK
        int episode_number
        string title
        string overview
        string air_date
        float rating
    }
    EPISODE_WATCH_RECORD {
        int id PK
        int episode_id FK
        boolean is_watched
        datetime watched_at
    }
    LOCAL_MEDIA_RECORD {
        int id PK
        int episode_id FK
        string relative_path
        boolean is_available
        datetime last_seen_at
    }
    TAG_RECORD {
        int id PK
        string name UK
        string color
    }
    SHOW_TAG_LINK {
        int show_id FK
        int tag_id FK
    }
    COLLECTION_RECORD {
        int id PK
        string name
        string description
        string filter_criteria
        datetime created_at
    }

    SHOW_RECORD ||--o{ SEASON_RECORD : "possui"
    SEASON_RECORD ||--o{ EPISODE_RECORD : "contém"
    EPISODE_RECORD ||--o| EPISODE_WATCH_RECORD : "rastreia"
    EPISODE_RECORD ||--o| LOCAL_MEDIA_RECORD : "mapeia"
    SHOW_RECORD ||--o{ SHOW_TAG_LINK : "associa"
    TAG_RECORD ||--o{ SHOW_TAG_LINK : "categoriza"
```

## 2. Mapa de Rotas REST da Aplicação FastAPI

```text
/api/
├── discovery/
│   ├── GET  /trending                   # Séries em alta na semana
│   ├── GET  /search?q={query}           # Busca com fallback automático TMDB -> TVMaze
│   └── GET  /shows/{tmdb_id}            # Detalhes completos do show
├── library/
│   ├── GET  /shows                      # Listar séries da biblioteca pessoal
│   ├── POST /shows                      # Salvar série descoberta na biblioteca
│   ├── GET  /shows/{id}                 # Obter série da biblioteca com temporadas/episódios
│   ├── PATCH /shows/{id}/status         # Atualizar status geral (watching, completed, etc)
│   └── DELETE /shows/{id}               # Remover série da biblioteca pessoal
├── watches/
│   ├── POST /episodes/{id}/toggle       # Alternar estado de assistido do episódio
│   ├── POST /seasons/{id}/watch-all     # Marcar temporada inteira como assistida
│   └── GET  /shows/{id}/progress        # Obter estatísticas percentuais de visualização
├── torrents/
│   └── GET  /shows/{imdb_id}            # Listar releases e magnets da EZTV
└── collections/
    ├── GET  /                           # Listar coleções e tags
    ├── POST /smart                      # Criar Smart Collection com filter_criteria JSON
    └── GET  /smart/{id}/items           # Executar consulta dinâmica da Smart Collection
```

