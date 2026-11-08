"""C-14 group 5.7: `comprobante.crear` audit actor and rejected writes."""

import uuid

from app.infrastructure.mercadopago import TestMercadoPagoClient
from tests.integration.clinica_helpers import auditorias
from tests.integration.cobros_helpers import (
    firma_mp,
    mp_override,
    pago,
    webhook_payload,
)
from tests.integration.comprobantes_helpers import (
    comprobante_de_cobro,
    contar_comprobantes,
    post_cobro,
    post_efectivo,
    setup_comprobantes,
)
from tests.integration.helpers import run


def _setup(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def test_efectivo_audita_con_el_usuario_y_el_borde(
    api_client, session_factory
) -> None:
    """Expected: the receptionist, IP and device land in the audit row."""
    data = _setup(session_factory)
    body = post_efectivo(
        api_client, data, actor="recepcionista"
    )

    async def leer():
        comprobante = await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )
        crear = await auditorias(session_factory, "comprobante.crear")
        return comprobante, crear

    comprobante, crear = run(leer())
    assert comprobante is not None
    assert len(crear) == 1
    fila = crear[0]
    assert fila.usuario_id == data["actores"]["recepcionista"].id
    assert fila.entidad == "comprobante"
    assert fila.entidad_id == str(comprobante.id)
    assert fila.ip == "testclient"
    assert fila.dispositivo == "pytest-ua-c14"


def test_webhook_audita_con_actor_sistema(api_client, session_factory) -> None:
    """Expected: the webhook has no user, so the audit actor is the system."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        respuesta = post_cobro(
            api_client,
            data,
            tipo="otro",
            medio="mercadopago",
            monto="15000.00",
        )
        cobro_id = uuid.UUID(respuesta.json()["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, monto="15000.00", pago_id="mp-c14-aud")
        )
        assert (
            api_client.post(
                "/webhooks/mercadopago",
                json=webhook_payload("mp-c14-aud"),
                headers=firma_mp("mp-c14-aud"),
            ).status_code
            == 200
        )

    async def leer():
        comprobante = await comprobante_de_cobro(session_factory, cobro_id)
        crear = await auditorias(session_factory, "comprobante.crear")
        return comprobante, crear

    comprobante, crear = run(leer())
    assert comprobante is not None
    assert len(crear) == 1
    assert crear[0].usuario_id is None
    assert crear[0].entidad_id == str(comprobante.id)


def test_alta_rechazada_no_deja_auditoria_de_comprobante(
    api_client, session_factory
) -> None:
    """Business error: a rejected payment leaves no receipt and no audit."""
    data = _setup(session_factory)
    rechazada = post_cobro(
        api_client, data, tipo="otro", medio="efectivo", monto="0.00"
    )
    assert rechazada.status_code == 422, rechazada.text

    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        respuesta = post_cobro(
            api_client,
            data,
            tipo="otro",
            medio="mercadopago",
            monto="15000.00",
        )
        cobro_id = uuid.UUID(respuesta.json()["id"])
        cliente.simular_pago(
            pago(
                cobro_id=cobro_id,
                monto="15000.00",
                estado="rechazado",
                pago_id="mp-c14-aud-no",
            )
        )
        assert (
            api_client.post(
                "/webhooks/mercadopago",
                json=webhook_payload("mp-c14-aud-no"),
                headers=firma_mp("mp-c14-aud-no"),
            ).status_code
            == 200
        )

    assert run(contar_comprobantes(session_factory)) == 0
    assert run(auditorias(session_factory, "comprobante.crear")) == []
