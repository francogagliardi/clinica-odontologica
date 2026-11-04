"""Appointments: alta, agenda, estados y reprogramación (C-06)."""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.application.turnos import (
    ComandoTurno,
    crear_turno,
    duracion_de,
    recursos,
    traducir_exclusion,
    validar_agenda,
    validar_bloqueos,
    validar_solapamiento,
)
from app.domain.agenda import ARGENTINA_OFFSET
from app.domain.turnos import (
    ESTADOS_TERMINALES,
    calcular_fin,
    puede_transicionar,
)
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Turno
from app.models.security import Usuario
from app.schemas.turnos import (
    TurnoCreate,
    TurnoEstadoUpdate,
    TurnoListado,
    TurnoReprogramar,
    TurnoResponse,
)

router = APIRouter(prefix="/turnos", tags=["turnos"])

ROLES_LECTURA = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
_lectura = require_role(*ROLES_LECTURA)
_escritura = require_role("administrador", "recepcionista")


def _to_response(turno: Turno) -> TurnoResponse:
    return TurnoResponse(
        id=turno.id,
        consultorio_id=turno.consultorio_id,
        paciente_id=turno.paciente_id,
        profesional_id=turno.profesional_id,
        sillon_id=turno.sillon_id,
        prestacion_id=turno.prestacion_id,
        inicio=turno.inicio,
        fin=turno.fin,
        estado=turno.estado,
        origen=turno.origen,
        es_sobreturno=turno.es_sobreturno,
        color_sobreturno=turno.color_sobreturno,
        token_publico=turno.token_publico,
        is_active=turno.is_active,
    )


async def _activo(
    uow: UnitOfWork, consultorio_id: uuid.UUID, turno_id: uuid.UUID
) -> Turno:
    turno = await uow.turnos.get(turno_id)
    if (
        turno is None
        or turno.consultorio_id != consultorio_id
        or not turno.is_active
        or turno.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turno no encontrado",
        )
    return turno


def _roles(usuario: Usuario) -> set[str]:
    return {
        rol.nombre
        for rol in usuario.roles
        if rol.is_active and rol.deleted_at is None
    }


async def _autorizar_estado(
    uow: UnitOfWork, current: Usuario, turno: Turno
) -> None:
    roles = _roles(current)
    if roles & {"administrador", "recepcionista"}:
        return
    if "odontologo" in roles:
        profesional = await uow.profesionales.get(turno.profesional_id)
        if profesional is not None and profesional.usuario_id == current.id:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes",
    )


@router.post(
    "",
    response_model=TurnoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear turno con validación anti-solapamiento",
)
async def create_turno(
    payload: TurnoCreate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> TurnoResponse:
    turno = await crear_turno(
        uow,
        consultorio_id,
        ComandoTurno(
            paciente_id=payload.paciente_id,
            profesional_id=payload.profesional_id,
            sillon_id=payload.sillon_id,
            prestacion_id=payload.prestacion_id,
            inicio=payload.inicio,
            origen=payload.origen,
            es_sobreturno=payload.es_sobreturno,
            color_sobreturno=payload.color_sobreturno,
        ),
    )
    return _to_response(turno)


@router.get(
    "",
    response_model=list[TurnoResponse],
    summary="Listar turnos por rango y filtros",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "desde", "hasta", "profesional_id", "sillon_id", "estado"
            )
        )
    ],
)
async def list_turnos(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    desde: date,
    hasta: date,
    profesional_id: uuid.UUID | None = None,
    sillon_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[TurnoResponse]:
    try:
        filtros = TurnoListado(
            desde=desde,
            hasta=hasta,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            estado=estado,
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.errors()[0]["msg"],
        ) from error

    inicio_rango = datetime.combine(
        filtros.desde, time.min, tzinfo=ARGENTINA_OFFSET
    )
    fin_rango = datetime.combine(
        filtros.hasta + timedelta(days=1), time.min, tzinfo=ARGENTINA_OFFSET
    )
    turnos = await uow.turnos.list_rango(
        consultorio_id,
        desde=inicio_rango,
        hasta=fin_rango,
        profesional_id=filtros.profesional_id,
        sillon_id=filtros.sillon_id,
        estado=filtros.estado,
    )
    return [_to_response(turno) for turno in turnos]


@router.get(
    "/{turno_id}",
    response_model=TurnoResponse,
    summary="Ficha de un turno",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_turno(
    turno_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> TurnoResponse:
    return _to_response(await _activo(uow, consultorio_id, turno_id))


@router.patch(
    "/{turno_id}/estado",
    response_model=TurnoResponse,
    summary="Cambiar el estado del turno (máquina de estados)",
)
async def update_estado(
    turno_id: uuid.UUID,
    payload: TurnoEstadoUpdate,
    current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> TurnoResponse:
    turno = await _activo(uow, consultorio_id, turno_id)
    await _autorizar_estado(uow, current, turno)
    if not puede_transicionar(turno.estado, payload.estado):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Transición inválida: {turno.estado} → {payload.estado}"
            ),
        )
    turno.estado = payload.estado
    await uow.session.flush()
    return _to_response(turno)


@router.patch(
    "/{turno_id}/reprogramar",
    response_model=TurnoResponse,
    summary="Reprogramar un turno con la misma validación anti-solapamiento",
)
async def reprogramar_turno(
    turno_id: uuid.UUID,
    payload: TurnoReprogramar,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> TurnoResponse:
    turno = await _activo(uow, consultorio_id, turno_id)
    if turno.estado in ESTADOS_TERMINALES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Un turno cerrado no se puede reprogramar",
        )

    campos = payload.model_fields_set
    if "inicio" in campos and payload.inicio is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El inicio no puede ser nulo",
        )
    if "profesional_id" in campos and payload.profesional_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El profesional no puede ser nulo",
        )
    if "sillon_id" in campos and payload.sillon_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El sillón no puede ser nulo",
        )

    nuevo_inicio = payload.inicio or turno.inicio
    nuevo_profesional_id = payload.profesional_id or turno.profesional_id
    nuevo_sillon_id = payload.sillon_id or turno.sillon_id
    nueva_prestacion_id = (
        payload.prestacion_id
        if "prestacion_id" in campos
        else turno.prestacion_id
    )

    _paciente, profesional, _sillon, prestacion = await recursos(
        uow,
        consultorio_id,
        paciente_id=turno.paciente_id,
        profesional_id=nuevo_profesional_id,
        sillon_id=nuevo_sillon_id,
        prestacion_id=nueva_prestacion_id,
    )
    nuevo_fin = calcular_fin(
        nuevo_inicio, duracion_de(prestacion, profesional)
    )
    validar_agenda(profesional, nuevo_inicio, nuevo_fin)
    await validar_bloqueos(
        uow,
        profesional_id=nuevo_profesional_id,
        sillon_id=nuevo_sillon_id,
        inicio=nuevo_inicio,
        fin=nuevo_fin,
    )
    await validar_solapamiento(
        uow,
        consultorio_id=consultorio_id,
        profesional_id=nuevo_profesional_id,
        sillon_id=nuevo_sillon_id,
        inicio=nuevo_inicio,
        fin=nuevo_fin,
        es_sobreturno=turno.es_sobreturno,
        exclude_id=turno.id,
    )

    turno.inicio = nuevo_inicio
    turno.fin = nuevo_fin
    turno.profesional_id = nuevo_profesional_id
    turno.sillon_id = nuevo_sillon_id
    turno.prestacion_id = nueva_prestacion_id
    try:
        await uow.session.flush()
    except IntegrityError as error:
        conflicto = traducir_exclusion(error)
        if conflicto is not None:
            raise conflicto from error
        raise
    return _to_response(turno)
