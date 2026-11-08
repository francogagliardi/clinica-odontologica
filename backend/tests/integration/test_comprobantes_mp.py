"""C-14 group 5.3: Mercado Pago approval creates exactly one receipt."""

import uuid
from concurrent.futures import ThreadPoolExecutor

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
    setup_comprobantes,
)
from tests.integration.helpers import run


def _setup(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def _crear_mp(api_client, data, *, monto: str = "15000.00"):
    respuesta = post_cobro(
        api_client,
        data,
        tipo="otro",
        medio="mercadopago",
        monto=monto,
    )
    assert respuesta.status_code == 201, respuesta.text
    return uuid.UUID(respuesta.json()["id"])


def _webhook(api_client, pago_id: str):
    return api_client.post(
        "/webhooks/mercadopago",
        json=webhook_payload(pago_id),
        headers=firma_mp(pago_id),
    )


def test_webhook_aprobado_crea_un_comprobante_pendiente(
    api_client, session_factory
) -> None:
    """Expected: approval creates one pending receipt with internal numbering."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        cobro_id = _crear_mp(api_client, data)
        cliente.simular_pago(
            pago(cobro_id=cobro_id, monto="15000.00", pago_id="mp-c14-ok")
        )
        respuesta = _webhook(api_client, "mp-c14-ok")
    assert respuesta.status_code == 200, respuesta.text

    async def leer():
        return await comprobante_de_cobro(session_factory, cobro_id)

    comprobante = run(leer())
    assert comprobante is not None
    assert comprobante.estado == "pendiente"
    assert comprobante.numero_interno == 1
    assert comprobante.tipo == "B"
    assert str(comprobante.importe_total) == "15000.00"
    assert comprobante.qr_interno.startswith(
        "https://app.local/comprobantes/verificar?p="
    )

    crear = run(auditorias(session_factory, "comprobante.crear"))
    assert len(crear) == 1
    assert crear[0].usuario_id is None
    assert crear[0].entidad == "comprobante"
    assert crear[0].entidad_id == str(comprobante.id)


def test_webhook_rechazado_no_crea_comprobante(
    api_client, session_factory
) -> None:
    """Business error: a rejected payment never produces a receipt."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        cobro_id = _crear_mp(api_client, data)
        cliente.simular_pago(
            pago(
                cobro_id=cobro_id,
                monto="15000.00",
                estado="rechazado",
                pago_id="mp-c14-no",
            )
        )
        respuesta = _webhook(api_client, "mp-c14-no")
    assert respuesta.status_code == 200, respuesta.text

    async def leer():
        return await comprobante_de_cobro(session_factory, cobro_id)

    assert run(leer()) is None
    assert run(contar_comprobantes(session_factory)) == 0
    assert run(auditorias(session_factory, "comprobante.crear")) == []


def test_webhook_repetido_no_duplica_comprobante(
    api_client, session_factory
) -> None:
    """Edge: the same approval twice leaves one receipt and one audit row."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        cobro_id = _crear_mp(api_client, data)
        cliente.simular_pago(
            pago(cobro_id=cobro_id, monto="15000.00", pago_id="mp-c14-dup")
        )
        primera = _webhook(api_client, "mp-c14-dup")
        segunda = _webhook(api_client, "mp-c14-dup")
    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text

    async def leer():
        return await comprobante_de_cobro(session_factory, cobro_id)

    assert run(leer()) is not None
    assert run(contar_comprobantes(session_factory)) == 1
    assert len(run(auditorias(session_factory, "comprobante.crear"))) == 1


def test_aprobacion_concurrente_deja_un_solo_comprobante(
    api_client, session_factory
) -> None:
    """Edge: two simultaneous deliveries still produce one receipt (D5)."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        cobro_id = _crear_mp(api_client, data)
        cliente.simular_pago(
            pago(cobro_id=cobro_id, monto="15000.00", pago_id="mp-c14-conc")
        )
        headers = firma_mp("mp-c14-conc")
        payload = webhook_payload("mp-c14-conc")

        def entregar(_: int) -> int:
            return api_client.post(
                "/webhooks/mercadopago", json=payload, headers=headers
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            estados = list(pool.map(entregar, range(2)))

    assert estados == [200, 200], estados
    assert run(contar_comprobantes(session_factory)) == 1

    async def leer():
        return await comprobante_de_cobro(session_factory, cobro_id)

    assert run(leer()) is not None
