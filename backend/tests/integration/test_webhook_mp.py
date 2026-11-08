"""C-13 Mercado Pago webhook: signature, idempotency and reconciliation."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.infrastructure.mercadopago import TestMercadoPagoClient
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.cobros_helpers import (
    cajas_hoy,
    cobro_payload,
    firma_mp,
    leer_cobro,
    leer_turno,
    movimientos_de,
    mp_override,
    pago,
    setear_cobro,
    setup_cobros,
    webhook_payload,
)
from tests.integration.clinica_helpers import auditorias
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


def _setup(session_factory, *, con_caja: bool = False) -> dict[str, object]:
    return run(setup_cobros(session_factory, con_caja=con_caja))


def _crear_mp(
    api_client,
    data,
    cliente,
    *,
    turno_key: str = "sena",
    paciente_id=None,
) -> dict[str, object]:
    respuesta = api_client.post(
        "/cobros",
        json=cobro_payload(
            data,
            paciente_id=paciente_id or data["paciente_os_demo"].id,
            tipo="sena",
            medio="mercadopago",
            monto="10000.00",
            turno_id=data["turnos_cobro"][turno_key],
        ),
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _webhook(api_client, pago_id: str, **kwargs):
    headers = kwargs.pop("headers", None) or firma_mp(pago_id)
    body = kwargs.pop("body", None) or webhook_payload(pago_id)
    return api_client.post(
        "/webhooks/mercadopago", json=body, headers=headers
    )


def test_aprobado_concilia_cobro_sena_y_movimiento(
    api_client, session_factory
) -> None:
    """Expected: cobro approved, deposit paid, one MP income and its register."""
    data = _setup(session_factory, con_caja=False)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, monto="10000.00", pago_id="mp-ok-1")
        )
        respuesta = _webhook(api_client, "mp-ok-1")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"recibido": True}

    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None
    assert cobro.estado == "aprobado"
    assert cobro.proveedor_pago_id == "mp-ok-1"
    assert cobro.fecha_conciliacion is not None

    turno = run(leer_turno(session_factory, data["turnos_cobro"]["sena"]))
    assert turno is not None and turno.sena_estado == "pagada"

    movimientos = run(movimientos_de(session_factory, cobro_id))
    assert len(movimientos) == 1
    assert movimientos[0].medio == "mercadopago"
    assert movimientos[0].tipo == "ingreso"
    assert movimientos[0].monto == 10000

    cajas = run(cajas_hoy(session_factory, data["consultorio_id"]))
    assert len(cajas) == 1
    assert cajas[0].monto_apertura == 0
    assert cajas[0].estado == "abierta"
    assert movimientos[0].caja_id == cajas[0].id


def test_rechazado_no_cobra_ni_crea_caja(api_client, session_factory) -> None:
    """Business error: a rejected payment leaves the deposit untouched."""
    data = _setup(session_factory, con_caja=False)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(
                cobro_id=cobro_id,
                estado="rechazado",
                pago_id="mp-no-1",
            )
        )
        respuesta = _webhook(api_client, "mp-no-1")
        repetida = _webhook(api_client, "mp-no-1")
    assert respuesta.status_code == 200, respuesta.text
    assert repetida.status_code == 200, repetida.text

    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "rechazado"
    assert cobro.proveedor_pago_id == "mp-no-1"
    assert run(movimientos_de(session_factory, cobro_id)) == []
    turno = run(leer_turno(session_factory, data["turnos_cobro"]["sena"]))
    assert turno is not None and turno.sena_estado == "pendiente"
    assert run(cajas_hoy(session_factory, data["consultorio_id"])) == []
    assert len(run(auditorias(session_factory, "cobro.conciliar"))) == 1


def test_webhook_duplicado_es_idempotente(api_client, session_factory) -> None:
    """Edge: the same payment twice answers 200 and never doubles the income."""
    data = _setup(session_factory, con_caja=True)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id="mp-dup-1")
        )
        primera = _webhook(api_client, "mp-dup-1")
        segunda = _webhook(api_client, "mp-dup-1")
    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert len(run(movimientos_de(session_factory, cobro_id))) == 1
    assert (
        len(run(auditorias(session_factory, "cobro.conciliar"))) == 1
    )


def test_webhooks_duplicados_concurrentes(api_client, session_factory) -> None:
    """Edge: two simultaneous deliveries produce one income, both 200."""
    data = _setup(session_factory, con_caja=True)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id="mp-conc-1")
        )
        headers = firma_mp("mp-conc-1")
        payload = webhook_payload("mp-conc-1")

        def entregar(_: int) -> int:
            return api_client.post(
                "/webhooks/mercadopago", json=payload, headers=headers
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            estados = list(pool.map(entregar, range(2)))
    assert estados == [200, 200], estados
    assert len(run(movimientos_de(session_factory, cobro_id))) == 1


@pytest.mark.parametrize("estado", ["reembolsado", "perdido"])
def test_webhook_tardio_sobre_cobro_resuelto_no_cambia(
    api_client, session_factory, estado: str
) -> None:
    """Edge: a late approval cannot revive a refunded or lost payment."""
    data = _setup(session_factory, con_caja=True)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        run(setear_cobro(session_factory, cobro_id, estado=estado))
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id=f"mp-tarde-{estado}")
        )
        respuesta = _webhook(api_client, f"mp-tarde-{estado}")
    assert respuesta.status_code == 200, respuesta.text
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == estado
    assert run(movimientos_de(session_factory, cobro_id)) == []


@pytest.mark.parametrize(
    ("monto", "moneda"), [("9999.99", "ARS"), ("10000.00", "USD")]
)
def test_monto_o_moneda_distinta_devuelve_409(
    api_client, session_factory, monto: str, moneda: str
) -> None:
    """Business error: a different amount/currency never reconciles (409)."""
    data = _setup(session_factory, con_caja=False)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(
                cobro_id=cobro_id,
                monto=monto,
                moneda=moneda,
                pago_id="mp-mismatch-1",
            )
        )
        respuesta = _webhook(api_client, "mp-mismatch-1")
    assert respuesta.status_code == 409, respuesta.text
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "pendiente"
    assert run(movimientos_de(session_factory, cobro_id)) == []


def test_referencia_externa_desconocida_devuelve_404(
    api_client, session_factory
) -> None:
    """Business error: an unknown external reference creates nothing."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        cliente.simular_pago(
            pago(cobro_id=uuid.uuid4(), pago_id="mp-orphan-1")
        )
        respuesta = _webhook(api_client, "mp-orphan-1")
    assert respuesta.status_code == 404, respuesta.text


def test_segundo_pago_para_sena_aprobada_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: a distinct second payment for the same deposit is 409."""
    data = _setup(session_factory, con_caja=True)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id="mp-first-1")
        )
        assert _webhook(api_client, "mp-first-1").status_code == 200
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id="mp-second-2")
        )
        segundo = _webhook(api_client, "mp-second-2")
    assert segundo.status_code == 409, segundo.text
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.proveedor_pago_id == "mp-first-1"
    assert len(run(movimientos_de(session_factory, cobro_id))) == 1


def test_firma_ausente_o_adulterada_devuelve_401(
    api_client, session_factory
) -> None:
    """Business error: no signature or a forged one changes nothing."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id="mp-forged-1")
        )
        sin_firma = api_client.post(
            "/webhooks/mercadopago", json=webhook_payload("mp-forged-1")
        )
        headers = firma_mp("mp-forged-1")
        headers["x-signature"] = "ts=1,v1=" + ("0" * 64)
        adulterada = api_client.post(
            "/webhooks/mercadopago",
            json=webhook_payload("mp-forged-1"),
            headers=headers,
        )
    assert sin_firma.status_code == 401, sin_firma.text
    assert adulterada.status_code == 401, adulterada.text
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "pendiente"
    assert run(movimientos_de(session_factory, cobro_id)) == []


def test_webhook_rechaza_pago_que_no_corresponde_a_efectivo(
    api_client, session_factory
) -> None:
    """Edge: an MP approval cannot conciliate a cash payment."""
    data = _setup(session_factory, con_caja=True)
    cobro_id = run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="otro",
            medio="efectivo",
            estado="aprobado",
            monto="15000.00",
        )
    )
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        cliente.simular_pago(
            pago(
                cobro_id=cobro_id,
                monto="15000.00",
                pago_id="mp-cash-1",
            )
        )
        respuesta = _webhook(api_client, "mp-cash-1")
    assert respuesta.status_code == 409, respuesta.text
    assert run(movimientos_de(session_factory, cobro_id)) == []


def test_caja_automatica_concurrente_se_crea_una_sola(
    api_client, session_factory
) -> None:
    """Edge: two MP approvals without a register race and share one (D10)."""
    data = _setup(session_factory, con_caja=False)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        primera = _crear_mp(api_client, data, cliente)
        segunda = _crear_mp(
            api_client,
            data,
            cliente,
            turno_key="ajeno",
            paciente_id=data["paciente_ajeno"].id,
        )
        cobro_a = uuid.UUID(primera["id"])
        cobro_b = uuid.UUID(segunda["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_a, pago_id="mp-caja-a")
        )
        cliente.simular_pago(
            pago(cobro_id=cobro_b, pago_id="mp-caja-b")
        )
        entregas = [
            ("mp-caja-a", firma_mp("mp-caja-a")),
            ("mp-caja-b", firma_mp("mp-caja-b")),
        ]

        def entregar(par) -> int:
            pago_id, headers = par
            return api_client.post(
                "/webhooks/mercadopago",
                json=webhook_payload(pago_id),
                headers=headers,
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            estados = list(pool.map(entregar, entregas))

    assert estados == [200, 200], estados
    cajas = run(cajas_hoy(session_factory, data["consultorio_id"]))
    assert len(cajas) == 1
    assert cajas[0].monto_apertura == 0
    assert len(run(movimientos_de(session_factory, cobro_a))) == 1
    assert len(run(movimientos_de(session_factory, cobro_b))) == 1
