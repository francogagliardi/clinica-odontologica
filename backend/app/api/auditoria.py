"""Read-only audit viewer (C-16, design D5/D12).

`GET /auditoria` is the only method: there is no write surface and a read never
appends a row. Administrators and auditors read the same history; the other
roles receive 403 and a missing Bearer 401.

Dates arrive as local UTC-3 dates and are converted to inclusive UTC bounds
before delegating to `AuditoriaRepository.list_filtrado`, which orders by
`timestamp DESC, id DESC` and counts the total before paginating.
"""

import uuid
from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.deps import (
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.uow import UnitOfWork
from app.models.security import Usuario
from app.schemas.auditoria import (
    AuditoriaFila,
    AuditoriaQuery,
    AuditoriaResponse,
)

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

_ROLES_LECTURA = require_role("administrador", "auditor")


def _validar(query: type[AuditoriaQuery], **datos: object) -> AuditoriaQuery:
    try:
        return query(**datos)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.errors()[0]["msg"],
        ) from error


def _desde_utc(fecha: date | None) -> datetime | None:
    if fecha is None:
        return None
    return datetime.combine(fecha, time.min, tzinfo=ARGENTINA_OFFSET)


def _hasta_utc(fecha: date | None) -> datetime | None:
    if fecha is None:
        return None
    return datetime.combine(fecha, time.max, tzinfo=ARGENTINA_OFFSET)


@router.get(
    "",
    response_model=AuditoriaResponse,
    summary="Consulta paginada del registro de auditoría (solo lectura)",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "usuario_id",
                "entidad",
                "accion",
                "desde",
                "hasta",
                "limite",
                "offset",
            )
        )
    ],
)
async def list_auditoria(
    _current: Annotated[Usuario, Depends(_ROLES_LECTURA)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    usuario_id: uuid.UUID | None = None,
    entidad: str | None = None,
    accion: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = 100,
    offset: int = 0,
) -> AuditoriaResponse:
    filtros = _validar(
        AuditoriaQuery,
        usuario_id=usuario_id,
        entidad=entidad,
        accion=accion,
        desde=desde,
        hasta=hasta,
        limite=limite,
        offset=offset,
    )
    filas, total = await uow.auditoria.list_filtrado(
        usuario_id=filtros.usuario_id,
        entidad=filtros.entidad,
        accion=filtros.accion,
        desde=_desde_utc(filtros.desde),
        hasta=_hasta_utc(filtros.hasta),
        limite=filtros.limite,
        offset=filtros.offset,
    )
    emails = await uow.usuarios.emails_por_ids(
        [fila.usuario_id for fila in filas if fila.usuario_id is not None]
    )
    return AuditoriaResponse(
        total=total,
        limite=filtros.limite,
        offset=filtros.offset,
        filas=[
            AuditoriaFila(
                id=fila.id,
                usuario_id=fila.usuario_id,
                usuario_email=emails.get(fila.usuario_id)
                if fila.usuario_id is not None
                else None,
                accion=fila.accion,
                entidad=fila.entidad,
                entidad_id=fila.entidad_id,
                ip=fila.ip,
                dispositivo=fila.dispositivo,
                timestamp=fila.timestamp,
            )
            for fila in filas
        ],
    )
