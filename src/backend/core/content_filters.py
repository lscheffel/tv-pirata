"""Shared global SQL content filters (Foreign Titles Policy & Parental Control)."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import and_, func, not_, or_
from sqlmodel import col

from src.backend.models.catalog_domain import IMDbCatalogShow

ForeignTitlesMode = Literal["off", "lite", "all"]
MoodFilterMode = Literal["all", "no_drama", "darkside", "riseup"]

_OFF_LANG_PREFIXES: tuple[str, ...] = (
    "English",
    "Português",
    "Portugues",
    "Portuguese",
    "en",
    "pt",
)

_LITE_EXTRA_LANG_PREFIXES: tuple[str, ...] = (
    "Español",
    "Espanol",
    "Spanish",
    "es",
    "普通话",
    "广州话",
    "Chinese",
    "Mandarin",
    "Cantonese",
    "zh",
    "cn",
    "한국어",
    "Korean",
    "ko",
)

_OFF_COUNTRIES: tuple[str, ...] = ("US", "GB", "CA", "AU", "NZ", "IE", "BR", "PT")
_LITE_COUNTRIES: tuple[str, ...] = (
    *_OFF_COUNTRIES,
    "ES",
    "MX",
    "AR",
    "CO",
    "CL",
    "CN",
    "HK",
    "TW",
    "KR",
)


def build_foreign_sql_clause(mode: ForeignTitlesMode) -> Any:
    """Build SQLAlchemy WHERE clause enforcing global foreign-language visibility."""
    if mode == "all":
        return None

    lang_prefixes = (
        _OFF_LANG_PREFIXES if mode == "off" else (*_OFF_LANG_PREFIXES, *_LITE_EXTRA_LANG_PREFIXES)
    )
    allowed_countries = _OFF_COUNTRIES if mode == "off" else _LITE_COUNTRIES

    lang_matches = or_(
        *(col(IMDbCatalogShow.languages).startswith(pfx) for pfx in lang_prefixes)
    )
    empty_lang = or_(
        col(IMDbCatalogShow.languages).is_(None),
        col(IMDbCatalogShow.languages) == "",
    )
    empty_country = or_(
        col(IMDbCatalogShow.countries).is_(None),
        col(IMDbCatalogShow.countries) == "",
    )
    country_matches = or_(
        *(col(IMDbCatalogShow.countries).contains(cc) for cc in allowed_countries)
    )
    return or_(lang_matches, and_(empty_lang, or_(empty_country, country_matches)))


def build_parental_sql_clause(enabled: bool) -> Any:
    """Build SQLAlchemy WHERE clause excluding animation, anime, cartoons and kids content."""
    if not enabled:
        return None

    blocked_tokens = ("Animation", "Animação", "Anime", "Kids", "Infantil", "Cartoon")
    not_anim_type = col(IMDbCatalogShow.title_type) != "animation"
    not_blocked_genres = and_(
        *(
            or_(
                col(IMDbCatalogShow.genres).is_(None),
                not_(col(IMDbCatalogShow.genres).contains(tok)),
            )
            for tok in blocked_tokens
        )
    )
    not_blocked_genres_ptbr = and_(
        *(
            or_(
                col(IMDbCatalogShow.genres_ptbr).is_(None),
                not_(col(IMDbCatalogShow.genres_ptbr).contains(tok)),
            )
            for tok in blocked_tokens
        )
    )
    return and_(not_anim_type, not_blocked_genres, not_blocked_genres_ptbr)


_NO_DRAMA_EXACT: tuple[str, ...] = (
    "drama",
    "romance",
    "drama, romance",
    "romance, drama",
    "drama,romance",
    "romance,drama",
)

_DARKSIDE_TOKENS: tuple[str, ...] = (
    "Thriller",
    "Suspense",
    "Sci-Fi",
    "Science Fiction",
    "Ficção Científica",
    "Crime",
    "Mystery",
    "Mistério",
    "Horror",
    "Terror",
    "Film-Noir",
)

_RISEUP_TOKENS: tuple[str, ...] = (
    "Comedy",
    "Comédia",
    "Adventure",
    "Aventura",
    "Action",
    "Ação",
    "Family",
    "Família",
    "Fantasy",
    "Fantasia",
    "Music",
    "Musical",
    "Música",
    "Sport",
    "Esporte",
)


def build_mood_sql_clause(mode: MoodFilterMode) -> Any:
    """Build SQLAlchemy WHERE clause for Mood filter (no_drama, darkside, riseup)."""
    if mode == "all":
        return None
    if mode == "no_drama":
        return and_(
            or_(
                col(IMDbCatalogShow.genres).is_(None),
                not_(func.lower(func.trim(col(IMDbCatalogShow.genres))).in_(_NO_DRAMA_EXACT)),
            ),
            or_(
                col(IMDbCatalogShow.genres_ptbr).is_(None),
                not_(
                    func.lower(func.trim(col(IMDbCatalogShow.genres_ptbr))).in_(_NO_DRAMA_EXACT)
                ),
            ),
        )
    tokens = _DARKSIDE_TOKENS if mode == "darkside" else _RISEUP_TOKENS
    return or_(
        *(col(IMDbCatalogShow.genres).contains(tok) for tok in tokens),
        *(col(IMDbCatalogShow.genres_ptbr).contains(tok) for tok in tokens),
    )
