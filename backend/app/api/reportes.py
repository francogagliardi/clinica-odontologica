"""Read-only report endpoints (C-15, design D8/D9/D13).

Four GET routes under `/reportes`. Each declares its exact filter list, so an
undeclared query parameter is a 422 instead of being silently ignored. Range
and limit live in the Pydantic query schemas (`extra='forbid'`).

RBAC: admin and auditor read everything; reception reads agenda, absence and
cash; the dentist reads their own agenda/absence/cash and settlements in read
mode; the assistant has no access.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.api.deps import (
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.application.reportes import (
    reporte_agenda,
    reporte_ausentismo,
    reporte_caja,
    reporte_liquidaciones,
)
from app.infrastructure.uow import UnitOfWork
from app.models.security import Usuario
from app.schemas.reportes import (
    ReporteAgendaQuery,
    ReporteAgendaResponse,
    ReporteAusentismoQuery,
    ReporteAusentismoResponse,
    ReporteCajaQuery,
    ReporteCajaResponse,
    ReporteLiquidacionesQuery,
    ReporteLiquidacionesResponse,
)

router = APIRouter(prefix="/reportes", tags=["reportes"])

_ROLES_AGENDA = require_role(
    "administrador", "odontologo", "recepcionista", "auditor"
)
_ROLES_LIQUIDACIONES = require_role(
    "administrador", "odontologo", "auditor"
)


def _validar(query, **datos):
    try:
        return query(**datos)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.errors()[0]["msg"],
        ) from error


@router.get(
    "/agenda",
    response_model=ReporteAgendaResponse,
    summary="Agenda, ocupación, cancelaciones y detalle acotado",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "desde",
                "hasta",
                "profesional_id",
                "sillon_id",
                "estado",
                "limite",
            )
        )
    ],
)
async def get_agenda(
    _current: Annotated[Usuario, Depends(_ROLES_AGENDA)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    desde: date,
    hasta: date,
    profesional_id: uuid.UUID | None = None,
    sillon_id: uuid.UUID | None = None,
    estado: str | None = None,
    limite: int = 500,
) -> ReporteAgendaResponse:
    filtros = _validar(
        ReporteAgendaQuery,
        desde=desde,
        hasta=hasta,
        profesional_id=profesional_id,
        sillon_id=sillon_id,
        estado=estado,
        limite=limite,
    )
    return await reporte_agenda(
        uow,
        consultorio_id=consultorio_id,
        usuario=_current,
        desde=filtros.desde,
        hasta=filtros.hasta,
        profesional_id=filtros.profesional_id,
        sillon_id=filtros.sillon_id,
        estado=filtros.estado,
        limite=filtros.limite,
    )


@router.get(
    "/ausentismo",
    response_model=ReporteAusentismoResponse,
    summary="Tasas de ausentismo sobre turnos cerrados y detalle",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "desde", "hasta", "profesional_id", "limite"
            )
        )
    ],
)
async def get_ausentismo(
    _current: Annotated[Usuario, Depends(_ROLES_AGENDA)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    desde: date,
    hasta: date,
    profesional_id: uuid.UUID | None = None,
    limite: int = 500,
) -> ReporteAusentismoResponse:
    filtros = _validar(
        ReporteAusentismoQuery,
        desde=desde,
        hasta=hasta,
        profesional_id=profesional_id,
        limite=limite,
    )
    return await reporte_ausentismo(
        uow,
        consultorio_id=consultorio_id,
        usuario=_current,
        desde=filtros.desde,
        hasta=filtros.hasta,
        profesional_id=filtros.profesional_id,
        limite=filtros.limite,
    )


@router.get(
    "/caja",
    response_model=ReporteCajaResponse,
    summary="Cobros por medio/estado, movimientos y arqueos del rango",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "desde", "hasta", "medio", "estado", "limite"
            )
        )
    ],
)
async def get_caja(
    _current: Annotated[Usuario, Depends(_ROLES_AGENDA)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    desde: date,
    hasta: date,
    medio: str | None = None,
    estado: str | None = None,
    limite: int = 500,
) -> ReporteCajaResponse:
    filtros = _validar(
        ReporteCajaQuery,
        desde=desde,
        hasta=hasta,
        medio=medio,
        estado=estado,
        limite=limite,
    )
    return await reporte_caja(
        uow,
        consultorio_id=consultorio_id,
        usuario=_current,
        desde=filtros.desde,
        hasta=filtros.hasta,
        medio=filtros.medio,
        estado=filtros.estado,
        limite=filtros.limite,
    )


@router.get(
    "/liquidaciones",
    response_model=ReporteLiquidacionesResponse,
    summary="Liquidaciones por obra social, estado y prestación",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "desde", "hasta", "obra_social_id", "estado", "limite"
            )
        )
    ],
)
async def get_liquidaciones(
    _current: Annotated[Usuario, Depends(_ROLES_LIQUIDACIONES)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    desde: date,
    hasta: date,
    obra_social_id: uuid.UUID | None = None,
    estado: str | None = None,
    limite: int = 500,
) -> ReporteLiquidacionesResponse:
    filtros = _validar(
        ReporteLiquidacionesQuery,
        desde=desde,
        hasta=hasta,
        obra_social_id=obra_social_id,
        estado=estado,
        limite=limite,
    )
    return await reporte_liquidaciones(
        uow,
        consultorio_id=consultorio_id,
        desde=filtros.desde,
        hasta=filtros.hasta,
        obra_social_id=filtros.obra_social_id,
        estado=filtros.estado,
        limite=filtros.limite,
    )
