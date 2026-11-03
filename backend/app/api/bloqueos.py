"""Agenda blocks (C-04, RN-TU-07, R-10).

A block affects exactly one resource (professional XOR chair). Administrators
and receptionists may block anything; a dentist may only manage blocks of the
professional linked to their own user (RBAC matrix, "RU (propios)"). Assistants
and auditors may only read.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Bloqueo, Profesional
from app.models.security import Usuario
from app.schemas.recursos import BloqueoCreate, BloqueoResponse

router = APIRouter(prefix="/bloqueos", tags=["bloqueos"])

AGENDA_ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
_lectura = require_role(*AGENDA_ROLES)
_escritura = require_role("administrador", "recepcionista", "odontologo")


def _to_response(bloqueo: Bloqueo) -> BloqueoResponse:
    return BloqueoResponse(
        id=bloqueo.id,
        profesional_id=bloqueo.profesional_id,
        sillon_id=bloqueo.sillon_id,
        desde=bloqueo.desde,
        hasta=bloqueo.hasta,
        motivo=bloqueo.motivo,
        is_active=bloqueo.is_active,
    )


def _roles(usuario: Usuario) -> set[str]:
    return {
        rol.nombre
        for rol in usuario.roles
        if rol.is_active and rol.deleted_at is None
    }


def _es_privilegiado(usuario: Usuario) -> bool:
    return bool({"administrador", "recepcionista"} & _roles(usuario))


async def _validar_recurso(
    uow: UnitOfWork,
    profesional_id: uuid.UUID | None,
    sillon_id: uuid.UUID | None,
) -> Profesional | None:
    """404 when the target resource does not exist or is soft-deleted."""
    if profesional_id is not None:
        profesional = await uow.profesionales.get(profesional_id)
        if (
            profesional is None
            or not profesional.is_active
            or profesional.deleted_at is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profesional no encontrado",
            )
        return profesional
    assert sillon_id is not None
    sillon = await uow.sillones.get(sillon_id)
    if sillon is None or not sillon.is_active or sillon.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sillón no encontrado",
        )
    return None


def _exigir_propiedad(
    usuario: Usuario, profesional: Profesional | None
) -> None:
    """Dentists may only manage blocks of their own professional."""
    if _es_privilegiado(usuario):
        return
    if profesional is None or profesional.usuario_id != usuario.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puede gestionar bloqueos de su propio profesional",
        )


async def _bloqueo_activo(uow: UnitOfWork, bloqueo_id: uuid.UUID) -> Bloqueo:
    bloqueo = await uow.bloqueos.get(bloqueo_id)
    if (
        bloqueo is None
        or not bloqueo.is_active
        or bloqueo.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloqueo no encontrado",
        )
    return bloqueo


@router.get(
    "",
    response_model=list[BloqueoResponse],
    summary="Listar bloqueos activos",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "profesional_id", "sillon_id", "desde", "hasta"
            )
        )
    ],
)
async def list_bloqueos(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    profesional_id: uuid.UUID | None = None,
    sillon_id: uuid.UUID | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> list[BloqueoResponse]:
    bloqueos = await uow.bloqueos.list_vigentes(
        profesional_id=profesional_id,
        sillon_id=sillon_id,
        desde=desde,
        hasta=hasta,
    )
    return [_to_response(bloqueo) for bloqueo in bloqueos]


@router.post(
    "",
    response_model=BloqueoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear bloqueo de profesional o sillón",
)
async def create_bloqueo(
    payload: BloqueoCreate,
    current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> BloqueoResponse:
    profesional = await _validar_recurso(
        uow, payload.profesional_id, payload.sillon_id
    )
    if payload.sillon_id is not None and not _es_privilegiado(current):
        # A dentist's ownership is defined over their professional, never a chair.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administración o recepción puede bloquear sillones",
        )
    _exigir_propiedad(current, profesional)

    bloqueo = Bloqueo(**payload.model_dump())
    await uow.bloqueos.add(bloqueo)
    return _to_response(bloqueo)


@router.delete(
    "/{bloqueo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de bloqueo",
)
async def delete_bloqueo(
    bloqueo_id: uuid.UUID,
    current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> Response:
    bloqueo = await _bloqueo_activo(uow, bloqueo_id)
    profesional = None
    if bloqueo.profesional_id is not None:
        profesional = await uow.profesionales.get(bloqueo.profesional_id)
    _exigir_propiedad(current, profesional)
    await uow.bloqueos.soft_delete(bloqueo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
