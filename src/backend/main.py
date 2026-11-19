"""Main application entrypoint for TV Pirata backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from src.backend.api import (
    catalog_router,
    collections_router,
    discovery_router,
    explore_router,
    library_router,
    notifications_router,
    sources_router,
    torrents_router,
    watches_router,
)
from src.backend.core.database import engine, init_db, init_eztv_db
from src.backend.services.federated_catalog import FederatedCatalogService
from src.backend.services.scheduler import scheduler
from src.backend.sidecar import sidecar_manager

STATIC_DIR = Path(__file__).parent / "static"
DIST_DIR = STATIC_DIR / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing DB initialization, sidecar :8009, auto-sync and teardown."""
    init_db()
    init_eztv_db()
    with Session(engine) as session:
        FederatedCatalogService().ensure_federated_catalog_seeded(session)
    await sidecar_manager.start()
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop(timeout=3.0)
        await sidecar_manager.stop(timeout=3.0)


app = FastAPI(
    title="TV Pirata 🏴‍☠️",
    description="Audiovisual Discovery Platform & Personal Media Ecosystem",
    version="0.7.0",
    lifespan=lifespan,
)

# CORS configuration allowing cross-origin requests from frontends
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and compiled frontend assets if present
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

# Register API routers under /api namespace
app.include_router(explore_router, prefix="/api")
app.include_router(discovery_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(library_router, prefix="/api")
app.include_router(watches_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(torrents_router, prefix="/api")
app.include_router(collections_router, prefix="/api")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Serve binary favicon for browsers."""
    ico_path = STATIC_DIR / "favicon.ico"
    if ico_path.exists():
        return FileResponse(ico_path, media_type="image/x-icon")
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg():
    """Serve scalable vector favicon."""
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/")
def root(request: Request):
    """Serve SPA web application in browsers or JSON status for API clients."""
    accept = request.headers.get("accept", "")
    dist_index = DIST_DIR / "index.html"
    if "text/html" in accept and dist_index.exists():
        return FileResponse(dist_index)
    return {
        "app": "TV Pirata 🏴‍☠️",
        "tagline": "Audiovisual Discovery Platform & Personal Media Ecosystem",
        "version": "0.6.0",
        "docs": "/docs",
    }


@app.get("/app", include_in_schema=False)
@app.get("/web", include_in_schema=False)
def app_view():
    """Explicit endpoint for SPA web application."""
    dist_index = DIST_DIR / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    return {"detail": "Frontend assets not compiled yet. Run: make build-front"}


@app.get("/api/health")
def healthcheck():
    """Healthcheck endpoint for orchestrators and monitoring."""
    return {"status": "ok", "service": "tv-pirata-backend"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.backend.main:app", host=host, port=port, reload=True)
