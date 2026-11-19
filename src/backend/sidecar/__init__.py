"""Embedded and standalone sidecar services for TV Pirata."""

from src.backend.sidecar.torrent_api_sidecar import (
    EmbeddedSidecarManager,
    sidecar_app,
    sidecar_manager,
)

__all__ = ["EmbeddedSidecarManager", "sidecar_app", "sidecar_manager"]
