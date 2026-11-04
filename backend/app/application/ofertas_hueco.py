"""Delivery of a freed-slot offer over the existing WhatsApp channel (C-10).

Design D9: instead of a new transport, the offer reuses `MensajeWhatsApp`,
the `whatsapp:send` queue and the single-use token infrastructure of C-09. A
Redis outage never breaks the cancellation that originated the offer: the
message stays `pendiente` with `proximo_intento` so the sender worker retries
it.
"""

from datetime import datetime

from app.application.plantillas import variables_oferta_hueco
from app.core.queues import WHATSAPP_SEND, try_enqueue
from app.infrastructure.tokens import create_single_use_token
from app.infrastructure.uow import UnitOfWork
from app.models.comunicaciones import MensajeWhatsApp
from app.models.lista_espera import EntradaListaEspera


async def emitir_oferta(
    uow: UnitOfWork,
    entrada: EntradaListaEspera,
    *,
    now: datetime,
    base_url: str,
    ttl_minutos: int,
    redis_client: object | None,
) -> MensajeWhatsApp | None:
    """Persist the offer message, issue its token and enqueue the delivery.

    The token life equals the offer TTL, so the link never outlives the
    retention it represents (design D8).
    """
    paciente = await uow.pacientes.get(entrada.paciente_id)
    profesional_id = entrada.oferta_profesional_id
    profesional = (
        await uow.profesionales.get(profesional_id)
        if profesional_id is not None
        else None
    )
    if paciente is None or profesional is None:  # pragma: no cover - parity
        return None

    emitido = await create_single_use_token(
        uow.session,
        tipo="oferta_hueco",
        entidad_tipo="entrada_lista_espera",
        entidad_id=str(entrada.id),
        expires_minutes=ttl_minutos,
    )
    oferta_url = f"{base_url.rstrip('/')}/reservar/oferta/{emitido.token}"
    variables = variables_oferta_hueco(
        entrada=entrada,
        paciente=paciente,
        profesional=profesional,
        oferta_url=oferta_url,
    )
    mensaje = MensajeWhatsApp(
        turno_id=None,
        lista_espera_id=entrada.id,
        plantilla="oferta_hueco",
        estado_envio="pendiente",
        payload={
            "telefono": paciente.telefono,
            "variables": variables,
        },
    )
    uow.session.add(mensaje)
    await uow.session.flush()

    encolada = (
        await try_enqueue(redis_client, WHATSAPP_SEND, str(mensaje.id))
        if redis_client is not None
        else False
    )
    if not encolada:
        # The sender worker picks it up through `procesar_reintentos`.
        mensaje.proximo_intento = now
        await uow.session.flush()
    return mensaje
