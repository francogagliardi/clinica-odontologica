"""C-13 Mercado Pago checkout: pending preference, 503 and no secrets."""

from sqlalchemy import func, select

from app.models.caja import CajaDiaria, Cobro
from app.models.caja import MovimientoCaja
from tests.integration.cobros_helpers import (
    cobro_payload,
    mp_override,
    setup_cobros,
)
from app.infrastructure.mercadopago import TestMercadoPagoClient
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


class FailingMercadoPago:
    async def crear_preferencia(self, **kwargs):
        raise RuntimeError("proveedor caído")

    async def consultar_pago(self, pago_id):
        return None


def _setup(session_factory, *, con_caja: bool = False) -> dict[str, object]:
    return run(setup_cobros(session_factory, con_caja=con_caja))


def _post_mp(api_client, data, cliente, **overrides):
    with mp_override(cliente):
        return api_client.post(
            "/cobros",
            json=cobro_payload(
                data,
                tipo="sena",
                medio="mercadopago",
                monto="10000.00",
                turno_id=data["turnos_cobro"]["sena"],
                **overrides,
            ),
            headers=bearer(data["actores"]["recepcionista"]),
        )


def _contar(session_factory, model) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count()).select_from(model)
            )

    return run(contar())


def test_link_de_pago_sandbox_queda_pendiente(
    api_client, session_factory
) -> None:
    """Expected: 201 pending with preference/link and no network or cash."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    respuesta = _post_mp(api_client, data, cliente)
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "pendiente"
    assert body["medio"] == "mercadopago"
    assert body["link_pago"]
    assert body["proveedor_preferencia_id"].startswith("test-pref-")
    assert "sandbox.mercadopago.test" in body["link_pago"]
    assert "MP_ACCESS_TOKEN" not in respuesta.text
    assert "webhook-secret" not in respuesta.text

    # No cash movement and no register: MP money is reconciled later.
    assert _contar(session_factory, MovimientoCaja) == 0
    assert _contar(session_factory, CajaDiaria) == 0


def test_proveedor_caido_devuelve_503_sin_cobro_huerfano(
    api_client, session_factory
) -> None:
    """Business error: provider outage is 503 and leaves zero rows."""
    data = _setup(session_factory)
    respuesta = _post_mp(api_client, data, FailingMercadoPago())
    assert respuesta.status_code == 503, respuesta.text
    assert _contar(session_factory, Cobro) == 0


def test_preferencia_para_tratamiento_no_toca_caja(
    api_client, session_factory
) -> None:
    """Edge: any payment type may use the hosted checkout."""
    data = _setup(session_factory)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        respuesta = api_client.post(
            "/cobros",
            json=cobro_payload(
                data,
                tipo="tratamiento",
                medio="mercadopago",
                monto="5000.00",
                presupuesto_id=data["presupuesto_cobro"],
            ),
            headers=bearer(data["actores"]["recepcionista"]),
        )
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "pendiente"
    assert body["link_pago"]
    assert _contar(session_factory, MovimientoCaja) == 0
