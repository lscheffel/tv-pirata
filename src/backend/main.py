"""Main application entrypoint for TV Pirata backend."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api import (
    collections_router,
    discovery_router,
    library_router,
    torrents_router,
    watches_router,
)
from src.backend.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan managing database initialization and teardown."""
    init_db()
    yield


app = FastAPI(
    title="TV Pirata 🏴‍☠️",
    description="Central de Descoberta, Controle e Administração de Séries para Rede Doméstica",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration allowing cross-origin requests from frontends
cors_origins_env = os.getenv("CORS_ORIGINS", '["*"]')
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers under /api namespace
app.include_router(discovery_router, prefix="/api")
app.include_router(library_router, prefix="/api")
app.include_router(watches_router, prefix="/api")
app.include_router(torrents_router, prefix="/api")
app.include_router(collections_router, prefix="/api")


@app.get("/")
def root():
    """Root status endpoint."""
    return {
        "app": "TV Pirata 🏴‍☠️",
        "tagline": "Seu Netflix pessoal para descoberta e controle",
        "version": "0.1.0",
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
