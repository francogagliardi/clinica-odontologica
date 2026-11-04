"""Public booking API: catalogue, availability, reservation and management.

No JWT here: the only authorization is the single-use management token
(RN-NO-03). Business rules are delegated to C-06's shared service.
"""

import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    get_redis,
    get_settings,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
)
from app.application.turnos import (
    ComandoTurno,
    crear_turno,
    duracion_de,
    profesional_y_prestacion,
    validar_bloqueos,
    validar_solapamiento,
)
from app.core.queues import WHATSAPP_SEND, try_enqueue
from app.core.settings import Settings
from app.domain.agenda import (
    ARGENTINA_OFFSET,
    AgendaConfig as AgendaConfigDominio,
    RangoBloqueo,
    calcular_disponibilidad,
)
from app.domain.turnos import (
    ESTADOS_TERMINALES,
    calcular_fin,
    puede_transicionar,
)
from app.infrastructure.tokens import (
    TokenError,
    consume_single_use_token,
    create_single_use_token,
    verify_single_use_token,
)
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Profesional, Turno
from app.models.comercial import Prestacion
from app.models.pacientes import Paciente
from app.models.security import Consultorio
from app.schemas.publico import (
    AccionResponse,
    CatalogoPublico,
    GestionTurnoResponse,
    PrestacionPublica,
    ProfesionalPublico,
    ReservaCreate,
    ReservaResponse,
    SenaPublica,
    SlotPublico,
)

router = APIRouter(prefix="/reservar", tags=["reservar"])

POLITICA_SENA = (
    "La seña se descuenta del total. Si cancelás fuera del plazo, puede "
    "perderse (RN-TU-04). El cobro se realiza por Mercado Pago."
)
POLITICA_CANCELACION = (
    "Podés cancelar sin costo hasta {horas} horas antes del turno."
)


def _consultorio(consultorio: Consultorio | None) -> Consultorio:
    if consultorio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultorio no encontrado",
        )
    return consultorio


async def _por_slug(uow: UnitOfWork, slug: str) -> Consultorio:
    return _consultorio(await uow.consultorios.get_by_slug(slug))


def _profesional_publico(profesional: Profesional) -> ProfesionalPublico:
    return ProfesionalPublico(
        id=profesional.id,
        matricula=profesional.matricula,
        especialidades=profesional.especialidades,
    )


def _prestacion_publica(prestacion: Prestacion) -> PrestacionPublica:
    return PrestacionPublica(
        id=prestacion.id,
        codigo=prestacion.codigo,
        nombre=prestacion.nombre,
        duracion_min=prestacion.duracion_min,
        precio_base=prestacion.precio_base,
        especialidad=prestacion.especialidad,
        requiere_sena=prestacion.requiere_sena,
        monto_sena=prestacion.monto_sena,
    )


def _sena(turno: Turno, prestacion: Prestacion | None) -> SenaPublica:
    return SenaPublica(
        requiere=prestacion.requiere_sena if prestacion else False,
        monto=prestacion.monto_sena if prestacion else None,
        estado=turno.sena_estado,
    )


def _politica_cancelacion(consultorio: Consultorio) -> str:
    return POLITICA_CANCELACION.format(
        horas=consultorio.plazo_cancelacion_horas
    )


@router.get(
    "/{slug}",
    response_model=CatalogoPublico,
    summary="Catálogo público del consultorio",
    dependencies=[Depends(reject_unexpected_query)],
)
async def catalogo(
    slug: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> CatalogoPublico:
    consultorio = await _por_slug(uow, slug)
    profesionales = await uow.profesionales.list_by_consultorio(consultorio.id)
    prestaciones = [
        prestacion
        for prestacion in await uow.prestaciones.list()
        if prestacion.is_active and prestacion.deleted_at is None
    ]
    return CatalogoPublico(
        slug=consultorio.slug,
        nombre=consultorio.nombre,
        profesionales=[
            _profesional_publico(profesional) for profesional in profesionales
        ],
        prestaciones=[
            _prestacion_publica(prestacion) for prestacion in prestaciones
        ],
        plazo_cancelacion_horas=consultorio.plazo_cancelacion_horas,
        politica_cancelacion=_politica_cancelacion(consultorio),
        politica_sena=POLITICA_SENA,
    )


@router.get(
    "/{slug}/disponibilidad",
    response_model=list[SlotPublico],
    summary="Disponibilidad pública por profesional y prestación",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "fecha", "profesional_id", "prestacion_id"
            )
        )
    ],
)
async def disponibilidad(
    slug: str,
    fecha: date,
    profesional_id: uuid.UUID,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    prestacion_id: uuid.UUID | None = None,
) -> list[SlotPublico]:
    consultorio = await _por_slug(uow, slug)
    profesional, prestacion = await profesional_y_prestacion(
        uow,
        consultorio.id,
        profesional_id=profesional_id,
        prestacion_id=prestacion_id,
    )

    inicio_dia = datetime.combine(fecha, time.min, tzinfo=ARGENTINA_OFFSET)
    fin_dia = inicio_dia + timedelta(days=1)
    bloqueos = await uow.bloqueos.list_para_disponibilidad(
        profesional_id=profesional.id,
        sillon_id=None,
        desde=inicio_dia,
        hasta=fin_dia,
    )
    turnos = await uow.turnos.list_activos_en_rango(
        profesional_id=profesional.id,
        sillon_id=None,
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
        duracion_min=duracion_de(prestacion, profesional),
        bloqueos=[
            RangoBloqueo(desde=bloqueo.desde, hasta=bloqueo.hasta)
            for bloqueo in bloqueos
        ],
        turnos=[
            RangoBloqueo(desde=turno.inicio, hasta=turno.fin)
            for turno in turnos
        ],
    )
    return [SlotPublico(inicio=slot.inicio, fin=slot.fin) for slot in slots]


async def _paciente_del_publico(
    uow: UnitOfWork, consultorio_id: uuid.UUID, payload: ReservaCreate
) -> Paciente:
    existente = await uow.pacientes.get_by_dni(consultorio_id, payload.dni)
    if existente is not None:
        if existente.telefono != payload.telefono:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Los datos no coinciden con un paciente registrado; "
                    "contactá a la clínica"
                ),
            )
        return existente

    paciente = Paciente(
        consultorio_id=consultorio_id,
        nombre=payload.nombre,
        apellido=payload.apellido,
        dni=payload.dni,
        telefono=payload.telefono,
        email=payload.email,
    )
    try:
        async with uow.session.begin_nested():
            uow.session.add(paciente)
            await uow.session.flush()
    except IntegrityError:
        # Two concurrent reservations created the same patient: reuse the row
        # that won the unique index instead of failing the booking.
        existente = await uow.pacientes.get_by_dni(
            consultorio_id, payload.dni
        )
        if existente is None or existente.telefono != payload.telefono:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Los datos no coinciden con un paciente registrado; "
                    "contactá a la clínica"
                ),
            )
        return existente
    return paciente


async def _elegir_sillon(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    profesional_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
) -> uuid.UUID:
    sillones = await uow.sillones.list_by_consultorio(consultorio_id)
    habilitados = set(
        await uow.profesionales_sillones.list_sillon_ids(profesional_id)
    )
    candidatos = [
        sillon
        for sillon in sillones
        if not habilitados or sillon.id in habilitados
    ]
    for sillon in sorted(candidatos, key=lambda item: item.nombre):
        try:
            await validar_bloqueos(
                uow,
                profesional_id=profesional_id,
                sillon_id=sillon.id,
                inicio=inicio,
                fin=fin,
            )
            await validar_solapamiento(
                uow,
                consultorio_id=consultorio_id,
                profesional_id=profesional_id,
                sillon_id=sillon.id,
                inicio=inicio,
                fin=fin,
                es_sobreturno=False,
            )
        except HTTPException as error:
            if error.status_code == status.HTTP_409_CONFLICT:
                continue
            raise
        return sillon.id
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No hay sillón disponible para ese horario",
    )


async def _encolar_confirmacion(
    redis_client, turno: Turno
) -> str:
    if redis_client is None:
        return "pendiente_reintento"
    payload = json.dumps(
        {"tipo": "confirmacion_reserva", "turno_id": str(turno.id)}
    )
    encolada = await try_enqueue(redis_client, WHATSAPP_SEND, payload)
    return "encolada" if encolada else "pendiente_reintento"


@router.post(
    "/{slug}/turnos",
    response_model=ReservaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reservar un turno desde el enlace público",
)
async def reservar(
    slug: str,
    payload: ReservaCreate,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    redis_client: Annotated[object | None, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReservaResponse:
    consultorio = await _por_slug(uow, slug)
    paciente = await _paciente_del_publico(uow, consultorio.id, payload)

    profesional, prestacion = await profesional_y_prestacion(
        uow,
        consultorio.id,
        profesional_id=payload.profesional_id,
        prestacion_id=payload.prestacion_id,
    )
    fin = calcular_fin(
        payload.inicio, duracion_de(prestacion, profesional)
    )
    sillon_id = await _elegir_sillon(
        uow,
        consultorio_id=consultorio.id,
        profesional_id=payload.profesional_id,
        inicio=payload.inicio,
        fin=fin,
    )

    turno = await crear_turno(
        uow,
        consultorio.id,
        ComandoTurno(
            paciente_id=paciente.id,
            profesional_id=payload.profesional_id,
            sillon_id=sillon_id,
            prestacion_id=payload.prestacion_id,
            inicio=payload.inicio,
            origen="online",
            es_sobreturno=False,
            color_sobreturno=None,
        ),
    )
    emitido = await create_single_use_token(
        uow.session,
        tipo="gestion_turno",
        entidad_tipo="turno",
        entidad_id=str(turno.id),
        expires_minutes=settings.gestion_token_ttl_minutes,
    )
    whatsapp = await _encolar_confirmacion(redis_client, turno)
    gestion_url = (
        f"{settings.app_base_url.rstrip('/')}/reservar/gestion/"
        f"{emitido.token}"
    )
    return ReservaResponse(
        turno_id=turno.id,
        inicio=turno.inicio,
        fin=turno.fin,
        estado=turno.estado,
        profesional=_profesional_publico(profesional),
        prestacion=(
            _prestacion_publica(prestacion) if prestacion is not None else None
        ),
        sena=_sena(turno, prestacion),
        gestion_url=gestion_url,
        whatsapp_confirmacion=whatsapp,
        plazo_cancelacion_horas=consultorio.plazo_cancelacion_horas,
        politica_sena=POLITICA_SENA,
    )


def _token_invalido(error: TokenError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="El enlace de gestión no es válido o venció",
    )


async def _turno_del_token(uow: UnitOfWork, token: str) -> Turno:
    try:
        registro = await verify_single_use_token(
            uow.session, token, expected_tipo="gestion_turno"
        )
    except TokenError as error:
        raise _token_invalido(error) from error

    try:
        turno_id = uuid.UUID(registro.entidad_id)
    except ValueError as error:
        raise _token_invalido(error) from error

    turno = await uow.turnos.get(turno_id)
    if (
        turno is None
        or not turno.is_active
        or turno.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="El enlace de gestión no es válido o venció",
        )
    return turno


async def _respuesta_gestion(
    uow: UnitOfWork, turno: Turno
) -> GestionTurnoResponse:
    consultorio = await uow.consultorios.get(turno.consultorio_id)
    assert consultorio is not None
    profesional = await uow.profesionales.get(turno.profesional_id)
    prestacion = (
        await uow.prestaciones.get(turno.prestacion_id)
        if turno.prestacion_id is not None
        else None
    )
    assert profesional is not None
    return GestionTurnoResponse(
        turno_id=turno.id,
        inicio=turno.inicio,
        fin=turno.fin,
        estado=turno.estado,
        profesional=_profesional_publico(profesional),
        prestacion=(
            _prestacion_publica(prestacion) if prestacion is not None else None
        ),
        sena=_sena(turno, prestacion),
        puede_confirmar=turno.estado == "reservado",
        puede_cancelar=(
            turno.estado not in ESTADOS_TERMINALES
            and turno.inicio > datetime.now(timezone.utc)
        ),
        plazo_cancelacion_horas=consultorio.plazo_cancelacion_horas,
        politica_sena=POLITICA_SENA,
    )


@router.get(
    "/gestion/{token}",
    response_model=GestionTurnoResponse,
    summary="Resumen del turno desde el enlace de gestión",
    dependencies=[Depends(reject_unexpected_query)],
)
async def gestion(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> GestionTurnoResponse:
    turno = await _turno_del_token(uow, token)
    return await _respuesta_gestion(uow, turno)


async def _consumir(uow: UnitOfWork, token: str) -> None:
    try:
        await consume_single_use_token(
            uow.session, token, expected_tipo="gestion_turno"
        )
    except TokenError as error:
        raise _token_invalido(error) from error


@router.post(
    "/gestion/{token}/confirmar",
    response_model=AccionResponse,
    summary="Confirmar el turno desde el enlace",
)
async def confirmar(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> AccionResponse:
    turno = await _turno_del_token(uow, token)
    if not puede_transicionar(turno.estado, "confirmado"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"No se puede confirmar un turno en estado {turno.estado}",
        )
    await _consumir(uow, token)
    turno.estado = "confirmado"
    await uow.session.flush()
    return AccionResponse(estado=turno.estado, sena_perdida=False)


@router.post(
    "/gestion/{token}/cancelar",
    response_model=AccionResponse,
    summary="Cancelar el turno desde el enlace",
)
async def cancelar(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> AccionResponse:
    turno = await _turno_del_token(uow, token)
    if not puede_transicionar(turno.estado, "cancelado"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"No se puede cancelar un turno en estado {turno.estado}",
        )
    consultorio = await uow.consultorios.get(turno.consultorio_id)
    assert consultorio is not None
    limite = turno.inicio - timedelta(
        hours=consultorio.plazo_cancelacion_horas
    )
    tarde = datetime.now(timezone.utc) > limite
    await _consumir(uow, token)
    turno.estado = "cancelado"
    sena_perdida = tarde and turno.sena_estado in {"pendiente", "pagada"}
    if sena_perdida:
        turno.sena_estado = "perdida"
    await uow.session.flush()
    return AccionResponse(estado=turno.estado, sena_perdida=sena_perdida)
