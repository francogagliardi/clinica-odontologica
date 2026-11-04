"""Reminder scheduling, message creation and retry processing (C-09)."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.application.plantillas import variables_recordatorio
from app.core.queues import WHATSAPP_SEND, try_enqueue
from app.domain.turnos import ESTADOS_TERMINALES
from app.infrastructure.tokens import create_single_use_token
from app.infrastructure.uow import UnitOfWork
from app.infrastructure.whatsapp import WhatsAppClient
from app.models.agenda import Turno
from app.models.comunicaciones import MensajeWhatsApp, Recordatorio
from app.models.security import RegistroAuditoria

VENTANAS = (("48h", 48 * 60), ("24h", 24 * 60))


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


async def programar_recordatorios(
    uow: UnitOfWork, turno: Turno, now: datetime | None = None
) -> None:
    """Create the 48h/24h reminders that are still in the future."""
    momento = _now(now)
    for ventana, minutos in VENTANAS:
        programado = turno.inicio - timedelta(minutes=minutos)
        if programado <= momento:
            continue
        await uow.session.execute(
            pg_insert(Recordatorio)
            .values(
                id=uuid.uuid4(),
                turno_id=turno.id,
                ventana=ventana,
                programado_para=programado,
                estado="pendiente",
            )
            .on_conflict_do_nothing(
                index_elements=["turno_id", "ventana"]
            )
        )
    await uow.session.flush()


async def cancelar_recordatorios(
    uow: UnitOfWork, turno_id: uuid.UUID
) -> None:
    """Closed appointments must not send pending reminders."""
    await uow.session.execute(
        update(Recordatorio)
        .where(
            Recordatorio.turno_id == turno_id,
            Recordatorio.estado.in_(("pendiente", "encolado")),
        )
        .values(estado="cancelado")
    )
    await uow.session.flush()


async def _crear_mensaje(
    uow: UnitOfWork,
    recordatorio: Recordatorio,
    turno: Turno,
    *,
    base_url: str,
    token_ttl_minutes: int,
) -> MensajeWhatsApp:
    paciente = await uow.pacientes.get(turno.paciente_id)
    profesional = await uow.profesionales.get(turno.profesional_id)
    if paciente is None or profesional is None:  # pragma: no cover
        raise RuntimeError("Turno sin paciente o profesional para recordatorio")

    emitido = await create_single_use_token(
        uow.session,
        tipo="gestion_turno",
        entidad_tipo="turno",
        entidad_id=str(turno.id),
        expires_minutes=token_ttl_minutes,
    )
    gestion_url = (
        f"{base_url.rstrip('/')}/reservar/gestion/{emitido.token}"
    )
    variables = variables_recordatorio(
        turno=turno,
        paciente=paciente,
        profesional=profesional,
        gestion_url=gestion_url,
    )
    mensaje = MensajeWhatsApp(
        recordatorio_id=recordatorio.id,
        turno_id=turno.id,
        plantilla="recordatorio",
        estado_envio="pendiente",
        payload={
            "telefono": paciente.telefono,
            "variables": variables,
        },
    )
    uow.session.add(mensaje)
    await uow.session.flush()
    return mensaje


async def procesar_vencidos(
    uow: UnitOfWork,
    redis_client,
    *,
    now: datetime | None = None,
    base_url: str,
    token_ttl_minutes: int,
) -> int:
    """Claim due reminders atomically and enqueue one message each."""
    momento = _now(now)
    ids = list(
        await uow.session.scalars(
            select(Recordatorio.id).where(
                Recordatorio.estado == "pendiente",
                Recordatorio.programado_para <= momento,
            )
        )
    )
    procesados = 0
    for recordatorio_id in ids:
        claimed = await uow.session.scalar(
            update(Recordatorio)
            .where(
                Recordatorio.id == recordatorio_id,
                Recordatorio.estado == "pendiente",
            )
            .values(estado="encolado")
            .returning(Recordatorio)
        )
        if claimed is None:
            continue
        turno = await uow.session.get(Turno, claimed.turno_id)
        if turno is None or turno.estado in ESTADOS_TERMINALES:
            claimed.estado = "cancelado"
            await uow.session.flush()
            continue
        mensaje = await _crear_mensaje(
            uow,
            claimed,
            turno,
            base_url=base_url,
            token_ttl_minutes=token_ttl_minutes,
        )
        encolada = (
            await try_enqueue(redis_client, WHATSAPP_SEND, str(mensaje.id))
            if redis_client is not None
            else False
        )
        if not encolada:
            claimed.estado = "fallido"
            mensaje.proximo_intento = momento
        await uow.session.flush()
        procesados += 1
    return procesados


async def procesar_mensaje(
    uow: UnitOfWork,
    cliente: WhatsAppClient,
    mensaje_id: uuid.UUID,
    *,
    now: datetime | None = None,
    max_intentos: int = 5,
) -> MensajeWhatsApp | None:
    """Send one pending message; persist success or schedule a retry."""
    momento = _now(now)
    mensaje = await uow.session.get(MensajeWhatsApp, mensaje_id)
    if mensaje is None or mensaje.estado_envio != "pendiente":
        return mensaje

    telefono = str(mensaje.payload.get("telefono", ""))
    variables = mensaje.payload.get("variables", {})
    try:
        proveedor_id = await cliente.enviar(
            telefono, mensaje.plantilla, dict(variables)  # type: ignore[arg-type]
        )
    except Exception as error:  # noqa: BLE001 - provider boundary
        mensaje.intentos += 1
        mensaje.ultimo_error = str(error)[:1000]
        if mensaje.intentos >= max_intentos:
            mensaje.estado_envio = "fallido"
            uow.session.add(
                RegistroAuditoria(
                    accion="whatsapp_fallo",
                    entidad="mensaje_whatsapp",
                    entidad_id=str(mensaje.id),
                )
            )
        else:
            mensaje.proximo_intento = momento + timedelta(
                minutes=2 ** mensaje.intentos
            )
        await uow.session.flush()
        return mensaje

    mensaje.estado_envio = "enviado"
    mensaje.proveedor_mensaje_id = proveedor_id
    mensaje.proximo_intento = None
    mensaje.ultimo_error = None
    if mensaje.recordatorio_id is not None:
        recordatorio = await uow.session.get(
            Recordatorio, mensaje.recordatorio_id
        )
        if recordatorio is not None:
            recordatorio.estado = "enviado"
    await uow.session.flush()
    return mensaje


async def procesar_reintentos(
    uow: UnitOfWork,
    cliente: WhatsAppClient,
    *,
    now: datetime | None = None,
    max_intentos: int = 5,
) -> int:
    """Retry pending messages whose backoff has elapsed."""
    momento = _now(now)
    ids = list(
        await uow.session.scalars(
            select(MensajeWhatsApp.id).where(
                MensajeWhatsApp.estado_envio == "pendiente",
                MensajeWhatsApp.proximo_intento.is_not(None),
                MensajeWhatsApp.proximo_intento <= momento,
            )
        )
    )
    for mensaje_id in ids:
        await procesar_mensaje(
            uow,
            cliente,
            mensaje_id,
            now=momento,
            max_intentos=max_intentos,
        )
    return len(ids)


async def procesar_entrante(
    uow: UnitOfWork,
    cliente: WhatsAppClient,
    mensaje_id: uuid.UUID,
    *,
    now: datetime | None = None,
    max_intentos: int = 5,
) -> MensajeWhatsApp | None:
    """Handle one queued message id (BRPOP worker entrypoint)."""
    return await procesar_mensaje(
        uow,
        cliente,
        mensaje_id,
        now=now,
        max_intentos=max_intentos,
    )
