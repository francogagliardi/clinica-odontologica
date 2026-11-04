"""Budget endpoints (C-12, design D9/D10/D11).

Read operations apply the RBAC matrix row by row; writes are limited to the
administrator and the owning dentist. All amounts are computed server-side and
every write is audited in the same transaction.
"""

import uuid
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
from app.application.clinica import ROLES_LECTURA
from app.application.presupuestos import (
    CoberturaProvider,
    actualizar_presupuesto,
    cambiar_estado_presupuesto,
    crear_presupuesto,
    eliminar_presupuesto,
    get_cobertura_provider,
    listar_presupuestos,
    obtener_presupuesto,
    recalcular_presupuesto,
)
from app.infrastructure.uow import UnitOfWork
from app.models.comercial import ItemPresupuesto, Presupuesto
from app.models.security import Usuario
from app.schemas.presupuestos import (
    EstadoRequest,
    ItemPresupuestoResponse,
    PresupuestoCreate,
    PresupuestoResponse,
    PresupuestoResumenResponse,
    PresupuestoUpdate,
    RecalculoRequest,
)

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])

_lectura = require_role(*ROLES_LECTURA)
_escritura = require_role("administrador", "odontologo")


def _to_resumen(presupuesto: Presupuesto) -> PresupuestoResumenResponse:
    return PresupuestoResumenResponse(
        id=presupuesto.id,
        consultorio_id=presupuesto.consultorio_id,
        paciente_id=presupuesto.paciente_id,
        profesional_id=presupuesto.profesional_id,
        creado_por=presupuesto.creado_por,
        estado=presupuesto.estado,
        cobertura_estado=presupuesto.cobertura_estado,
        subtotal=presupuesto.subtotal,
        cobertura_calculada=presupuesto.cobertura_calculada,
        copago=presupuesto.copago,
        created_at=presupuesto.created_at,
        updated_at=presupuesto.updated_at,
    )


def _to_response(
    presupuesto: Presupuesto, items: list[ItemPresupuesto]
) -> PresupuestoResponse:
    resumen = _to_resumen(presupuesto)
    return PresupuestoResponse(
        **resumen.model_dump(),
        items=[
            ItemPresupuestoResponse(
                id=item.id,
                prestacion_id=item.prestacion_id,
                pieza=item.pieza,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
                cobertura_item=item.cobertura_item,
                copago_item=item.copago_item,
            )
            for item in items
        ],
    )


@router.post(
    "",
    response_model=PresupuestoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un presupuesto en borrador con ítems calculados",
    dependencies=[Depends(reject_unexpected_query)],
)
async def create_presupuesto(
    payload: PresupuestoCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    provider: Annotated[CoberturaProvider, Depends(get_cobertura_provider)],
) -> PresupuestoResponse:
    presupuesto, items = await crear_presupuesto(
        uow,
        provider,
        consultorio_id=consultorio_id,
        usuario=current_user,
        paciente_id=payload.paciente_id,
        profesional_id=payload.profesional_id,
        items=[
            (item.prestacion_id, item.pieza, item.cantidad)
            for item in payload.items
        ],
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(presupuesto, items)


@router.get(
    "",
    response_model=list[PresupuestoResumenResponse],
    summary="Listar presupuestos (descendente, filtrable)",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "paciente_id", "profesional_id", "estado"
            )
        )
    ],
)
async def list_presupuestos(
    _current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    paciente_id: uuid.UUID | None = None,
    profesional_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[PresupuestoResumenResponse]:
    presupuestos = await listar_presupuestos(
        uow,
        consultorio_id=consultorio_id,
        usuario=_current_user,
        paciente_id=paciente_id,
        profesional_id=profesional_id,
        estado=estado,
    )
    return [_to_resumen(presupuesto) for presupuesto in presupuestos]


@router.get(
    "/{presupuesto_id}",
    response_model=PresupuestoResponse,
    summary="Leer un presupuesto con sus ítems y totales",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_presupuesto(
    presupuesto_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> PresupuestoResponse:
    presupuesto, items = await obtener_presupuesto(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        presupuesto_id=presupuesto_id,
    )
    return _to_response(presupuesto, items)


@router.put(
    "/{presupuesto_id}",
    response_model=PresupuestoResponse,
    summary="Reemplazar los ítems de un borrador y recalcular",
    dependencies=[Depends(reject_unexpected_query)],
)
async def update_presupuesto(
    presupuesto_id: uuid.UUID,
    payload: PresupuestoUpdate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    provider: Annotated[CoberturaProvider, Depends(get_cobertura_provider)],
) -> PresupuestoResponse:
    presupuesto, items = await actualizar_presupuesto(
        uow,
        provider,
        consultorio_id=consultorio_id,
        usuario=current_user,
        presupuesto_id=presupuesto_id,
        paciente_id=payload.paciente_id,
        profesional_id=payload.profesional_id,
        items=[
            (item.prestacion_id, item.pieza, item.cantidad)
            for item in payload.items
        ],
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(presupuesto, items)


@router.post(
    "/{presupuesto_id}/recalcular",
    response_model=PresupuestoResponse,
    summary="Recalcular la cobertura de un borrador sin tocar precios",
    dependencies=[Depends(reject_unexpected_query)],
)
async def recalculate_presupuesto(
    presupuesto_id: uuid.UUID,
    payload: RecalculoRequest,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    provider: Annotated[CoberturaProvider, Depends(get_cobertura_provider)],
) -> PresupuestoResponse:
    presupuesto, items = await recalcular_presupuesto(
        uow,
        provider,
        consultorio_id=consultorio_id,
        usuario=current_user,
        presupuesto_id=presupuesto_id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(presupuesto, items)


@router.patch(
    "/{presupuesto_id}/estado",
    response_model=PresupuestoResponse,
    summary="Cambiar el estado de un presupuesto (idempotente)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def change_presupuesto_estado(
    presupuesto_id: uuid.UUID,
    payload: EstadoRequest,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> PresupuestoResponse:
    presupuesto, items = await cambiar_estado_presupuesto(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        presupuesto_id=presupuesto_id,
        nuevo_estado=payload.estado,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(presupuesto, items)


@router.delete(
    "/{presupuesto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dar de baja lógica un borrador",
    dependencies=[Depends(reject_unexpected_query)],
)
async def delete_presupuesto(
    presupuesto_id: uuid.UUID,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    await eliminar_presupuesto(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        presupuesto_id=presupuesto_id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
