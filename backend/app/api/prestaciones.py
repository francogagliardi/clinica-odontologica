"""Service catalogue and optional deposit (C-04, RN-TU-02, RN-TU-08, DD-10)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_uow,
    reject_unexpected_query,
    require_role,
)
from app.infrastructure.uow import UnitOfWork
from app.models.comercial import Prestacion
from app.models.security import Usuario
from app.schemas.recursos import (
    PrestacionCreate,
    PrestacionResponse,
    PrestacionUpdate,
)

router = APIRouter(prefix="/prestaciones", tags=["prestaciones"])

AGENDA_ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
_lectura = require_role(*AGENDA_ROLES)
_escritura = require_role("administrador")


def _to_response(prestacion: Prestacion) -> PrestacionResponse:
    return PrestacionResponse(
        id=prestacion.id,
        codigo=prestacion.codigo,
        nombre=prestacion.nombre,
        duracion_min=prestacion.duracion_min,
        precio_base=prestacion.precio_base,
        especialidad=prestacion.especialidad,
        requiere_sena=prestacion.requiere_sena,
        monto_sena=prestacion.monto_sena,
        is_active=prestacion.is_active,
    )


async def _activa(uow: UnitOfWork, prestacion_id: uuid.UUID) -> Prestacion:
    prestacion = await uow.prestaciones.get(prestacion_id)
    if (
        prestacion is None
        or not prestacion.is_active
        or prestacion.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestación no encontrada",
        )
    return prestacion


async def _validar_codigo(
    uow: UnitOfWork, codigo: str, exclude_id: uuid.UUID | None = None
) -> None:
    if (
        await uow.prestaciones.get_by_codigo(codigo, exclude_id)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El código de prestación ya existe",
        )


@router.get(
    "",
    response_model=list[PrestacionResponse],
    summary="Listar prestaciones activas",
    dependencies=[Depends(reject_unexpected_query)],
)
async def list_prestaciones(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[PrestacionResponse]:
    prestaciones = await uow.prestaciones.list()
    return [_to_response(prestacion) for prestacion in prestaciones]


@router.post(
    "",
    response_model=PrestacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear prestación (solo administrador)",
)
async def create_prestacion(
    payload: PrestacionCreate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> PrestacionResponse:
    await _validar_codigo(uow, payload.codigo)
    prestacion = Prestacion(**payload.model_dump())
    await uow.prestaciones.add(prestacion)
    return _to_response(prestacion)


@router.get(
    "/{prestacion_id}",
    response_model=PrestacionResponse,
    summary="Obtener una prestación activa",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_prestacion(
    prestacion_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> PrestacionResponse:
    return _to_response(await _activa(uow, prestacion_id))


@router.put(
    "/{prestacion_id}",
    response_model=PrestacionResponse,
    summary="Actualizar prestación (solo administrador)",
)
async def update_prestacion(
    prestacion_id: uuid.UUID,
    payload: PrestacionUpdate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> PrestacionResponse:
    prestacion = await _activa(uow, prestacion_id)
    await _validar_codigo(uow, payload.codigo, exclude_id=prestacion.id)
    for campo, valor in payload.model_dump().items():
        setattr(prestacion, campo, valor)
    await uow.session.flush()
    return _to_response(prestacion)


@router.delete(
    "/{prestacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de prestación (solo administrador)",
)
async def delete_prestacion(
    prestacion_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> Response:
    prestacion = await _activa(uow, prestacion_id)
    await uow.prestaciones.soft_delete(prestacion)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
