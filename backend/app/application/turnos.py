"""Shared appointment service (C-06/C-07).

The backoffice router and the public booking router must apply the same rules:
resource validity, duration, agenda window, blocks, anti-overlap and PostgreSQL
exclusion translation. Keeping them here avoids two diverging copies of RN-TU-01.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import DBAPIError

from app.domain.turnos import ESTADOS_TERMINALES, calcular_fin, validar_ventana
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Profesional, Sillon, Turno
from app.models.comercial import Prestacion
from app.models.pacientes import Paciente


@dataclass(frozen=True)
class ComandoTurno:
    """Input of a new appointment, independent from the HTTP schema."""

    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    sillon_id: uuid.UUID
    prestacion_id: uuid.UUID | None
    inicio: datetime
    origen: str
    es_sobreturno: bool
    color_sobreturno: str | None


def no_encontrado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=detalle
    )


async def profesional_y_prestacion(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    *,
    profesional_id: uuid.UUID,
    prestacion_id: uuid.UUID | None,
) -> tuple[Profesional, Prestacion | None]:
    profesional = await uow.profesionales.get(profesional_id)
    if (
        profesional is None
        or profesional.consultorio_id != consultorio_id
        or not profesional.is_active
        or profesional.deleted_at is not None
    ):
        raise no_encontrado("Profesional no encontrado")

    prestacion: Prestacion | None = None
    if prestacion_id is not None:
        prestacion = await uow.prestaciones.get(prestacion_id)
        if (
            prestacion is None
            or not prestacion.is_active
            or prestacion.deleted_at is not None
        ):
            raise no_encontrado("Prestación no encontrada")
    return profesional, prestacion


async def recursos(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    *,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    prestacion_id: uuid.UUID | None,
) -> tuple[Paciente, Profesional, Sillon, Prestacion | None]:
    paciente = await uow.pacientes.get(paciente_id)
    if (
        paciente is None
        or paciente.consultorio_id != consultorio_id
        or not paciente.is_active
        or paciente.deleted_at is not None
    ):
        raise no_encontrado("Paciente no encontrado")

    profesional, prestacion = await profesional_y_prestacion(
        uow,
        consultorio_id,
        profesional_id=profesional_id,
        prestacion_id=prestacion_id,
    )

    sillon = await uow.sillones.get(sillon_id)
    if (
        sillon is None
        or sillon.consultorio_id != consultorio_id
        or not sillon.is_active
        or sillon.deleted_at is not None
    ):
        raise no_encontrado("Sillón no encontrado")

    return paciente, profesional, sillon, prestacion


def validar_agenda(
    profesional: Profesional, inicio: datetime, fin: datetime
) -> None:
    try:
        validar_ventana(
            inicio,
            fin,
            dias_atencion=profesional.dias_atencion,
            hora_desde=profesional.hora_desde,
            hora_hasta=profesional.hora_hasta,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error


async def validar_bloqueos(
    uow: UnitOfWork,
    *,
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
) -> None:
    bloqueos = await uow.bloqueos.list_para_disponibilidad(
        profesional_id=profesional_id,
        sillon_id=sillon_id,
        desde=inicio,
        hasta=fin,
    )
    if bloqueos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El horario se solapa con un bloqueo del profesional o sillón",
        )


async def validar_solapamiento(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
    es_sobreturno: bool,
    exclude_id: uuid.UUID | None = None,
    retencion_excluida: uuid.UUID | None = None,
) -> None:
    """Reject overlaps with a live waiting-list offer and then with turnos.

    The retention is checked *before* the sobreturno early return: a marked
    sobreturno cannot step on an offer (C-10, `agenda/turnos`). The lazy expiry
    lives in the repository query, so an expired offer stops blocking instantly.
    """
    retenciones = await uow.lista_espera.retenciones_vigentes(
        profesional_id=profesional_id,
        sillon_id=sillon_id,
        desde=inicio,
        hasta=fin,
        now=datetime.now(timezone.utc),
        exclude_id=retencion_excluida,
    )
    if retenciones:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El horario está retenido por una oferta de lista de espera"
            ),
        )
    if es_sobreturno:
        return
    solapados = await uow.turnos.list_solapados(
        consultorio_id=consultorio_id,
        profesional_id=profesional_id,
        sillon_id=sillon_id,
        inicio=inicio,
        fin=fin,
        exclude_id=exclude_id,
    )
    if solapados:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El horario se solapa con otro turno del profesional o "
                "del sillón"
            ),
        )


def traducir_exclusion(error: DBAPIError) -> HTTPException | None:
    original = getattr(error, "orig", error)
    sqlstate = getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )
    if sqlstate == "23P01":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El horario acaba de ser ocupado por otro turno; "
                "actualizá la disponibilidad"
            ),
        )
    if sqlstate == "40P01":
        # Two concurrent inserts can deadlock on the GiST exclusion index;
        # the loser must see a conflict, not a 500, and retry.
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El horario está siendo reservado en este momento; "
                "reintentá la operación"
            ),
        )
    return None


def duracion_de(prestacion: Prestacion | None, profesional: Profesional) -> int:
    """Service duration or the professional base one (RN-TU-02)."""
    return (
        prestacion.duracion_min
        if prestacion is not None
        else profesional.duracion_base_min
    )


def estado_de_sena(prestacion: Prestacion | None) -> str:
    return (
        "pendiente"
        if prestacion is not None and prestacion.requiere_sena
        else "no_requiere"
    )


@dataclass(frozen=True)
class ComandoReprogramar:
    inicio: datetime | None = None
    profesional_id: uuid.UUID | None = None
    sillon_id: uuid.UUID | None = None
    prestacion_id: uuid.UUID | None = None
    cambiar_prestacion: bool = False


async def reprogramar_turno(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    turno: Turno,
    comando: ComandoReprogramar,
    *,
    retencion_excluida: uuid.UUID | None = None,
) -> Turno:
    """Apply the same agenda/block/overlap rules to a moved appointment."""
    if turno.estado in ESTADOS_TERMINALES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Un turno cerrado no se puede reprogramar",
        )
    nuevo_inicio = comando.inicio or turno.inicio
    nuevo_profesional_id = comando.profesional_id or turno.profesional_id
    nuevo_sillon_id = comando.sillon_id or turno.sillon_id
    nueva_prestacion_id = (
        comando.prestacion_id
        if comando.cambiar_prestacion
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
        retencion_excluida=retencion_excluida,
    )

    turno.inicio = nuevo_inicio
    turno.fin = nuevo_fin
    turno.profesional_id = nuevo_profesional_id
    turno.sillon_id = nuevo_sillon_id
    turno.prestacion_id = nueva_prestacion_id
    try:
        await uow.session.flush()
    except DBAPIError as error:
        conflicto = traducir_exclusion(error)
        if conflicto is not None:
            raise conflicto from error
        raise
    return turno


async def crear_turno(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    comando: ComandoTurno,
    *,
    retencion_excluida: uuid.UUID | None = None,
) -> Turno:
    """Validate every RN-TU rule and persist a `reservado` appointment."""
    _paciente, profesional, _sillon, prestacion = await recursos(
        uow,
        consultorio_id,
        paciente_id=comando.paciente_id,
        profesional_id=comando.profesional_id,
        sillon_id=comando.sillon_id,
        prestacion_id=comando.prestacion_id,
    )
    fin = calcular_fin(comando.inicio, duracion_de(prestacion, profesional))
    validar_agenda(profesional, comando.inicio, fin)
    await validar_bloqueos(
        uow,
        profesional_id=comando.profesional_id,
        sillon_id=comando.sillon_id,
        inicio=comando.inicio,
        fin=fin,
    )
    await validar_solapamiento(
        uow,
        consultorio_id=consultorio_id,
        profesional_id=comando.profesional_id,
        sillon_id=comando.sillon_id,
        inicio=comando.inicio,
        fin=fin,
        es_sobreturno=comando.es_sobreturno,
        retencion_excluida=retencion_excluida,
    )

    turno = Turno(
        consultorio_id=consultorio_id,
        paciente_id=comando.paciente_id,
        profesional_id=comando.profesional_id,
        sillon_id=comando.sillon_id,
        prestacion_id=comando.prestacion_id,
        inicio=comando.inicio,
        fin=fin,
        estado="reservado",
        origen=comando.origen,
        es_sobreturno=comando.es_sobreturno,
        color_sobreturno=comando.color_sobreturno,
        sena_estado=estado_de_sena(prestacion),
    )
    try:
        await uow.turnos.add(turno)
    except DBAPIError as error:
        conflicto = traducir_exclusion(error)
        if conflicto is not None:
            raise conflicto from error
        raise

    from app.application.recordatorios import programar_recordatorios

    await programar_recordatorios(uow, turno)
    return turno
