"""Patient registry: alta, ficha, búsqueda, edición y baja lógica (C-05)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError

from app.api.deps import (
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.infrastructure.uow import UnitOfWork
from app.models.pacientes import Paciente
from app.models.security import Usuario
from app.schemas.pacientes import (
    BusquedaPaciente,
    PacienteCreate,
    PacienteResponse,
    PacienteUpdate,
)

router = APIRouter(prefix="/pacientes", tags=["pacientes"])

ROLES_LECTURA = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
ROLES_ESCRITURA = ("administrador", "recepcionista")

_lectura = require_role(*ROLES_LECTURA)
_escritura = require_role(*ROLES_ESCRITURA)
_baja = require_role("administrador")


def _to_response(paciente: Paciente) -> PacienteResponse:
    return PacienteResponse(
        id=paciente.id,
        consultorio_id=paciente.consultorio_id,
        nombre=paciente.nombre,
        apellido=paciente.apellido,
        dni=paciente.dni,
        fecha_nacimiento=paciente.fecha_nacimiento,
        telefono=paciente.telefono,
        email=paciente.email,
        obra_social_id=paciente.obra_social_id,
        nro_afiliado=paciente.nro_afiliado,
        notas=paciente.notas,
        is_active=paciente.is_active,
    )


async def _activo(
    uow: UnitOfWork, consultorio_id: uuid.UUID, paciente_id: uuid.UUID
) -> Paciente:
    paciente = await uow.pacientes.get(paciente_id)
    if (
        paciente is None
        or paciente.consultorio_id != consultorio_id
        or not paciente.is_active
        or paciente.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado",
        )
    return paciente


async def _validar_dni(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    dni: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if (
        await uow.pacientes.get_by_dni(consultorio_id, dni, exclude_id)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El DNI ya está registrado en este consultorio",
        )


async def _validar_obra_social(
    uow: UnitOfWork, consultorio_id: uuid.UUID, obra_social_id: uuid.UUID | None
) -> None:
    if obra_social_id is None:
        return
    obra_social = await uow.obras_sociales.get(obra_social_id)
    if (
        obra_social is None
        or obra_social.consultorio_id != consultorio_id
        or not obra_social.is_active
        or obra_social.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Obra social no encontrada",
        )


@router.post(
    "",
    response_model=PacienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de paciente (administrador o recepción)",
)
async def create_paciente(
    payload: PacienteCreate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> PacienteResponse:
    await _validar_dni(uow, consultorio_id, payload.dni)
    await _validar_obra_social(uow, consultorio_id, payload.obra_social_id)
    paciente = Paciente(
        **payload.model_dump(), consultorio_id=consultorio_id
    )
    await uow.pacientes.add(paciente)
    return _to_response(paciente)


@router.get(
    "",
    response_model=list[PacienteResponse],
    summary="Buscar pacientes por DNI, teléfono o apellido",
    dependencies=[
        Depends(reject_unexpected_query_except("dni", "telefono", "apellido"))
    ],
)
async def search_pacientes(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    dni: Annotated[str | None, Query()] = None,
    telefono: Annotated[str | None, Query()] = None,
    apellido: Annotated[str | None, Query()] = None,
) -> list[PacienteResponse]:
    try:
        criterios = BusquedaPaciente(
            dni=dni, telefono=telefono, apellido=apellido
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422, detail=error.errors()[0]["msg"]
        ) from error

    pacientes = await uow.pacientes.search(
        consultorio_id,
        dni=criterios.dni,
        telefono=criterios.telefono,
        apellido=criterios.apellido,
    )
    return [_to_response(paciente) for paciente in pacientes]


@router.get(
    "/{paciente_id}",
    response_model=PacienteResponse,
    summary="Ficha de un paciente activo",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_paciente(
    paciente_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> PacienteResponse:
    return _to_response(
        await _activo(uow, consultorio_id, paciente_id)
    )


@router.put(
    "/{paciente_id}",
    response_model=PacienteResponse,
    summary="Editar paciente (administrador o recepción)",
)
async def update_paciente(
    paciente_id: uuid.UUID,
    payload: PacienteUpdate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> PacienteResponse:
    paciente = await _activo(uow, consultorio_id, paciente_id)
    await _validar_dni(
        uow, consultorio_id, payload.dni, exclude_id=paciente.id
    )
    await _validar_obra_social(uow, consultorio_id, payload.obra_social_id)
    for campo, valor in payload.model_dump().items():
        setattr(paciente, campo, valor)
    await uow.session.flush()
    return _to_response(paciente)


@router.delete(
    "/{paciente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de paciente (solo administrador)",
)
async def delete_paciente(
    paciente_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_baja)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    paciente = await _activo(uow, consultorio_id, paciente_id)
    await uow.pacientes.soft_delete(paciente)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
