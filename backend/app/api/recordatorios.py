"""Reminder and notification endpoints (C-09)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_redis,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.core.queues import WHATSAPP_SEND, try_enqueue
from app.infrastructure.uow import UnitOfWork
from app.models.comunicaciones import MensajeWhatsApp
from app.models.security import Usuario
from app.schemas.comunicaciones import (
    MensajeResponse,
    RecordatorioResponse,
    ReenvioResponse,
)

router = APIRouter(tags=["comunicaciones"])

_lectura = require_role(
    "administrador", "odontologo", "recepcionista", "asistente", "auditor"
)
_reenvio = require_role("administrador", "recepcionista")


def _mensaje_response(mensaje: MensajeWhatsApp) -> MensajeResponse:
    return MensajeResponse(
        id=mensaje.id,
        turno_id=mensaje.turno_id,
        lista_espera_id=mensaje.lista_espera_id,
        recordatorio_id=mensaje.recordatorio_id,
        plantilla=mensaje.plantilla,
        estado_envio=mensaje.estado_envio,
        respuesta=mensaje.respuesta,
        proveedor_mensaje_id=mensaje.proveedor_mensaje_id,
        intentos=mensaje.intentos,
        proximo_intento=mensaje.proximo_intento,
        ultimo_error=mensaje.ultimo_error,
    )


@router.get(
    "/recordatorios",
    response_model=list[RecordatorioResponse],
    summary="Listar recordatorios por rango o turno",
    dependencies=[
        Depends(
            reject_unexpected_query_except("desde", "hasta", "turno_id")
        )
    ],
)
async def list_recordatorios(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    desde: datetime | None = None,
    hasta: datetime | None = None,
    turno_id: uuid.UUID | None = None,
) -> list[RecordatorioResponse]:
    recordatorios = await uow.recordatorios.list_rango(
        desde=desde, hasta=hasta, turno_id=turno_id
    )
    return [
        RecordatorioResponse(
            id=recordatorio.id,
            turno_id=recordatorio.turno_id,
            ventana=recordatorio.ventana,
            programado_para=recordatorio.programado_para,
            estado=recordatorio.estado,
        )
        for recordatorio in recordatorios
    ]


@router.get(
    "/notificaciones",
    response_model=list[MensajeResponse],
    summary="Listar mensajes de WhatsApp",
    dependencies=[
        Depends(reject_unexpected_query_except("desde", "hasta", "estado"))
    ],
)
async def list_notificaciones(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    desde: datetime | None = None,
    hasta: datetime | None = None,
    estado: str | None = None,
) -> list[MensajeResponse]:
    mensajes = await uow.mensajes.list_rango(
        desde=desde, hasta=hasta, estado=estado
    )
    return [_mensaje_response(mensaje) for mensaje in mensajes]


@router.post(
    "/notificaciones/{mensaje_id}/reenviar",
    response_model=ReenvioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reenviar una notificación (administrador o recepción)",
)
async def reenviar(
    mensaje_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_reenvio)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    redis_client: Annotated[object | None, Depends(get_redis)],
) -> ReenvioResponse:
    original = await uow.mensajes.get(mensaje_id)
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensaje no encontrado",
        )
    nuevo = MensajeWhatsApp(
        recordatorio_id=original.recordatorio_id,
        turno_id=original.turno_id,
        lista_espera_id=original.lista_espera_id,
        plantilla=original.plantilla,
        estado_envio="pendiente",
        payload=dict(original.payload),
    )
    await uow.mensajes.add(nuevo)
    encolado = (
        await try_enqueue(redis_client, WHATSAPP_SEND, str(nuevo.id))
        if redis_client is not None
        else False
    )
    return ReenvioResponse(
        id=nuevo.id, estado_envio=nuevo.estado_envio, encolado=encolado
    )
