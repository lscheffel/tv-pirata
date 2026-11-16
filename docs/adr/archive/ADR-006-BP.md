# Blueprint Arquitetural: ADR-006 — Catálogo Local EZTV e Motor de Ingestão P2P

## 1. Visão Geral do Fluxo de Dados e Ingestão

```
┌────────────────────────────────────────────────────────────────────────┐
│                   MOTOR DE INGESTÃO & CATÁLOGO EZTV                    │
├────────────────────────────────────────────────────────────────────────┤
│ 1. CAMADA DE AQUISIÇÃO (EZTV Public API)                               │
│    └── GET /api/get-torrents?limit=100&page={page}                     │
│        ├── Parse de releases (hash, title, season, episode, seeds)     │
│        └── Normalização do IMDB ID (ex: "0944947" -> "tt0944947")       │
├────────────────────────────────────────────────────────────────────────┤
│ 2. CAMADA DE INDEXAÇÃO & AGREGAÇÃO (EZTVIndexerService)                │
│    ├── Agrupa releases por imdb_id                                     │
│    ├── Extrai nome limpo da série (regex heurístico de release groups) │
│    ├── Calcula estatísticas: total_torrents, max_seeds, latest_date    │
│    └── Upsert atômico relacional em CatalogShow e CatalogRelease       │
├────────────────────────────────────────────────────────────────────────┤
│ 3. CAMADA DE ENRIQUECIMENTO METADATA (TVMaze / TMDB Lookup)            │
│    ├── Consulta por IMDB ID: https://api.tvmaze.com/lookup/shows?imdb= │
│    └── Atualiza CatalogShow com: poster_url, backdrop, sinopse, rating │
├────────────────────────────────────────────────────────────────────────┤
│ 4. CAMADA DE PERSISTÊNCIA LOCAL (tv_pirata.db)                         │
│    ├── CatalogShow (Tabela de Séries com Torrents Garantidos)          │
│    └── CatalogRelease (Tabela de Magnets e Sementes por Episódio)      │
├────────────────────────────────────────────────────────────────────────┤
│ 5. CAMADA DE CONSUMO REST & FRONTEND                                   │
│    ├── GET /api/catalog/shows (Filtro por seeds, gênero, busca)        │
│    ├── GET /api/catalog/stats (Estatísticas globais do acervo)         │
│    └── POST /api/catalog/sync (Sincronizador em background)            │
└────────────────────────────────────────────────────────────────────────┘
```

## 2. Esquemas de Dados Relacionais SQLModel

```python
class CatalogShow(SQLModel, table=True):
    """Série catalogada com distribuição real no EZTV."""
    imdb_id: str = Field(primary_key=True, index=True) # Formato canônico: tt1234567
    title: str = Field(index=True)
    original_title: Optional[str] = None
    overview: str = ""
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    rating: float = 0.0
    genres: str = "" # CSV
    first_air_date: Optional[str] = None
    status: Optional[str] = None
    total_torrents: int = Field(default=0, index=True)
    max_seeds: int = Field(default=0, index=True)
    latest_season: int = 0
    latest_episode: int = 0
    latest_release_date: Optional[datetime] = None
    last_synced_at: datetime = Field(default_factory=utc_now)
    
    releases: List["CatalogRelease"] = Relationship(
        back_populates="show",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class CatalogRelease(SQLModel, table=True):
    """Release de torrent individual indexada do EZTV."""
    id: Optional[int] = Field(default=None, primary_key=True)
    eztv_id: int = Field(unique=True, index=True)
    hash: str = Field(index=True)
    imdb_id: str = Field(foreign_key="catalogshow.imdb_id", index=True)
    title: str = ""
    filename: str = ""
    season: int = Field(default=0, index=True)
    episode: int = Field(default=0, index=True)
    quality: str = Field(default="Unknown", index=True)
    seeds: int = Field(default=0, index=True)
    peers: int = 0
    size_bytes: int = 0
    magnet_url: str
    torrent_url: Optional[str] = None
    date_released_unix: int = 0
    created_at: datetime = Field(default_factory=utc_now)

    show: Optional[CatalogShow] = Relationship(back_populates="releases")
```

## 3. Heurística de Limpeza de Título de Séries
A maioria dos releases na EZTV segue a convenção:
`{Show Name} S{XX}E{YY} {Resolution} {Source} {Codec}-{Group} [EZTV]`
Exemplo: `The Good Daughter 2026 S01E01 1080p AMZN WEB-DL DDP2 0 H 264 DUAL-BiOMA[EZTVx.to].mkv`
O indexador aplica regex para extrair o título base (`The Good Daughter 2026`) antes do marcador `S\d+E\d+` ou `\d+x\d+`. Caso o título contenha sufixos residuais, a consulta ao TVMaze ou TMDB por `imdb_id` sobrescreve com o nome oficial canônico.

