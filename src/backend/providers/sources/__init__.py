"""Dynamic autodiscovery package for external source adapters (ADR-013)."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from src.backend.providers.sources.base import (
    ADAPTER_LOAD_ERRORS,
    ADAPTER_REGISTRY,
    AdapterSearchOutcome,
    BaseSourceAdapter,
    NormalizedReleaseCandidate,
    SourceDiagnostic,
    SourceQueryContext,
    register_source_adapter,
    validate_safe_url,
)

_DISCOVERED = False


def discover_source_adapters(force: bool = False) -> dict[str, BaseSourceAdapter]:
    """Autodiscover all *_adapter.py modules in this package with fault isolation."""
    global _DISCOVERED
    if _DISCOVERED and not force and ADAPTER_REGISTRY:
        return ADAPTER_REGISTRY

    pkg_dir = Path(__file__).resolve().parent
    for mod_info in pkgutil.iter_modules([str(pkg_dir)]):
        mod_name = mod_info.name
        if mod_name in ("__init__", "base") or mod_name.startswith("_"):
            continue
        fq_name = f"{__name__}.{mod_name}"
        try:
            importlib.import_module(fq_name)
            ADAPTER_LOAD_ERRORS.pop(mod_name, None)
        except Exception as exc:
            ADAPTER_LOAD_ERRORS[mod_name] = str(exc)

    _DISCOVERED = True
    return ADAPTER_REGISTRY


__all__ = [
    "ADAPTER_LOAD_ERRORS",
    "ADAPTER_REGISTRY",
    "AdapterSearchOutcome",
    "BaseSourceAdapter",
    "NormalizedReleaseCandidate",
    "SourceDiagnostic",
    "SourceQueryContext",
    "discover_source_adapters",
    "register_source_adapter",
    "validate_safe_url",
]
