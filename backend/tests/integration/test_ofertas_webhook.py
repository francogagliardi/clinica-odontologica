"""Offer responses through the WhatsApp webhook (C-10, tasks 8.1/8.2)."""

import pytest
from sqlalchemy import func, select

from app.application.webhooks import procesar_webhook
from app.infrastructure.uow import UnitOfWork
from app.models import MensajeWhatsApp, Turno
from app.schemas.comunicaciones import WebhookMensaje
from tests.integration.helpers import run
from tests.integration.ofertas_helpers import (
    FakeRedis,
    ahora,
    cancelar,
    crear_entrada,
    crear_turno,
    hora,
    leer_entrada,
    marcar_mensaje_enviado,
    mensajes_oferta,
    setup_base,
)


def _procesar(
    session_factory, fake: FakeRedis, mensaje: WebhookMensaje
):
    async def procesar():
        async with UnitOfWork(session_factory) as uow:
            return await procesar_webhook(
                uow,
                [mensaje],
                now=ahora(),
                base_url="http://127.0.0.1:8080",
                ttl_minutos=30,
                redis_client=fake,
            )

    return run(procesar())


def _contar_turnos(session_factory, estado: str = "reservado") -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(Turno)
                .where(Turno.estado == estado)
            )

    return run(contar())


def _leer_mensaje(session_factory, mensaje_id) -> MensajeWhatsApp:
    async def leer():
        async with session_factory() as session:
            fila = await session.get(MensajeWhatsApp, mensaje_id)
            assert fila is not None
            return fila

    return run(leer())


def test_aceptar_por_whatsapp_crea_el_turno(
    api_client, session_factory
) -> None:
    """Expected: the reply applies the same conversion as the link."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    mensaje = mensajes_oferta(session_factory)[0]
    marcar_mensaje_enviado(session_factory, mensaje.id, "wamid.c10-aceptar")

    resultado = _procesar(
        session_factory,
        FakeRedis(),
        WebhookMensaje(id="wamid.c10-aceptar", respuesta="aceptar"),
    )

    assert resultado[0].aplicado is True
    assert resultado[0].derivado is False
    assert _leer_mensaje(session_factory, mensaje.id).respuesta == "aceptado"
    assert leer_entrada(session_factory, entrada["id"]).estado == "convertido"
    assert _contar_turnos(session_factory) == 1

    async def turno_creado() -> Turno:
        async with session_factory() as session:
            fila = await session.scalar(
                select(Turno).where(Turno.estado == "reservado")
            )
            assert fila is not None
            return fila

    creado = run(turno_creado())
    assert creado.profesional_id == base["profesional"].id
    assert creado.sillon_id == base["sillon"].id
    assert creado.inicio == hora(9)


def test_rechazar_por_whatsapp_libera_y_rota(
    api_client, session_factory
) -> None:
    """Expected: the reply releases and offers the slot to the next entry."""
    base = setup_base(session_factory)
    primera = crear_entrada(api_client, base)
    segunda = crear_entrada(api_client, base, paciente=base["paciente2"])
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    mensaje = mensajes_oferta(session_factory)[0]
    marcar_mensaje_enviado(session_factory, mensaje.id, "wamid.c10-rechazar")

    resultado = _procesar(
        session_factory,
        FakeRedis(),
        WebhookMensaje(id="wamid.c10-rechazar", respuesta="rechazar"),
    )

    assert resultado[0].aplicado is True
    assert _leer_mensaje(session_factory, mensaje.id).respuesta == "rechazado"
    assert leer_entrada(session_factory, primera["id"]).estado == "vencido"
    assert leer_entrada(session_factory, segunda["id"]).estado == "ofrecido"
    assert len(mensajes_oferta(session_factory)) == 2
    assert _contar_turnos(session_factory) == 0


def test_evento_duplicado_no_crea_un_segundo_turno(
    api_client, session_factory
) -> None:
    """Edge: provider message id idempotency (C-09) still applies."""
    base = setup_base(session_factory)
    crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    mensaje = mensajes_oferta(session_factory)[0]
    marcar_mensaje_enviado(session_factory, mensaje.id, "wamid.c10-dup")
    evento = WebhookMensaje(id="wamid.c10-dup", respuesta="aceptar")

    primero = _procesar(session_factory, FakeRedis(), evento)
    segundo = _procesar(session_factory, FakeRedis(), evento)

    assert primero[0].aplicado is True
    assert segundo[0].aplicado is False
    assert _contar_turnos(session_factory) == 1


@pytest.mark.parametrize("accion", ["confirmar", "reprogramar"])
def test_accion_no_aplicable_a_una_oferta_deriva(
    api_client, session_factory, accion: str
) -> None:
    """Business error: confirming/moving an offer is not applicable (D9)."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    mensaje = mensajes_oferta(session_factory)[0]
    marcar_mensaje_enviado(session_factory, mensaje.id, f"wamid.c10-{accion}")

    resultado = _procesar(
        session_factory,
        FakeRedis(),
        WebhookMensaje(id=f"wamid.c10-{accion}", respuesta=accion),
    )

    assert resultado[0].aplicado is False
    assert resultado[0].derivado is True
    assert leer_entrada(session_factory, entrada["id"]).estado == "ofrecido"
    assert _contar_turnos(session_factory) == 0
