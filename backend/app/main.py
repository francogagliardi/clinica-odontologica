"""FastAPI entrypoint: lifespan owns pool + Redis client lifecycle (R-02)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, ready
from app.core import resources
from app.core.settings import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared resources on startup, close them on shutdown."""
    settings = load_settings()
    resources.init_resources(settings)
    yield
    await resources.close_resources()


app = FastAPI(title="Clinica Odontologica API", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(ready.router)
