"""Professional resources and base availability (C-04, R-02, R-03).

Writes require `administrador` (configuration column of the RBAC matrix);
reads are open to every role that operates the agenda. Availability is computed
by the pure function in `app.domain.agenda`, so C-06 can reuse it.
"""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.domain.agenda import (
    ARGENTINA_OFFSET,
    AgendaConfig as AgendaConfigDominio,
    RangoBloqueo,
    calcular_disponibilidad,
)
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Profesional
from app.models.security import Usuario
from app.schemas.recursos import (
    AgendaConfig,
    ProfesionalCreate,
    ProfesionalResponse,
    ProfesionalUpdate,
    SillonResponse,
    SlotResponse,
)

router = APIRouter(prefix="/profesionales", tags=["profesionales"])

AGENDA_ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
_lectura = require_role(*AGENDA_ROLES)
_escritura = require_role("administrador")


def _to_response(profesional: Profesional) -> ProfesionalResponse:
    return ProfesionalResponse(
        id=profesional.id,
        consultorio_id=profesional.consultorio_id,
        usuario_id=profesional.usuario_id,
        matricula=profesional.matricula,
        especialidades=profesional.especialidades,
        agenda_config=AgendaConfig(
            duracion_base_min=profesional.duracion_base_min,
            dias_atencion=profesional.dias_atencion,
            hora_desde=profesional.hora_desde,
            hora_hasta=profesional.hora_hasta,
        ),
        is_active=profesional.is_active,
    )


async def _activo(
    uow: UnitOfWork, profesional_id: uuid.UUID
) -> Profesional:
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


async def _validar_usuario(
    uow: UnitOfWork,
    usuario_id: uuid.UUID | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if usuario_id is None:
        return
    if await uow.usuarios.get(usuario_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    if (
        await uow.profesionales.get_by_usuario(usuario_id, exclude_id)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya está vinculado a otro profesional activo",
        )


def _datos_agenda(payload: ProfesionalCreate) -> dict[str, object]:
    agenda = payload.agenda_config
    return {
        "duracion_base_min": agenda.duracion_base_min,
        "dias_atencion": agenda.dias_atencion,
        "hora_desde": agenda.hora_desde,
        "hora_hasta": agenda.hora_hasta,
    }


@router.get(
    "",
    response_model=list[ProfesionalResponse],
    summary="Listar profesionales activos",
    dependencies=[Depends(reject_unexpected_query)],
)
async def list_profesionales(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[ProfesionalResponse]:
    profesionales = await uow.profesionales.list()
    return [_to_response(profesional) for profesional in profesionales]


@router.post(
    "",
    response_model=ProfesionalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear profesional (solo administrador)",
)
async def create_profesional(
    payload: ProfesionalCreate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ProfesionalResponse:
    if (
        await uow.profesionales.get_by_matricula(
            consultorio_id, payload.matricula
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La matrícula ya está registrada en este consultorio",
        )
    await _validar_usuario(uow, payload.usuario_id)

    profesional = Profesional(
        consultorio_id=consultorio_id,
        matricula=payload.matricula,
        usuario_id=payload.usuario_id,
        especialidades=payload.especialidades,
        **_datos_agenda(payload),
    )
    await uow.profesionales.add(profesional)
    return _to_response(profesional)


@router.get(
    "/{profesional_id}",
    response_model=ProfesionalResponse,
    summary="Obtener un profesional activo",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_profesional(
    profesional_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> ProfesionalResponse:
    return _to_response(await _activo(uow, profesional_id))


@router.put(
    "/{profesional_id}",
    response_model=ProfesionalResponse,
    summary="Actualizar profesional (solo administrador)",
)
async def update_profesional(
    profesional_id: uuid.UUID,
    payload: ProfesionalUpdate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> ProfesionalResponse:
    profesional = await _activo(uow, profesional_id)
    if (
        await uow.profesionales.get_by_matricula(
            profesional.consultorio_id,
            payload.matricula,
            exclude_id=profesional.id,
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La matrícula ya está registrada en este consultorio",
        )
    await _validar_usuario(uow, payload.usuario_id, exclude_id=profesional.id)

    profesional.matricula = payload.matricula
    profesional.usuario_id = payload.usuario_id
    profesional.especialidades = payload.especialidades
    for campo, valor in _datos_agenda(payload).items():
        setattr(profesional, campo, valor)
    await uow.session.flush()
    return _to_response(profesional)


@router.delete(
    "/{profesional_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de profesional (solo administrador)",
)
async def delete_profesional(
    profesional_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> Response:
    profesional = await _activo(uow, profesional_id)
    await uow.profesionales.soft_delete(profesional)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{profesional_id}/sillones",
    response_model=list[SillonResponse],
    summary="Sillones habilitados para el profesional",
    dependencies=[Depends(reject_unexpected_query)],
)
async def list_sillones_habilitados(
    profesional_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[SillonResponse]:
    profesional = await _activo(uow, profesional_id)
    sillon_ids = await uow.profesionales_sillones.list_sillon_ids(
        profesional.id
    )
    sillones = []
    for sillon_id in sillon_ids:
        sillon = await uow.sillones.get(sillon_id)
        if sillon is not None and sillon.deleted_at is None:
            sillones.append(
                SillonResponse(
                    id=sillon.id,
                    consultorio_id=sillon.consultorio_id,
                    nombre=sillon.nombre,
                    is_active=sillon.is_active,
                )
            )
    return sillones


@router.post(
    "/{profesional_id}/sillones/{sillon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Habilitar sillón para el profesional (idempotente)",
)
async def habilitar_sillon(
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> Response:
    profesional = await _activo(uow, profesional_id)
    sillon = await uow.sillones.get(sillon_id)
    if sillon is None or not sillon.is_active or sillon.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sillón no encontrado",
        )
    await uow.profesionales_sillones.add(profesional.id, sillon.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{profesional_id}/sillones/{sillon_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar habilitación de sillón (idempotente)",
)
async def deshabilitar_sillon(
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> Response:
    profesional = await _activo(uow, profesional_id)
    sillon = await uow.sillones.get(sillon_id)
    if sillon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sillón no encontrado",
        )
    await uow.profesionales_sillones.delete(profesional.id, sillon.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{profesional_id}/disponibilidad",
    response_model=list[SlotResponse],
    summary="Disponibilidad base por profesional y fecha",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "fecha", "prestacion_id", "sillon_id"
            )
        )
    ],
)
async def disponibilidad(
    profesional_id: uuid.UUID,
    fecha: date,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    prestacion_id: uuid.UUID | None = None,
    sillon_id: uuid.UUID | None = None,
) -> list[SlotResponse]:
    profesional = await _activo(uow, profesional_id)

    duracion: int | None = None
    if prestacion_id is not None:
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
        duracion = prestacion.duracion_min

    if sillon_id is not None:
        sillon = await uow.sillones.get(sillon_id)
        if (
            sillon is None
            or not sillon.is_active
            or sillon.deleted_at is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sillón no encontrado",
            )

    inicio_dia = datetime.combine(
        fecha, time.min, tzinfo=ARGENTINA_OFFSET
    )
    fin_dia = inicio_dia + timedelta(days=1)
    bloqueos = await uow.bloqueos.list_para_disponibilidad(
        profesional_id=profesional.id,
        sillon_id=sillon_id,
        desde=inicio_dia,
        hasta=fin_dia,
    )
    turnos = await uow.turnos.list_activos_en_rango(
        profesional_id=profesional.id,
        sillon_id=sillon_id,
        desde=inicio_dia,
        hasta=fin_dia,
    )

    slots = calcular_disponibilidad(
        fecha=fecha,
        agenda=AgendaConfigDominio(
            duracion_base_min=profesional.duracion_base_min,
            dias_atencion=tuple(profesional.dias_atencion),
            hora_desde=profesional.hora_desde,
            hora_hasta=profesional.hora_hasta,
        ),
        duracion_min=duracion,
        bloqueos=[
            RangoBloqueo(desde=bloqueo.desde, hasta=bloqueo.hasta)
            for bloqueo in bloqueos
        ],
        turnos=[
            RangoBloqueo(desde=turno.inicio, hasta=turno.fin)
            for turno in turnos
        ],
    )
    return [SlotResponse(inicio=slot.inicio, fin=slot.fin) for slot in slots]
