"""Inbound WhatsApp webhook processing (C-09, idempotent)."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.application.lista_espera import (
    OfertaAceptada,
    aceptar_entrada,
    oferta_vigente,
    rechazar_entrada,
    registrar_hueco_liberado,
)
from app.application.turnos import ComandoReprogramar, reprogramar_turno
from app.domain.turnos import ESTADOS_TERMINALES, puede_transicionar
from app.infrastructure.uow import UnitOfWork
from app.models.comunicaciones import MensajeWhatsApp
from app.models.lista_espera import EntradaListaEspera
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
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
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

        if mensaje.plantilla == "oferta_hueco":
            # D9: an offer reply is resolved before any turno lookup.
            resultados.append(
                await _procesar_oferta(
                    uow,
                    entrada,
                    mensaje,
                    momento,
                    base_url=base_url,
                    ttl_minutos=ttl_minutos,
                    redis_client=redis_client,
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
                # Single trigger (D1): audit once and offer the freed slot.
                await registrar_hueco_liberado(
                    uow,
                    turno,
                    now=momento,
                    base_url=base_url,
                    ttl_minutos=ttl_minutos,
                    redis_client=redis_client,
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


def _aplicado(mensaje: WebhookMensaje) -> WebhookResultado:
    return WebhookResultado(
        id=mensaje.id, aplicado=True, derivado=False
    )


async def _procesar_oferta(
    uow: UnitOfWork,
    webhook_mensaje: WebhookMensaje,
    mensaje: MensajeWhatsApp,
    momento: datetime,
    *,
    base_url: str,
    ttl_minutos: int,
    redis_client: object | None,
) -> WebhookResultado:
    """Apply an offer reply with the same services as the public link (D9)."""
    entrada: EntradaListaEspera | None = None
    if mensaje.lista_espera_id is not None:
        entrada = await uow.lista_espera.get_for_update(
            mensaje.lista_espera_id
        )

    accion = webhook_mensaje.respuesta.strip().lower()
    if accion in {"aceptar", "aceptado"} and oferta_vigente(entrada, momento):
        assert entrada is not None
        resultado = await aceptar_entrada(
            uow,
            entrada,
            now=momento,
            base_url=base_url,
            ttl_minutos=ttl_minutos,
            redis_client=redis_client,
        )
        if isinstance(resultado, OfertaAceptada):
            mensaje.respuesta = "aceptado"
            await uow.session.flush()
            return _aplicado(webhook_mensaje)
    elif accion in {"rechazar", "rechazado"} and oferta_vigente(
        entrada, momento
    ):
        assert entrada is not None
        await rechazar_entrada(
            uow,
            entrada,
            now=momento,
            base_url=base_url,
            ttl_minutos=ttl_minutos,
            redis_client=redis_client,
        )
        mensaje.respuesta = "rechazado"
        await uow.session.flush()
        return _aplicado(webhook_mensaje)

    mensaje.respuesta = "derivado"
    await uow.session.flush()
    return _derivado(webhook_mensaje)
