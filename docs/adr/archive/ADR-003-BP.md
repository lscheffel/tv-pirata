---
id: ADR-003-BP
title: "Blueprint: Implementação do Contrato Unificado, Provedores com Fallback e EZTV"
adr_ref: ADR-003
created: "2026-11-11"
status: ACCEPTED
---

# Blueprint Arquitetural — ADR-003

## 1. Diagrama de Classes e Contratos de Domínio

```mermaid
classDiagram
    class BaseMetadataProvider {
        <<Interface>>
        +search_shows(query: str) list[UnifiedShow]
        +get_show_details(show_id: int) UnifiedShow
        +get_trending() list[UnifiedShow]
    }
    class TMDBProvider {
        -api_key: str
        -base_url: str
        +search_shows(query: str)
        +get_show_details(show_id: int)
        +get_trending()
    }
    class TVMazeProvider {
        -base_url: str
        +search_shows(query: str)
        +get_show_details(show_id: int)
        +get_trending()
    }
    class EZTVProvider {
        -base_url: str
        +get_torrents_by_imdb(imdb_id: str) list[TorrentRelease]
    }
    class ResilientDiscoveryService {
        -primary: TMDBProvider
        -fallback: TVMazeProvider
        -timeout_seconds: float
        +get_show_with_fallback(tmdb_id: int, tvmaze_id: int) UnifiedShow
    }

    BaseMetadataProvider <|.. TMDBProvider
    BaseMetadataProvider <|.. TVMazeProvider
    ResilientDiscoveryService --> TMDBProvider
    ResilientDiscoveryService --> TVMazeProvider
```

## 2. Estrutura do UnifiedShow (Pydantic Schema)

- `id`: int (TMDB ID prioritário ou derivado TVMaze)
- `tmdb_id`: Optional[int]
- `tvmaze_id`: Optional[int]
- `imdb_id`: Optional[str]
- `title`: str
- `original_title`: Optional[str]
- `overview`: str
- `poster_url`: Optional[str]
- `backdrop_url`: Optional[str]
- `rating`: float
- `genres`: list[str]
- `first_air_date`: Optional[str]
- `status`: Optional[str]
- `source_provider`: str ("tmdb" | "tvmaze")
- `seasons`: list[UnifiedSeason]
