"""Single Source of Truth for canonical genres, streaming providers, formats, and data sources."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

ALL_CANONICAL_GENRES: tuple[str, ...] = (
    "Drama",
    "Comédia",
    "Romance",
    "Suspense",
    "Ação",
    "Crime & Investigação",
    "Documentário",
    "Aventura",
    "Terror",
    "Família",
    "Mistério",
    "Fantasia",
    "Ficção Científica",
    "Cinema TV",
    "Animação",
    "História",
    "Música",
    "Biografia",
    "Guerra & Política",
    "Reality-TV",
    "Faroeste",
    "Musical",
    "Esporte",
    "Infantil / Kids",
    "Talk-Show",
    "Game-Show",
    "Adulto",
    "Novela / Soap",
    "Notícias",
    "Film-Noir",
    "Curta-Metragem",
)

# Maps lowercase/folded genre tokens (EN & PT-BR) to canonical PT-BR genre(s).
# Compound TMDB TV genres split cleanly into their component canonical genres.
_GENRE_TOKEN_TO_CANONICAL: dict[str, tuple[str, ...]] = {
    "drama": ("Drama",),
    "comedy": ("Comédia",),
    "comédia": ("Comédia",),
    "comedia": ("Comédia",),
    "romance": ("Romance",),
    "action": ("Ação",),
    "ação": ("Ação",),
    "acao": ("Ação",),
    "action & adventure": ("Ação", "Aventura"),
    "action and adventure": ("Ação", "Aventura"),
    "thriller": ("Suspense",),
    "suspense": ("Suspense",),
    "documentary": ("Documentário",),
    "documentário": ("Documentário",),
    "documentario": ("Documentário",),
    "crime": ("Crime & Investigação",),
    "crime & investigação": ("Crime & Investigação",),
    "crime & investigacao": ("Crime & Investigação",),
    "crime and investigacao": ("Crime & Investigação",),
    "crime investigacao": ("Crime & Investigação",),
    "policial": ("Crime & Investigação",),
    "horror": ("Terror",),
    "terror": ("Terror",),
    "adventure": ("Aventura",),
    "aventura": ("Aventura",),
    "mystery": ("Mistério",),
    "mistério": ("Mistério",),
    "misterio": ("Mistério",),
    "family": ("Família",),
    "família": ("Família",),
    "familia": ("Família",),
    "kids": ("Infantil / Kids",),
    "infantil": ("Infantil / Kids",),
    "infantil / kids": ("Infantil / Kids",),
    "anime": ("Animação",),
    "animation": ("Animação",),
    "animação": ("Animação",),
    "animacao": ("Animação",),
    "food": ("Reality-TV",),
    "diy": ("Reality-TV",),
    "nature": ("Documentário",),
    "travel": ("Documentário",),
    "medical": ("Drama",),
    "supernatural": ("Fantasia",),
    "legal": ("Crime & Investigação",),
    "fantasy": ("Fantasia",),
    "fantasia": ("Fantasia",),
    "sci-fi": ("Ficção Científica",),
    "sci fi": ("Ficção Científica",),
    "science fiction": ("Ficção Científica",),
    "science-fiction": ("Ficção Científica",),
    "ficção científica": ("Ficção Científica",),
    "ficcao cientifica": ("Ficção Científica",),
    "sci-fi & fantasy": ("Ficção Científica", "Fantasia"),
    "sci-fi and fantasy": ("Ficção Científica", "Fantasia"),
    "history": ("História",),
    "história": ("História",),
    "historia": ("História",),
    "biography": ("Biografia",),
    "biografia": ("Biografia",),
    "music": ("Música",),
    "música": ("Música",),
    "musica": ("Música",),
    "musical": ("Musical",),
    "war": ("Guerra & Política",),
    "guerra": ("Guerra & Política",),
    "war & politics": ("Guerra & Política",),
    "guerra & política": ("Guerra & Política",),
    "guerra & politica": ("Guerra & Política",),
    "guerra e politica": ("Guerra & Política",),
    "guerra politica": ("Guerra & Política",),
    "politics": ("Guerra & Política",),
    "western": ("Faroeste",),
    "faroeste": ("Faroeste",),
    "sport": ("Esporte",),
    "sports": ("Esporte",),
    "esporte": ("Esporte",),
    "reality-tv": ("Reality-TV",),
    "reality tv": ("Reality-TV",),
    "reality": ("Reality-TV",),
    "cinema tv": ("Cinema TV",),
    "tv movie": ("Cinema TV",),
    "game-show": ("Game-Show",),
    "game show": ("Game-Show",),
    "talk-show": ("Talk-Show",),
    "talk show": ("Talk-Show",),
    "talk": ("Talk-Show",),
    "soap": ("Novela / Soap",),
    "novela / soap": ("Novela / Soap",),
    "novela": ("Novela / Soap",),
    "news": ("Notícias",),
    "notícias": ("Notícias",),
    "noticias": ("Notícias",),
    "film-noir": ("Film-Noir",),
    "film noir": ("Film-Noir",),
    "short": ("Curta-Metragem",),
    "curta-metragem": ("Curta-Metragem",),
    "adult": ("Adulto",),
    "adulto": ("Adulto",),
}

# Compact SQL synonym list per canonical genre (actual DB tokens only, minimizing SQL LIKE clauses).
_CANONICAL_TO_RAW_SYNONYMS: dict[str, list[str]] = {
    "Drama": ["Drama", "Medical"],
    "Comédia": ["Comédia", "Comedy"],
    "Romance": ["Romance"],
    "Suspense": ["Suspense", "Thriller"],
    "Ação": ["Ação", "Action", "Action & Adventure"],
    "Crime & Investigação": ["Crime & Investigação", "Crime", "Policial", "Legal"],
    "Documentário": ["Documentário", "Documentary", "Nature", "Travel"],
    "Aventura": ["Aventura", "Adventure", "Action & Adventure"],
    "Terror": ["Terror", "Horror"],
    "Família": ["Família", "Family"],
    "Mistério": ["Mistério", "Mystery"],
    "Fantasia": ["Fantasia", "Fantasy", "Sci-Fi & Fantasy", "Supernatural"],
    "Ficção Científica": ["Ficção Científica", "Sci-Fi", "Science Fiction", "Sci-Fi & Fantasy"],
    "Cinema TV": ["Cinema TV", "TV Movie"],
    "Animação": ["Animação", "Animation", "Anime"],
    "História": ["História", "History"],
    "Música": ["Música", "Music"],
    "Biografia": ["Biografia", "Biography"],
    "Guerra & Política": ["Guerra & Política", "War", "War & Politics", "Guerra"],
    "Reality-TV": ["Reality-TV", "Reality", "Food", "DIY"],
    "Faroeste": ["Faroeste", "Western"],
    "Musical": ["Musical"],
    "Esporte": ["Esporte", "Sport", "Sports"],
    "Infantil / Kids": ["Infantil / Kids", "Kids"],
    "Talk-Show": ["Talk-Show", "Talk"],
    "Game-Show": ["Game-Show"],
    "Adulto": ["Adulto", "Adult"],
    "Novela / Soap": ["Novela / Soap", "Soap"],
    "Notícias": ["Notícias", "News"],
    "Film-Noir": ["Film-Noir"],
    "Curta-Metragem": ["Curta-Metragem", "Short"],
}


ALL_CANONICAL_PROVIDERS: tuple[str, ...] = (
    "Netflix",
    "Prime Video",
    "Max",
    "Disney+",
    "Globoplay",
    "Apple TV+",
    "Paramount+",
    "Crunchyroll",
    "MUBI",
    "Looke",
    "Claro tv+",
    "Hulu",
    "Peacock / NBC",
    "BBC",
    "Discovery",
    "FOX / FX",
    "CBS",
    "ABC",
    "YouTube",
    "AMC+",
    "Cartoon Network",
    "Nickelodeon",
    "MTV / Comedy Central",
    "History / A&E",
    "The CW",
)

# Maps lowercase provider/network aliases to canonical streaming/network labels.
_PROVIDER_ALIAS_MAP: dict[str, str] = {
    "netflix": "Netflix",
    "prime video": "Prime Video",
    "amazon prime video": "Prime Video",
    "amazon": "Prime Video",
    "amazon video": "Prime Video",
    "amazon studios": "Prime Video",
    "amazon freevee": "Prime Video",
    "freevee": "Prime Video",
    "mgm+": "Prime Video",
    "max": "Max",
    "hbo max": "Max",
    "hbo": "Max",
    "cinemax": "Max",
    "hbo europe": "Max",
    "hbo latin america": "Max",
    "hbo brasil": "Max",
    "hbo asia": "Max",
    "disney+": "Disney+",
    "disney plus": "Disney+",
    "disney channel": "Disney+",
    "disney xd": "Disney+",
    "disney junior": "Disney+",
    "apple tv+": "Apple TV+",
    "apple tv": "Apple TV+",
    "apple tv plus": "Apple TV+",
    "apple tv store": "Apple TV+",
    "paramount+": "Paramount+",
    "paramount plus": "Paramount+",
    "paramount network": "Paramount+",
    "showtime": "Paramount+",
    "cbs all access": "Paramount+",
    "globoplay": "Globoplay",
    "tv globo": "Globoplay",
    "rede globo": "Globoplay",
    "multishow": "Globoplay",
    "gnt": "Globoplay",
    "canal brasil": "Globoplay",
    "globonews": "Globoplay",
    "viva": "Globoplay",
    "mubi": "MUBI",
    "crunchyroll": "Crunchyroll",
    "funimation": "Crunchyroll",
    "tokyo mx": "Crunchyroll",
    "tv tokyo": "Crunchyroll",
    "at-x": "Crunchyroll",
    "fuji tv": "Crunchyroll",
    "tbs": "Crunchyroll",
    "mbs": "Crunchyroll",
    "bs11": "Crunchyroll",
    "tv asahi": "Crunchyroll",
    "nippon tv": "Crunchyroll",
    "ntv": "Crunchyroll",
    "wowow": "Crunchyroll",
    "looke": "Looke",
    "claro tv+": "Claro tv+",
    "claro video": "Claro tv+",
    "hulu": "Hulu",
    "star+": "Hulu",
    "peacock": "Peacock / NBC",
    "peacock / nbc": "Peacock / NBC",
    "nbc": "Peacock / NBC",
    "usa network": "Peacock / NBC",
    "syfy": "Peacock / NBC",
    "bravo": "Peacock / NBC",
    "msnbc": "Peacock / NBC",
    "telemundo": "Peacock / NBC",
    "bbc": "BBC",
    "bbc iplayer": "BBC",
    "bbc one": "BBC",
    "bbc two": "BBC",
    "bbc three": "BBC",
    "bbc four": "BBC",
    "cbbc": "BBC",
    "cbeebies": "BBC",
    "discovery": "Discovery",
    "discovery+": "Discovery",
    "discovery channel": "Discovery",
    "investigation discovery": "Discovery",
    "tlc": "Discovery",
    "animal planet": "Discovery",
    "hgtv": "Discovery",
    "food network": "Discovery",
    "fox": "FOX / FX",
    "fx": "FOX / FX",
    "fxx": "FOX / FX",
    "fox / fx": "FOX / FX",
    "national geographic": "FOX / FX",
    "nat geo wild": "FOX / FX",
    "cbs": "CBS",
    "abc": "ABC",
    "abc tv": "ABC",
    "freeform": "ABC",
    "youtube": "YouTube",
    "youtube premium": "YouTube",
    "youtube red": "YouTube",
    "amc": "AMC+",
    "amc+": "AMC+",
    "bbc america": "AMC+",
    "ifc": "AMC+",
    "sundancetv": "AMC+",
    "shudder": "AMC+",
    "cartoon network": "Cartoon Network",
    "adult swim": "Cartoon Network",
    "boomerang": "Cartoon Network",
    "toonami": "Cartoon Network",
    "nickelodeon": "Nickelodeon",
    "nick jr.": "Nickelodeon",
    "nicktoons": "Nickelodeon",
    "teennick": "Nickelodeon",
    "mtv": "MTV / Comedy Central",
    "comedy central": "MTV / Comedy Central",
    "mtv / comedy central": "MTV / Comedy Central",
    "vh1": "MTV / Comedy Central",
    "bet": "MTV / Comedy Central",
    "history": "History / A&E",
    "history / a&e": "History / A&E",
    "a&e": "History / A&E",
    "lifetime": "History / A&E",
    "the cw": "The CW",
    "cw": "The CW",
    "upn": "The CW",
    "the wb": "The CW",
}

_PROVIDER_REVERSE_ALIASES: dict[str, list[str]] = {}
for _alias, _canon_p in _PROVIDER_ALIAS_MAP.items():
    _plist = _PROVIDER_REVERSE_ALIASES.setdefault(_canon_p, [_canon_p])
    if _alias not in [x.lower() for x in _plist]:
        _plist.append(_alias)

# Canonical TMDB watch provider IDs -> (canonical_name, tmdb_provider_id, region, max_pages)
TMDB_DISCOVER_PROVIDERS: list[tuple[str, int, str, int]] = [
    ("Netflix", 8, "BR", 60),
    ("Prime Video", 119, "BR", 50),
    ("Max", 1899, "BR", 45),
    ("Disney+", 337, "BR", 45),
    ("Globoplay", 307, "BR", 40),
    ("Crunchyroll", 283, "BR", 35),
    ("Looke", 47, "BR", 35),
    ("Claro tv+", 484, "BR", 30),
    ("Claro tv+", 167, "BR", 20),
    ("Paramount+", 531, "BR", 20),
    ("Apple TV+", 350, "BR", 15),
    ("MUBI", 11, "BR", 30),
    ("Hulu", 15, "US", 30),
    ("Peacock / NBC", 386, "US", 25),
]

WORK_TYPE_KEYS: tuple[str, ...] = (
    "movie",
    "tv_show",
    "mini_series",
    "tv_movie",
    "documentary",
    "animation",
    "special",
    "short",
)

DATA_SOURCE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("eztv", "EZTV P2P (sources.db)"),
    ("yify", "YIFY / YTS (sources.db)"),
    ("1337x", "1337x (sources.db)"),
    ("p2p_active", "Torrents / Magnets Ativos"),
    ("imdb", "IMDb Universal"),
    ("tmdb", "TMDB Hidratado"),
    ("ptbr", "Sinopse PT-BR"),
    ("youtube_trailer", "Com Trailer YouTube"),
    ("tvmaze", "TVMaze Séries"),
    ("personal_library", "Minha Biblioteca"),
)


def _fold_key(raw: str) -> str:
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", folded.strip().lower())


_FOLDED_GENRE_LOOKUP: dict[str, tuple[str, ...]] = {
    _fold_key(k): v for k, v in _GENRE_TOKEN_TO_CANONICAL.items()
}
for _canon_g in ALL_CANONICAL_GENRES:
    _FOLDED_GENRE_LOOKUP.setdefault(_fold_key(_canon_g), (_canon_g,))

_FOLDED_PROVIDER_LOOKUP: dict[str, str] = {_fold_key(k): v for k, v in _PROVIDER_ALIAS_MAP.items()}
for _canon_p in ALL_CANONICAL_PROVIDERS:
    _FOLDED_PROVIDER_LOOKUP.setdefault(_fold_key(_canon_p), _canon_p)


def normalize_genre_tokens(raw: Optional[str]) -> list[str]:
    """Normalize a comma-separated genre string into canonical PT-BR genre names."""
    if not raw:
        return []
    seen: dict[str, None] = {}
    for part in raw.split(","):
        clean = part.strip()
        if not clean:
            continue
        direct = _GENRE_TOKEN_TO_CANONICAL.get(clean.lower())
        if direct is None:
            direct = _FOLDED_GENRE_LOOKUP.get(_fold_key(clean))
        if direct:
            for item in direct:
                seen[item] = None
        else:
            seen[clean] = None
    return list(seen.keys())


def merge_canonical_genres(*raw_fields: Optional[str]) -> list[str]:
    """Merge multiple genre CSV fields into a deduplicated canonical PT-BR list."""
    seen: dict[str, None] = {}
    for field in raw_fields:
        for g in normalize_genre_tokens(field):
            seen[g] = None
    return list(seen.keys())


def expand_genre_synonyms(raw_genre: str) -> list[str]:
    """Return canonical + legacy raw database tokens matching a requested genre."""
    canonical_targets = normalize_genre_tokens(raw_genre)
    syns: dict[str, None] = {}
    for canon in canonical_targets:
        syns[canon] = None
        for s in _CANONICAL_TO_RAW_SYNONYMS.get(canon, []):
            syns[s] = None
    if raw_genre.strip():
        syns[raw_genre.strip()] = None
    return list(syns.keys())


def normalize_provider_tokens(raw: Optional[str], keep_unknown: bool = False) -> list[str]:
    """Normalize streaming provider / network CSV tokens into canonical service names."""
    if not raw:
        return []
    seen: dict[str, None] = {}
    for part in raw.split(","):
        clean = part.strip()
        if not clean:
            continue
        mapped = _PROVIDER_ALIAS_MAP.get(clean.lower())
        if mapped is None:
            mapped = _FOLDED_PROVIDER_LOOKUP.get(_fold_key(clean))
        if mapped:
            seen[mapped] = None
        elif keep_unknown:
            seen[clean] = None
    return list(seen.keys())


def merge_canonical_providers(*raw_fields: Optional[str], keep_unknown: bool = False) -> list[str]:
    """Merge streaming_providers and network fields into ordered canonical providers."""
    seen: dict[str, None] = {}
    for field in raw_fields:
        for p in normalize_provider_tokens(field, keep_unknown=keep_unknown):
            seen[p] = None
    return list(seen.keys())


def expand_provider_aliases(raw_provider: str) -> list[str]:
    """Return canonical provider key plus raw network/streaming aliases for SQL pushdown."""
    clean = raw_provider.strip()
    if not clean:
        return []
    mapped = _PROVIDER_ALIAS_MAP.get(clean.lower()) or _FOLDED_PROVIDER_LOOKUP.get(_fold_key(clean))
    if not mapped:
        return [clean]
    aliases: dict[str, None] = {mapped: None, clean: None}
    for al in _PROVIDER_REVERSE_ALIASES.get(mapped, []):
        aliases[al] = None
    return list(aliases.keys())


def normalize_status_label(raw_status: Optional[str]) -> Optional[str]:
    """Normalize raw status strings into canonical filterable buckets."""
    if not raw_status:
        return None
    low = raw_status.strip().lower()
    if low in ("unknown", ""):
        return None
    if low in ("running", "returning series", "airing", "in production"):
        return "Running"
    if low in ("ended", "completed"):
        return "Ended"
    if low in ("to be determined", "tbd"):
        return "To Be Determined"
    if low in ("released",):
        return "Released"
    if low in ("canceled", "cancelled"):
        return "Canceled"
    return raw_status.strip()


def extract_tmdb_watch_providers(full_data: dict) -> list[str]:
    """Extract canonical streaming providers from TMDB networks + watch/providers node."""
    found: dict[str, None] = {}

    for net in (full_data.get("networks") or [])[:6]:
        name = (net.get("name") or "").strip() if isinstance(net, dict) else ""
        for p in normalize_provider_tokens(name, keep_unknown=False):
            found[p] = None

    wp_results = (full_data.get("watch/providers") or {}).get("results") or {}
    for region in ("BR", "US"):
        reg_node = wp_results.get(region) or {}
        for bucket in ("flatrate", "free", "ads"):
            for entry in reg_node.get(bucket) or []:
                pname = (entry.get("provider_name") or "").strip()
                for p in normalize_provider_tokens(pname, keep_unknown=False):
                    found[p] = None

    return list(found.keys())


def empty_facet_template() -> dict[str, list[dict[str, int | str]]]:
    """Return initialized empty facet structure."""
    return {
        "work_types": [],
        "data_sources": [],
        "genres": [],
        "streaming_providers": [],
        "decades": [],
        "statuses": [],
        "countries": [],
    }


def list_all_canonical_genres_sorted(
    counts: Optional[Iterable[tuple[str, int]]] = None,
) -> list[str]:
    """Helper returning all canonical genres, optionally ordered by popularity."""
    if counts is None:
        return list(ALL_CANONICAL_GENRES)
    score_map = {k: v for k, v in counts}
    return sorted(ALL_CANONICAL_GENRES, key=lambda g: score_map.get(g, 0), reverse=True)
