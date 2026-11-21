"""Native Torrent-Api-py compatible FastAPI Sidecar Server (:8009) & Lifespan Manager.

Implements the Ryuk-me/Torrent-Api-py REST API contract:
  - GET /api/v1/sites
  - GET /api/v1/recent?site=<site>&limit=<n>&page=<p>
  - GET /api/v1/search?site=<site>&query=<q>&limit=<n>&page=<p>
  - GET /api/v1/all/search?query=<q>&limit=<n>
  - GET /health

Can be started standalone on port 8009 (`make run-sidecar` or
`python -m uvicorn src.backend.sidecar.torrent_api_sidecar:sidecar_app --port 8009`)
or automatically managed inside the main FastAPI `lifespan` when `SIDECAR_AUTOSTART=true`
(default in development/homelab, disabled automatically under pytest).
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.backend.providers.sources.torrent_api_py_adapter import (
    TORRENT_API_PY_SITE_CATALOG,
    TorrentApiPySourceAdapter,
)

logger = logging.getLogger(__name__)

sidecar_app = FastAPI(
    title="TV Pirata — Torrent-Api-py Native Sidecar",
    description="Ryuk-me/Torrent-Api-py compatible multi-indexer microservice (:8009)",
    version="1.0.0",
)

sidecar_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@sidecar_app.get("/health")
def sidecar_health() -> dict[str, Any]:
    """Return sidecar operational status and supported sites count."""
    return {
        "status": "ok",
        "service": "torrent-api-py-sidecar",
        "supported_sites": sorted(TORRENT_API_PY_SITE_CATALOG.keys()),
        "total_sites": len(TORRENT_API_PY_SITE_CATALOG),
    }


@sidecar_app.get("/api/v1/sites")
def list_supported_sites() -> dict[str, Any]:
    """Return all 12 supported torrent indexer sites and their metadata."""
    return {
        "supported_sites": TORRENT_API_PY_SITE_CATALOG,
        "count": len(TORRENT_API_PY_SITE_CATALOG),
    }


@sidecar_app.get("/api/v1/recent")
async def get_recent_torrents(
    site: str = Query(..., description="Site key (tgx, nyaasi, bitsearch, glodls, etc.)"),
    limit: int = Query(35, ge=1, le=100),
    page: int = Query(1, ge=1, le=20),
) -> dict[str, Any]:
    """Fetch recent torrents for a specific site in Torrent-Api-py JSON format."""
    site_key = site.strip().lower()
    if site_key not in TORRENT_API_PY_SITE_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Site '{site_key}' not supported.",
        )
    items = await TorrentApiPySourceAdapter._fetch_native_direct_items(
        site_key,
        query=None,
        limit=limit,
        page=page,
        timeout=8.0,
    )
    return {
        "site": site_key,
        "page": page,
        "limit": limit,
        "total": len(items),
        "data": items,
    }


@sidecar_app.get("/api/v1/search")
async def search_site_torrents(
    site: str = Query(..., description="Site key (tgx, nyaasi, bitsearch, glodls, etc.)"),
    query: str = Query(..., min_length=1, description="Search query or IMDb ID"),
    limit: int = Query(35, ge=1, le=100),
    page: int = Query(1, ge=1, le=20),
) -> dict[str, Any]:
    """Search torrents on a specific site in Torrent-Api-py JSON format."""
    site_key = site.strip().lower()
    if site_key not in TORRENT_API_PY_SITE_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Site '{site_key}' not supported.",
        )
    items = await TorrentApiPySourceAdapter._fetch_native_direct_items(
        site_key,
        query=query.strip(),
        limit=limit,
        page=page,
        timeout=8.0,
    )
    return {
        "site": site_key,
        "query": query.strip(),
        "page": page,
        "limit": limit,
        "total": len(items),
        "data": items,
    }


@sidecar_app.get("/api/v1/all/search")
async def search_all_sites(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    """Federated search across the resilient quartet (tgx, nyaasi, bitsearch, glodls)."""
    default_sites = ("tgx", "nyaasi", "bitsearch", "glodls")

    async def _fetch(s: str) -> list[dict[str, Any]]:
        try:
            rows = await TorrentApiPySourceAdapter._fetch_native_direct_items(
                s, query=query.strip(), limit=limit, timeout=6.0
            )
            for r in rows:
                r["site"] = s
            return rows
        except Exception:
            return []

    batches = await asyncio.gather(*(_fetch(s) for s in default_sites))
    combined = [item for batch in batches for item in batch]
    return {
        "query": query.strip(),
        "sites": list(default_sites),
        "total": len(combined),
        "data": combined,
    }


class EmbeddedSidecarManager:
    """Lifecycle-managed asyncio Uvicorn server for the :8009 Torrent-Api-py sidecar."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8009) -> None:
        self.host = host
        self.port = port
        self._server: Optional[uvicorn.Server] = None
        self._task: Optional[asyncio.Task[None]] = None

    @staticmethod
    def _is_port_in_use(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as bind_sock:
            bind_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                bind_sock.bind((host, port))
                return False
            except OSError:
                return True

    async def _serve_safely(self) -> None:
        """Run Uvicorn sidecar without propagating SystemExit(3) to the main app loop."""
        if self._server is None:
            return
        try:
            await self._server.serve()
        except SystemExit as exc:
            logger.warning(
                "Embedded sidecar %s:%d exited cleanly with code %s (main app unaffected).",
                self.host,
                self.port,
                exc.code,
            )
        except OSError as exc:
            logger.warning(
                "Embedded sidecar %s:%d could not bind (%s); direct fallback remains active.",
                self.host,
                self.port,
                exc,
            )

    async def start(self) -> bool:
        """Start the embedded :8009 sidecar if enabled and port 8009 is free."""
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("SIDECAR_AUTOSTART") == "false":
            return False
        if self._task and not self._task.done():
            return True
        if self._is_port_in_use(self.host, self.port):
            logger.info(
                "Sidecar port %s:%d already in use; reusing existing listener or direct fallback.",
                self.host,
                self.port,
            )
            return True

        config = uvicorn.Config(
            app=sidecar_app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._serve_safely())
        # Wait up to 1.5s for socket readiness
        for _ in range(15):
            if self._task.done():
                return False
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.15)
                if sock.connect_ex((self.host, self.port)) == 0:
                    logger.info(
                        "Embedded Torrent-Api-py Sidecar started on http://%s:%d",
                        self.host,
                        self.port,
                    )
                    return True
            await asyncio.sleep(0.1)
        return False

    async def stop(self, timeout: float = 3.0) -> None:
        """Cooperatively stop the embedded :8009 sidecar with zero orphaned processes."""
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._server = None
        self._task = None


sidecar_manager = EmbeddedSidecarManager(
    host=os.environ.get("SIDECAR_HOST", "127.0.0.1"),
    port=int(os.environ.get("SIDECAR_PORT", "8009")),
)
