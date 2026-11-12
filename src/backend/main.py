"""Main application entrypoint for TV Pirata backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.backend.api import (
    collections_router,
    discovery_router,
    library_router,
    torrents_router,
    watches_router,
)
from src.backend.core.database import init_db

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing database initialization and teardown."""
    init_db()
    yield


app = FastAPI(
    title="TV Pirata 🏴‍☠️",
    description="Central de Descoberta, Controle e Administração de Séries para Rede Doméstica",
    version="0.2.0",
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

# Mount static files directory if present
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Register API routers under /api namespace
app.include_router(discovery_router, prefix="/api")
app.include_router(library_router, prefix="/api")
app.include_router(watches_router, prefix="/api")
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
def root():
    """Root status endpoint."""
    return {
        "app": "TV Pirata 🏴‍☠️",
        "tagline": "Seu Netflix pessoal para descoberta e controle",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/api/health")
def healthcheck():
    """Healthcheck endpoint for orchestrators and monitoring."""
    return {"status": "ok", "service": "tv-pirata-backend"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.backend.main:app", host=host, port=port, reload=True)
