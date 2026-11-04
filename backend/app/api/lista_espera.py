"""Waiting-list endpoints: alta, listado, detalle y baja (C-10, D11/D12)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.infrastructure.uow import UnitOfWork
from app.models.lista_espera import EntradaListaEspera
from app.models.security import Usuario
from app.schemas.lista_espera import (
    EntradaListaEsperaCreate,
    EntradaListaEsperaResponse,
    EstadoListaEspera,
)

router = APIRouter(prefix="/lista-espera", tags=["lista-espera"])

AGENDA_ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
_lectura = require_role(*AGENDA_ROLES)
_escritura = require_role("administrador", "recepcionista")
_LECTURA_COMPLETA = {"administrador", "recepcionista", "asistente", "auditor"}


def _to_response(entrada: EntradaListaEspera) -> EntradaListaEsperaResponse:
    return EntradaListaEsperaResponse(
        id=entrada.id,
        consultorio_id=entrada.consultorio_id,
        paciente_id=entrada.paciente_id,
        prestacion_id=entrada.prestacion_id,
        profesional_id=entrada.profesional_id,
        orden=entrada.orden,
        estado=entrada.estado,  # type: ignore[arg-type]
        oferta_profesional_id=entrada.oferta_profesional_id,
        oferta_sillon_id=entrada.oferta_sillon_id,
        oferta_inicio=entrada.oferta_inicio,
        oferta_fin=entrada.oferta_fin,
        oferta_expira_en=entrada.oferta_expira_en,
        turno_id=entrada.turno_id,
        is_active=entrada.is_active,
    )


def _roles(usuario: Usuario) -> set[str]:
    return {
        rol.nombre
        for rol in usuario.roles
        if rol.is_active and rol.deleted_at is None
    }


async def _alcance(
    uow: UnitOfWork, current: Usuario
) -> tuple[bool, uuid.UUID | None]:
    """(restringido, profesional_id): the dentist only sees own entries (D11).

    Entries without a fixed professional are not "his", so a restricted reader
    with no linked professional simply sees nothing.
    """
    roles = _roles(current)
    if roles & _LECTURA_COMPLETA:
        return False, None
    if "odontologo" in roles:
        profesional = await uow.profesionales.get_by_usuario(current.id)
        return True, profesional.id if profesional is not None else None
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes",
    )


async def _propia(
    uow: UnitOfWork,
    current: Usuario,
    consultorio_id: uuid.UUID,
    entrada_id: uuid.UUID,
) -> EntradaListaEspera:
    entrada = await uow.lista_espera.get(entrada_id)
    if (
        entrada is None
        or entrada.consultorio_id != consultorio_id
        or entrada.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrada de lista de espera no encontrada",
        )
    restringido, propio = await _alcance(uow, current)
    if restringido and entrada.profesional_id != propio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrada de lista de espera no encontrada",
        )
    return entrada


def _sqlstate(error: IntegrityError) -> str | None:
    original = getattr(error, "orig", error)
    return getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )


async def _recursos_validos(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    payload: EntradaListaEsperaCreate,
) -> None:
    paciente = await uow.pacientes.get(payload.paciente_id)
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

    prestacion = await uow.prestaciones.get(payload.prestacion_id)
    if (
        prestacion is None
        or not prestacion.is_active
        or prestacion.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestación no encontrada",
        )

    if payload.profesional_id is None:
        return
    profesional = await uow.profesionales.get(payload.profesional_id)
    if (
        profesional is None
        or profesional.consultorio_id != consultorio_id
        or not profesional.is_active
        or profesional.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesional no encontrado",
        )


@router.post(
    "",
    response_model=EntradaListaEsperaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Anotar un paciente en la lista de espera",
)
async def create_entrada(
    payload: EntradaListaEsperaCreate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EntradaListaEsperaResponse:
    await _recursos_validos(uow, consultorio_id, payload)

    existente = await uow.lista_espera.get_pendiente(
        consultorio_id=consultorio_id,
        paciente_id=payload.paciente_id,
        prestacion_id=payload.prestacion_id,
        profesional_id=payload.profesional_id,
    )
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El paciente ya tiene una entrada pendiente para esa "
                "prestación y profesional"
            ),
        )

    entrada = EntradaListaEspera(
        consultorio_id=consultorio_id,
        paciente_id=payload.paciente_id,
        prestacion_id=payload.prestacion_id,
        profesional_id=payload.profesional_id,
        estado="pendiente",
    )
    try:
        await uow.lista_espera.add(entrada)
    except IntegrityError as error:
        if _sqlstate(error) == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "El paciente ya tiene una entrada pendiente para esa "
                    "prestación y profesional"
                ),
            ) from error
        raise
    return _to_response(entrada)


@router.get(
    "",
    response_model=list[EntradaListaEsperaResponse],
    summary="Listar la lista de espera en orden FIFO",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "estado", "prestacion_id", "profesional_id"
            )
        )
    ],
)
async def list_entradas(
    current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    estado: EstadoListaEspera | None = None,
    prestacion_id: uuid.UUID | None = None,
    profesional_id: uuid.UUID | None = None,
) -> list[EntradaListaEsperaResponse]:
    restringido, propio = await _alcance(uow, current)
    if restringido:
        if propio is None:
            return []
        profesional_id = propio
    entradas = await uow.lista_espera.list_by_consultorio(
        consultorio_id,
        estado=estado,
        prestacion_id=prestacion_id,
        profesional_id=profesional_id,
    )
    return [_to_response(entrada) for entrada in entradas]


@router.get(
    "/{entrada_id}",
    response_model=EntradaListaEsperaResponse,
    summary="Detalle de una entrada (oferta y turno incluidos)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_entrada(
    entrada_id: uuid.UUID,
    current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EntradaListaEsperaResponse:
    return _to_response(
        await _propia(uow, current, consultorio_id, entrada_id)
    )


@router.delete(
    "/{entrada_id}",
    response_model=EntradaListaEsperaResponse,
    summary="Dar de baja una entrada pendiente (baja lógica)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def delete_entrada(
    entrada_id: uuid.UUID,
    current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EntradaListaEsperaResponse:
    entrada = await _propia(uow, current, consultorio_id, entrada_id)
    if entrada.estado != "pendiente":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Solo se puede dar de baja una entrada pendiente; "
                f"la entrada está {entrada.estado}"
            ),
        )
    await uow.lista_espera.soft_delete(entrada)
    return _to_response(entrada)
