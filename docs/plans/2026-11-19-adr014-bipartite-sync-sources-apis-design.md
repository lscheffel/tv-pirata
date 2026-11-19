# Design Doc — ADR-014: Alinhamento Canônico com `sources-apis.md` (`movies-api.accel.li` & `eztvx.to`), Curadoria `Torrent-Api-py` (12 Sites), Sincronia Bipartida em 2 Etapas e Sync Command Deck UI/UX

- **Data:** 2026-11-19
- **Status:** Validated & Approved (`Garimpo R1: 1B 2A 3C 4D 5B 6A 7C 8B 9D 10C` | `R2: 1B 2A 3C 4D 5A 6B 7C 8C 9D 10A` | `R3: schema v1`)
- **Target ADR:** `ADR-014` (`DCI = 8`, `Tier 2 — Quadra SOTA`, `BR = 8.5 CRITICAL`)

---

## 1. Visão Arquitetural: Catálogo Canônico Soberano + Fontes Semi-Efêmeras Bipartidas

O **TV Pirata** opera sob o princípio da **Soberania da Camada 1 (`data/mainstream.db`)**:
- **Camada 1 (`data/mainstream.db` — Soberana e Permanente):** `279.362` obras e `4.529.748` episódios canônicos (`IMDbCatalogShow` + `MediaWork`). Detém 100% da verdade sobre títulos, sinopses PT-BR, pôsteres, notas IMDb, gêneros e plataformas de streaming.
- **Camada 2 (`data/sources.db` — Semi-Efêmera Bipartida):** As fontes externas (`EZTV`, `YTS / YIFY`, `Torrent-Api-py`, `Torznab`) fornecem artefatos efêmeros (hashes, magnets, seeds, peers, qualidades). A sincronia é dividida em **2 Etapas**:
  1. **Etapa 1 — Sincronia Estrutural de Presença (`Incremental Delta`, `Baseline Denso`, `Minha Biblioteca` & `Poda de Obsoletos`):** Descobre *quais* obras canônicas (`imdb_id`) possuem mídia ativa em cada provedor, resolvendo títulos limpos contra `mainstream.db`, acendendo `has_media` / `media_sources` e podando releases mortos (`seeds == 0` ou expirados).
  2. **Etapa 2 — Hidratação Efêmera Just-in-Time (`Stale-While-Revalidate` + `Replace-on-Success` no Clique do Card / `TorrentModal.tsx`):** Exibe o snapshot local em `0ms` e consulta ao vivo as fontes compatíveis com o formato da obra (`movie` vs `tv_show`), atualizando seeds/peers, removendo torrents mortos daquele título (`Replace-on-Success`) e carregando a faixa **"Inteligência YTS"** (`movie_details.json`, `movie_suggestions.json`, `movie_parental_guides.json`).

---

## 2. Especificações Oficiais de Protocolo (`sources-apis.md`)

1. **YTS API v2 (`https://movies-api.accel.li/api/v2/`):**
   - `list_movies.json`: `limit` (`1..50`), `page`, `quality` (`480p`, `720p`, `1080p`, `1080p.x265`, `2160p`, `3D`), `minimum_rating` (`0..9`), `query_term` (Title / `ttXXXXXXX` / Actor / Director), `genre`, `sort_by` (`date_added`, `seeds`, `download_count`, `rating`, `year`, `title`, `peers`, `like_count`), `order_by` (`desc`, `asc`), `with_rt_ratings=true`.
   - `movie_details.json`: `movie_id` ou `imdb_id`, `with_images=true`, `with_cast=true`.
   - `movie_suggestions.json`: `movie_id` (4 sugestões relacionadas).
   - `movie_parental_guides.json`: `movie_id` (guias parentais).
   - **Magnet URL Oficial (`build_official_magnet`):** `magnet:?xt=urn:btih:{HASH}&dn={quote_plus(title)}` + 10 trackers oficiais (`udp://tracker.opentrackr.org:1337/announce`, `udp://tracker.torrent.eu.org:451/announce`, `udp://tracker.dler.org:6969/announce`, `udp://open.stealth.si:80/announce`, `udp://open.demonii.com:1337/announce`, `https://tracker.moeblog.cn:443/announce`, `udp://open.dstud.io:6969/announce`, `udp://tracker.srv00.com:6969/announce`, `https://tracker.zhuqiy.com:443/announce`, `https://tracker.pmman.tech:443/announce`).
2. **EZTV API (`https://eztvx.to/api/get-torrents`):**
   - Paginação: `?limit=100&page=1..100`.
   - Lookup exato por IMDb ID numérico sem `tt`: `?imdb_id=6048596` (`imdb_id.lstrip("t")`).
   - Feed RSS oficial: `https://myrss.org/eztv` e Health URL: `https://eztvstatus.org/`.
3. **Catálogo `Ryuk-me/Torrent-Api-py` (12 Provedores + Quarteto Resiliente Default):**
   - Suporte completo a `tgx` (TorrentGalaxy), `nyaasi` (Nyaa.si), `bitsearch` (BitSearch), `glodls` (GloDLS), `magnetdl` (MagnetDL), `limetorrent` (LimeTorrents), `torlock` (Torlock), `kickass` (Kickass), `zooqle` (Zooqle), `yts` (YTS Sidecar), `1337x` e `piratebay`.
   - Dual-mode: `/api/v1/recent?site=<site>` (Etapa 1: `supports_sync = True`) e `/api/v1/search?site=<site>&query=<q>` (Etapa 2).
   - Quarteto padrão pré-configurado em `DEFAULT_SOURCE_INSTANCES`: `tgx`, `nyaasi`, `bitsearch`, `glodls`.
