"""Core plugin contract, security guards, and matching utilities for external sources."""

from __future__ import annotations

import difflib
import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Literal, Optional, TypeVar
from urllib.parse import quote_plus, urlparse

from pydantic import BaseModel, Field
from sqlmodel import Session

from src.backend.models.sources_db import ExternalSourceRecord

SourceKind = Literal["torrent_mirrorable", "unique_web_source"]
DiagnosticStatus = Literal["ok", "challenge_required", "cooldown", "timeout", "error"]

SECRET_MASK_PREFIX = "••••"

OFFICIAL_YTS_TRACKERS: tuple[str, ...] = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://open.stealth.si:80/announce",
    "udp://open.demonii.com:1337/announce",
    "https://tracker.moeblog.cn:443/announce",
    "udp://open.dstud.io:6969/announce",
    "udp://tracker.srv00.com:6969/announce",
    "https://tracker.zhuqiy.com:443/announce",
    "https://tracker.pmman.tech:443/announce",
)


def build_official_magnet(
    info_hash: Optional[str],
    title: str,
    trackers: Optional[list[str] | tuple[str, ...]] = None,
) -> Optional[str]:
    """Construct URL-safe official magnet link with quote_plus(dn) and 10 recommended trackers."""
    clean_hash = re.sub(r"[^a-fA-F0-9]", "", str(info_hash or "").strip())
    if len(clean_hash) < 32:
        return None
    dn = quote_plus((title or "release").strip())
    active_trackers = trackers if trackers is not None else OFFICIAL_YTS_TRACKERS
    tr_params = "".join(f"&tr={tr}" for tr in active_trackers if tr)
    return validate_safe_url(f"magnet:?xt=urn:btih:{clean_hash}&dn={dn}{tr_params}", ("magnet",))


def parse_release_title_and_year(
    raw_title: str,
) -> tuple[str, Optional[int], int, int, str]:
    """Extract (clean_title, year, season, episode, quality) from a raw torrent release title."""
    text = (raw_title or "").strip()
    year, season, episode = extract_release_year_and_se(text)
    low = text.lower()
    if "2160p" in low or "4k" in low or "uhd" in low:
        quality = "2160p"
    elif "1080p" in low and ("x265" in low or "hevc" in low):
        quality = "1080p.x265"
    elif "1080p" in low:
        quality = "1080p"
    elif "720p" in low:
        quality = "720p"
    elif "480p" in low:
        quality = "480p"
    else:
        quality = "Unknown"

    normalized = re.sub(r"[._\[\]\(\)]+", " ", text)
    head = re.split(
        r"\b(?:19\d{2}|20\d{2}|[sS]\d{1,2}[eE]\d{1,3}|[sS]eason\s*\d+|2160p|1080p|720p|480p|4k|uhd|bluray|bdrip|brrip|webrip|web-dl|web|hdtv|dvdrip|x264|x265|hevc|h264|h265|aac|ddp5|proper|repack)\b",
        normalized,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    clean_title = re.sub(r"\s+", " ", head).strip(" -:")
    if not clean_title:
        clean_title = re.sub(r"\s+", " ", normalized).strip()[:80]
    return clean_title, year, season, episode, quality


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def validate_safe_url(
    raw_url: Optional[str],
    allowed_schemes: tuple[str, ...] = ("http", "https", "magnet"),
) -> Optional[str]:
    """Validate and sanitize external URLs against scheme injection (javascript:, data:, etc.)."""
    if not raw_url or not isinstance(raw_url, str):
        return None
    cleaned = raw_url.strip()
    if not cleaned:
        return None
    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "").lower()
    if scheme not in allowed_schemes:
        return None
    if scheme in ("http", "https"):
        if not parsed.netloc or " " in parsed.netloc:
            return None
        return cleaned
    if scheme == "magnet":
        if not cleaned.lower().startswith("magnet:?xt=urn:"):
            return None
        return cleaned
    return None


def mask_secret_config(
    config: dict[str, Any], secret_fields: set[str]
) -> dict[str, Any]:
    """Mask secret configuration values before returning over REST API."""
    masked: dict[str, Any] = {}
    for key, val in config.items():
        if key in secret_fields:
            str_val = str(val or "").strip()
            if str_val:
                suffix = str_val[-4:] if len(str_val) > 4 else ""
                masked[key] = f"{SECRET_MASK_PREFIX}{suffix}"
                masked[f"{key}__has_secret"] = True
            else:
                masked[key] = ""
                masked[f"{key}__has_secret"] = False
        else:
            masked[key] = val
    for s_key in secret_fields:
        if s_key not in masked:
            masked[s_key] = ""
            masked[f"{s_key}__has_secret"] = False
    return masked


def merge_preserving_secrets(
    existing_config: dict[str, Any],
    incoming_config: dict[str, Any],
    secret_fields: set[str],
) -> dict[str, Any]:
    """Merge incoming configuration while preserving existing secrets if masked/empty (RT13-02)."""
    merged = dict(existing_config)
    for key, val in incoming_config.items():
        if key.endswith("__has_secret"):
            continue
        if key in secret_fields:
            if val is None:
                continue
            if isinstance(val, dict) and val.get("has_secret"):
                continue
            str_val = str(val).strip()
            if not str_val or str_val.startswith(SECRET_MASK_PREFIX) or str_val == "***":
                continue
            merged[key] = str_val
        else:
            merged[key] = val
    return merged


def is_antibot_challenge(
    status_code: int,
    body_text: str = "",
    headers: Optional[dict[str, str]] = None,
) -> bool:
    """Detect Cloudflare Turnstile, reCAPTCHA, hCaptcha, or WAF anti-bot challenge responses."""
    hdrs = {k.lower(): v.lower() for k, v in (headers or {}).items()}
    if "cf-mitigated" in hdrs or hdrs.get("server") == "cloudflare" and status_code in (403, 503):
        return True
    low = (body_text or "")[:8000].lower()
    challenge_markers = (
        "cf-turnstile",
        "challenges.cloudflare.com",
        "just a moment...",
        "attention required! | cloudflare",
        "g-recaptcha",
        "h-captcha",
        "verify you are human",
        "captcha-delivery",
        "ddos-guard",
    )
    if status_code in (403, 429, 503) and any(m in low for m in challenge_markers):
        return True
    return any(m in low for m in ("cf-turnstile", "g-recaptcha", "verify you are human"))


def _normalize_title_tokens(raw: str) -> str:
    folded = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", folded.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_release_year_and_se(title: str) -> tuple[Optional[int], int, int]:
    """Extract 4-digit year and SxxExx season/episode from a raw release title."""
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", title or "")
    year = int(year_match.group(1)) if year_match else None
    se_match = re.search(r"\b[sS](\d{1,2})[eE](\d{1,3})\b", title or "")
    if se_match:
        return year, int(se_match.group(1)), int(se_match.group(2))
    return year, 0, 0


def compute_title_match_confidence(
    *,
    query_title: str,
    query_original_title: Optional[str] = None,
    query_year: Optional[int] = None,
    query_work_type: Optional[str] = None,
    candidate_title: str,
    candidate_year: Optional[int] = None,
) -> float:
    """Compute [0.0, 1.0] entity resolution confidence for a release without IMDb ID (RT13-04)."""
    cand_norm = _normalize_title_tokens(candidate_title)
    if not cand_norm:
        return 0.0

    ext_year, season, episode = extract_release_year_and_se(candidate_title)
    eff_cand_year = candidate_year or ext_year

    # Strip technical release tokens from candidate title before comparing
    stripped_cand = re.split(
        r"\b(?:19\d{2}|20\d{2}|s\d{1,2}e\d{1,3}|1080p|720p|2160p|4k|bluray|webrip|web|hdtv|x264|x265|hevc)\b",
        cand_norm,
    )[0].strip()
    if not stripped_cand:
        stripped_cand = cand_norm

    targets = [
        _normalize_title_tokens(t)
        for t in (query_title, query_original_title)
        if t and _normalize_title_tokens(t)
    ]
    if not targets:
        return 0.0

    best_ratio = 0.0
    exact_title_hit = False
    for target in targets:
        if stripped_cand == target:
            exact_title_hit = True
            best_ratio = 1.0
            break
        ratio = difflib.SequenceMatcher(None, target, stripped_cand).ratio()
        if stripped_cand.startswith(f"{target} ") and len(target) >= 5:
            ratio = max(ratio, 0.88)
        best_ratio = max(best_ratio, ratio)

    score = best_ratio * 0.78

    # Year verification bonus / penalty
    if query_year and eff_cand_year:
        diff = abs(int(query_year) - int(eff_cand_year))
        if diff == 0:
            score += 0.20
        elif diff == 1:
            score += 0.14
        else:
            score -= 0.30
    elif exact_title_hit and len(targets[0]) >= 6 and (season > 0 or not query_year):
        score += 0.12

    # Format consistency check (Movie vs TV Series episodic release)
    is_tv_query = query_work_type in ("tvSeries", "tv_show", "mini_series", "tvMiniSeries")
    if is_tv_query and season > 0:
        score += 0.08
    elif query_work_type == "movie" and season > 0:
        score -= 0.25

    # Short/ambiguous title guard (e.g. "Dark", "Home") without year or SxxExx
    if len(targets[0]) <= 4 and not (
        (query_year and eff_cand_year and abs(query_year - eff_cand_year) <= 1) or season > 0
    ):
        score = min(score, 0.75)

    return round(max(0.0, min(1.0, score)), 3)


class SourceQueryContext(BaseModel):
    """Canonical query payload for on-demand source adapter searches."""

    imdb_id: Optional[str] = None
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    work_type: Optional[str] = None
    custom_query: Optional[str] = None
    limit: int = 50


class NormalizedReleaseCandidate(BaseModel):
    """Normalized release candidate returned by an adapter before persistence."""

    external_id: str
    imdb_id: Optional[str] = None
    title: str
    work_type: str = "movie"
    season: int = 0
    episode: int = 0
    quality: str = "Unknown"
    seeds: int = 0
    peers: int = 0
    size_bytes: int = 0
    release_type: Literal["magnet", "torrent", "link"] = "magnet"
    magnet_url: Optional[str] = None
    torrent_url: Optional[str] = None
    external_url: Optional[str] = None
    info_hash: Optional[str] = None
    poster_url: Optional[str] = None
    genres: Optional[str] = None
    year: Optional[int] = None
    rating: float = 0.0
    matched_by: str = "exact_imdb"
    match_confidence: float = 1.0


class SourceDiagnostic(BaseModel):
    """Per-source execution diagnostic returned to the modal and config UI."""

    source_key: str
    source_name: str
    adapter_key: str
    source_kind: SourceKind = "torrent_mirrorable"
    status: DiagnosticStatus = "ok"
    message: Optional[str] = None
    challenge_url: Optional[str] = None
    from_cache: bool = False
    cached_at: Optional[str] = None
    latency_ms: int = 0


class AdapterSearchOutcome(BaseModel):
    """Result envelope produced by BaseSourceAdapter.search()."""

    status: DiagnosticStatus = "ok"
    releases: list[NormalizedReleaseCandidate] = Field(default_factory=list)
    message: Optional[str] = None
    challenge_url: Optional[str] = None


class BaseSourceAdapter(ABC):
    """Polymorphic contract for pluggable external media source adapters (1:N instances)."""

    adapter_key: str
    display_name: str
    description: str = ""
    default_source_kind: SourceKind = "torrent_mirrorable"
    default_media_types: str = "movie,tvSeries"
    supports_sync: bool = False
    supports_search: bool = True

    @classmethod
    def config_model(cls) -> type[BaseModel]:
        """Return Pydantic config schema class for dynamic UI form generation."""
        return DefaultAdapterConfig

    @classmethod
    def secret_fields(cls) -> set[str]:
        """Return set of field names in config_model marked with secret=True."""
        secrets: set[str] = set()
        for name, field_info in cls.config_model().model_fields.items():
            extra = field_info.json_schema_extra
            if isinstance(extra, dict) and extra.get("secret") is True:
                secrets.add(name)
        return secrets

    @classmethod
    def config_json_schema(cls) -> dict[str, Any]:
        """Return JSON schema describing adapter configuration fields."""
        return cls.config_model().model_json_schema()

    async def sync(
        self,
        instance: ExternalSourceRecord,
        sources_session: Session,
        mainstream_session: Optional[Session] = None,
        *,
        pages: int = 2,
        enrich: bool = False,
    ) -> dict[str, Any]:
        """Batch synchronize catalog pages if supported by this adapter."""
        return {
            "source": instance.source_key,
            "adapter": self.adapter_key,
            "releases_indexed": 0,
            "note": f"Adapter '{self.adapter_key}' opera sob demanda (Lazy Search).",
        }

    @abstractmethod
    async def search(
        self,
        instance: ExternalSourceRecord,
        query_ctx: SourceQueryContext,
        sources_session: Optional[Session] = None,
        mainstream_session: Optional[Session] = None,
    ) -> AdapterSearchOutcome:
        """Execute on-demand search for an audiovisual work."""

    async def healthcheck(
        self,
        instance: ExternalSourceRecord,
        sources_session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """Verify connectivity or readiness of a configured source instance."""
        outcome = await self.search(
            instance,
            SourceQueryContext(title="Matrix", year=1999, imdb_id="tt0133093", limit=5),
            sources_session=sources_session,
        )
        return {
            "status": outcome.status,
            "releases_found": len(outcome.releases),
            "message": outcome.message,
            "challenge_url": outcome.challenge_url,
        }


class DefaultAdapterConfig(BaseModel):
    """Default configuration schema shared by simple HTTP adapters."""

    base_url: str = Field(default="", title="URL Principal")
    mirrors: list[str] = Field(default_factory=list, title="Mirrors / URLs Alternativas")
    timeout_seconds: float = Field(default=6.0, ge=1.0, le=30.0, title="Timeout (s)")
    ttl_hours: int = Field(default=24, ge=1, le=720, title="TTL do Cache (Horas)")


ADAPTER_REGISTRY: dict[str, BaseSourceAdapter] = {}
ADAPTER_LOAD_ERRORS: dict[str, str] = {}

TAdapter = TypeVar("TAdapter", bound=BaseSourceAdapter)


def register_source_adapter(cls: type[TAdapter]) -> type[TAdapter]:
    """Class decorator registering a BaseSourceAdapter into ADAPTER_REGISTRY."""
    instance = cls()
    ADAPTER_REGISTRY[instance.adapter_key] = instance
    return cls
