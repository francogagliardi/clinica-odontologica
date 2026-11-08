"""Insurance settlement endpoints (C-14, design D9/D11/D13).

Creation/closing/deletion are administrator-only; reception may edit the
observations of a draft; the four read roles share the listing and detail.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    client_ip,
    dispositivo,
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.application.liquidaciones import (
    actualizar_observaciones,
    cerrar,
    crear,
    eliminar,
    listar,
    obtener,
)
from app.infrastructure.uow import UnitOfWork
from app.models.liquidaciones import ItemLiquidacion, LiquidacionObraSocial
from app.models.security import Usuario
from app.schemas.liquidaciones import (
    EstadoLiquidacion,
    ItemLiquidacionResponse,
    LiquidacionCreate,
    LiquidacionObservacionesUpdate,
    LiquidacionResponse,
    LiquidacionResumenResponse,
)

router = APIRouter(
    prefix="/obras-sociales/liquidaciones", tags=["liquidaciones"]
)

_lectura = require_role(
    "administrador", "recepcionista", "odontologo", "auditor"
)
_observaciones = require_role("administrador", "recepcionista")
_alta_baja = require_role("administrador")


def _to_item(item: ItemLiquidacion) -> ItemLiquidacionResponse:
    return ItemLiquidacionResponse(
        id=item.id,
        item_presupuesto_id=item.item_presupuesto_id,
        presupuesto_id=item.presupuesto_id,
        cobro_id=item.cobro_id,
        prestacion_id=item.prestacion_id,
        prestacion_codigo=item.prestacion_codigo,
        pieza=item.pieza,
        cantidad=item.cantidad,
        cobertura_item=item.cobertura_item,
    )


def _to_resumen(
    liquidacion: LiquidacionObraSocial,
) -> LiquidacionResumenResponse:
    return LiquidacionResumenResponse(
        id=liquidacion.id,
        consultorio_id=liquidacion.consultorio_id,
        obra_social_id=liquidacion.obra_social_id,
        creado_por=liquidacion.creado_por,
        desde=liquidacion.desde,
        hasta=liquidacion.hasta,
        estado=liquidacion.estado,  # type: ignore[arg-type]
        total_cobertura=liquidacion.total_cobertura,
        cantidad_practicas=liquidacion.cantidad_practicas,
        observaciones=liquidacion.observaciones,
        cerrada_por=liquidacion.cerrada_por,
        cerrada_at=liquidacion.cerrada_at,
        created_at=liquidacion.created_at,
        updated_at=liquidacion.updated_at,
    )


def _to_response(
    liquidacion: LiquidacionObraSocial,
    items: list[ItemLiquidacion],
) -> LiquidacionResponse:
    resumen = _to_resumen(liquidacion)
    return LiquidacionResponse(
        **resumen.model_dump(),
        items=[_to_item(item) for item in items],
    )


@router.post(
    "",
    response_model=LiquidacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una liquidación en borrador para una obra social",
    dependencies=[Depends(reject_unexpected_query)],
)
async def create_liquidacion(
    payload: LiquidacionCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_alta_baja)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> LiquidacionResponse:
    liquidacion, items = await crear(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        obra_social_id=payload.obra_social_id,
        desde=payload.desde,
        hasta=payload.hasta,
        observaciones=payload.observaciones,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(liquidacion, items)


@router.get(
    "",
    response_model=list[LiquidacionResumenResponse],
    summary="Listar liquidaciones por obra social, estado y período",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "obra_social_id", "estado", "desde", "hasta"
            )
        )
    ],
)
async def list_liquidaciones(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    obra_social_id: uuid.UUID | None = None,
    estado: EstadoLiquidacion | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> list[LiquidacionResumenResponse]:
    liquidaciones = await listar(
        uow,
        consultorio_id=consultorio_id,
        obra_social_id=obra_social_id,
        estado=estado,
        desde=desde,
        hasta=hasta,
    )
    return [_to_resumen(liquidacion) for liquidacion in liquidaciones]


@router.get(
    "/{liquidacion_id}",
    response_model=LiquidacionResponse,
    summary="Ficha de una liquidación con ítems y totales",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_liquidacion(
    liquidacion_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> LiquidacionResponse:
    liquidacion, items = await obtener(
        uow,
        consultorio_id=consultorio_id,
        liquidacion_id=liquidacion_id,
    )
    return _to_response(liquidacion, items)


@router.put(
    "/{liquidacion_id}",
    response_model=LiquidacionResponse,
    summary="Actualizar observaciones de un borrador",
    dependencies=[Depends(reject_unexpected_query)],
)
async def update_liquidacion(
    liquidacion_id: uuid.UUID,
    payload: LiquidacionObservacionesUpdate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_observaciones)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> LiquidacionResponse:
    liquidacion = await actualizar_observaciones(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        liquidacion_id=liquidacion_id,
        observaciones=payload.observaciones,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    _header, items = await obtener(
        uow,
        consultorio_id=consultorio_id,
        liquidacion_id=liquidacion.id,
    )
    return _to_response(liquidacion, items)


@router.post(
    "/{liquidacion_id}/cerrar",
    response_model=LiquidacionResponse,
    summary="Cerrar una liquidación en borrador (solo administrador)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def close_liquidacion(
    liquidacion_id: uuid.UUID,
    request: Request,
    current_user: Annotated[Usuario, Depends(_alta_baja)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> LiquidacionResponse:
    liquidacion, items = await cerrar(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        liquidacion_id=liquidacion_id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(liquidacion, items)


@router.delete(
    "/{liquidacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar lógicamente un borrador (solo administrador)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def delete_liquidacion(
    liquidacion_id: uuid.UUID,
    request: Request,
    current_user: Annotated[Usuario, Depends(_alta_baja)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    await eliminar(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        liquidacion_id=liquidacion_id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
