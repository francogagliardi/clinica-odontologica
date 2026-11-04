"""FastAPI entrypoint: lifespan owns pool + Redis client lifecycle (R-02)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    bloqueos,
    health,
    obras_sociales,
    pacientes,
    prestaciones,
    profesionales,
    publico,
    ready,
    sillones,
    turnos,
)
from app.core import resources
from app.core.settings import load_settings

settings = load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared resources on startup, close them on shutdown."""
    resources.init_resources(settings)
    yield
    await resources.close_resources()


app = FastAPI(title="Clinica Odontologica API", version="0.1.0", lifespan=lifespan)

# SPA (:8080) and API (:8000) are different origins, so the browser needs an
# explicit allow-list (no wildcard). Credentials stay off: the backoffice
# token travels in the Authorization header, never in cookies (R-03).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(ready.router)
app.include_router(auth.router)
app.include_router(profesionales.router)
app.include_router(sillones.router)
app.include_router(prestaciones.router)
app.include_router(bloqueos.router)
app.include_router(pacientes.router)
app.include_router(obras_sociales.router)
app.include_router(turnos.router)
app.include_router(publico.router)
