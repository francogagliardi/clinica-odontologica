"""FastAPI entrypoint: lifespan owns pool + Redis client lifecycle (R-02)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    auditoria,
    bloqueos,
    caja,
    cobros,
    comprobantes,
    exportaciones,
    health,
    historia_clinica,
    liquidaciones,
    lista_espera,
    obras_sociales,
    odontograma,
    ofertas,
    pacientes,
    prestaciones,
    presupuestos,
    privacidad,
    profesionales,
    publico,
    ready,
    recordatorios,
    reportes,
    sillones,
    turnos,
    usuarios,
    webhooks,
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
app.include_router(usuarios.router)
app.include_router(auditoria.router)
app.include_router(profesionales.router)
app.include_router(sillones.router)
app.include_router(prestaciones.router)
app.include_router(presupuestos.router)
app.include_router(cobros.router)
app.include_router(comprobantes.router)
app.include_router(caja.router)
app.include_router(reportes.router)
app.include_router(exportaciones.router)
app.include_router(bloqueos.router)
app.include_router(pacientes.router)
app.include_router(historia_clinica.router)
app.include_router(odontograma.router)
app.include_router(liquidaciones.router)
app.include_router(obras_sociales.router)
app.include_router(turnos.router)
app.include_router(lista_espera.router)
app.include_router(publico.router)
app.include_router(privacidad.router)
app.include_router(ofertas.router)
app.include_router(recordatorios.router)
app.include_router(webhooks.router)
