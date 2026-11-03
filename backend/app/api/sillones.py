"""Chair resources (C-04): admin-only writes, agenda-wide reads."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query,
    require_role,
)
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Sillon
from app.models.security import Usuario
from app.schemas.recursos import SillonCreate, SillonResponse, SillonUpdate

router = APIRouter(prefix="/sillones", tags=["sillones"])

AGENDA_ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
_lectura = require_role(*AGENDA_ROLES)
_escritura = require_role("administrador")


def _to_response(sillon: Sillon) -> SillonResponse:
    return SillonResponse(
        id=sillon.id,
        consultorio_id=sillon.consultorio_id,
        nombre=sillon.nombre,
        is_active=sillon.is_active,
    )


async def _activo(uow: UnitOfWork, sillon_id: uuid.UUID) -> Sillon:
    sillon = await uow.sillones.get(sillon_id)
    if sillon is None or not sillon.is_active or sillon.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sillón no encontrado",
        )
    return sillon


@router.get(
    "",
    response_model=list[SillonResponse],
    summary="Listar sillones activos",
    dependencies=[Depends(reject_unexpected_query)],
)
async def list_sillones(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[SillonResponse]:
    sillones = await uow.sillones.list()
    return [_to_response(sillon) for sillon in sillones]


@router.post(
    "",
    response_model=SillonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear sillón (solo administrador)",
)
async def create_sillon(
    payload: SillonCreate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> SillonResponse:
    if (
        await uow.sillones.get_by_nombre(consultorio_id, payload.nombre)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El sillón ya existe en este consultorio",
        )
    sillon = Sillon(consultorio_id=consultorio_id, nombre=payload.nombre)
    await uow.sillones.add(sillon)
    return _to_response(sillon)


@router.get(
    "/{sillon_id}",
    response_model=SillonResponse,
    summary="Obtener un sillón activo",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_sillon(
    sillon_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> SillonResponse:
    return _to_response(await _activo(uow, sillon_id))


@router.put(
    "/{sillon_id}",
    response_model=SillonResponse,
    summary="Actualizar sillón (solo administrador)",
)
async def update_sillon(
    sillon_id: uuid.UUID,
    payload: SillonUpdate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> SillonResponse:
    sillon = await _activo(uow, sillon_id)
    if (
        await uow.sillones.get_by_nombre(
            sillon.consultorio_id, payload.nombre, exclude_id=sillon.id
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El sillón ya existe en este consultorio",
        )
    sillon.nombre = payload.nombre
    await uow.session.flush()
    return _to_response(sillon)


@router.delete(
    "/{sillon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de sillón (solo administrador)",
)
async def delete_sillon(
    sillon_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> Response:
    sillon = await _activo(uow, sillon_id)
    await uow.sillones.soft_delete(sillon)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
