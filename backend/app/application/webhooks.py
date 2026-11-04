"""Inbound WhatsApp webhook processing (C-09, idempotent)."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.application.turnos import ComandoReprogramar, reprogramar_turno
from app.domain.turnos import ESTADOS_TERMINALES, puede_transicionar
from app.infrastructure.uow import UnitOfWork
from app.models.comunicaciones import MensajeWhatsApp
from app.models.security import RegistroAuditoria
from app.schemas.comunicaciones import WebhookMensaje, WebhookResultado


def firma_valida(raw_body: bytes, header: str | None, secret: str) -> bool:
    """Validate `X-Hub-Signature-256: sha256=<hex>` over the raw body."""
    if header is None or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(header.split("=", 1)[1], expected)


def _derivado(
    mensaje: WebhookMensaje, resultado: WebhookResultado | None = None
) -> WebhookResultado:
    if resultado is None:
        return WebhookResultado(
            id=mensaje.id, aplicado=False, derivado=True
        )
    resultado.derivado = True
    return resultado


async def procesar_webhook(
    uow: UnitOfWork,
    mensajes: list[WebhookMensaje],
    *,
    now: datetime | None = None,
) -> list[WebhookResultado]:
    momento = now or datetime.now(timezone.utc)
    resultados: list[WebhookResultado] = []

    for entrada in mensajes:
        mensaje = await uow.session.scalar(
            select(MensajeWhatsApp).where(
                MensajeWhatsApp.proveedor_mensaje_id == entrada.id
            )
        )
        if mensaje is None:
            resultados.append(_derivado(entrada))
            continue
        if mensaje.respuesta != "ninguna":
            resultados.append(
                WebhookResultado(
                    id=entrada.id, aplicado=False, derivado=False
                )
            )
            continue

        turno = await uow.turnos.get(mensaje.turno_id)
        if turno is None:
            mensaje.respuesta = "derivado"
            resultados.append(_derivado(entrada))
            continue
        if turno.inicio <= momento:
            mensaje.respuesta = "derivado"
            resultados.append(_derivado(entrada))
            await uow.session.flush()
            continue

        accion = entrada.respuesta.strip().lower()
        aplicado = False
        derivado = False

        if accion in {"confirmar", "confirmado"}:
            if turno.estado == "reservado" and puede_transicionar(
                turno.estado, "confirmado"
            ):
                turno.estado = "confirmado"
                mensaje.respuesta = "confirmado"
                aplicado = True
            else:
                mensaje.respuesta = "derivado"
                derivado = True
        elif accion in {"cancelar", "cancelado"}:
            if turno.estado not in ESTADOS_TERMINALES and puede_transicionar(
                turno.estado, "cancelado"
            ):
                turno.estado = "cancelado"
                mensaje.respuesta = "cancelado"
                uow.session.add(
                    RegistroAuditoria(
                        accion="hueco_liberado",
                        entidad="turno",
                        entidad_id=str(turno.id),
                    )
                )
                aplicado = True
            else:
                mensaje.respuesta = "derivado"
                derivado = True
        elif accion in {"reprogramar", "reprogramado"}:
            if entrada.nueva_fecha is None:
                mensaje.respuesta = "derivado"
                derivado = True
            else:
                try:
                    turno = await reprogramar_turno(
                        uow,
                        turno.consultorio_id,
                        turno,
                        ComandoReprogramar(inicio=entrada.nueva_fecha),
                    )
                    mensaje.respuesta = "reprogramado"
                    aplicado = True
                except HTTPException:
                    mensaje.respuesta = "derivado"
                    derivado = True
        else:
            mensaje.respuesta = "derivado"
            derivado = True

        await uow.session.flush()
        resultados.append(
            WebhookResultado(
                id=entrada.id, aplicado=aplicado, derivado=derivado
            )
        )

    return resultados
