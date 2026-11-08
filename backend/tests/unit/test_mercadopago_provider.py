"""C-13 Mercado Pago test provider: simulated, offline and explicit (D3)."""

import asyncio
import socket
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.settings import Settings
from app.infrastructure.mercadopago import (
    PagoNormalizado,
    PreferenciaPago,
    TestMercadoPagoClient,
    get_mercadopago_client,
)


def _run(coro):
    return asyncio.run(coro)


def test_preferencia_simulada_tiene_id_y_link_ficticios() -> None:
    cobro_id = uuid.uuid4()

    async def scenario() -> None:
        client = TestMercadoPagoClient()
        preferencia = await client.crear_preferencia(
            cobro_id=cobro_id,
            monto=Decimal("8000.00"),
            descripcion="Seña turno",
        )
        assert isinstance(preferencia, PreferenciaPago)
        assert preferencia.preferencia_id.startswith("test-pref-")
        # Fictional sandbox domain: no real checkout and no cost (R-12).
        assert "sandbox.mercadopago.test" in preferencia.link_pago
        assert preferencia.preferencia_id in preferencia.link_pago
        # Registered for later lookup.
        assert client.preferencias[cobro_id].preferencia_id == (
            preferencia.preferencia_id
        )

    _run(scenario())


def test_consultar_pago_lee_del_diccionario_simulado() -> None:
    cobro_id = uuid.uuid4()
    fecha = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)
    pago = PagoNormalizado(
        proveedor_pago_id="mp-pago-1",
        cobro_id=cobro_id,
        estado="aprobado",
        monto=Decimal("8000.00"),
        moneda="ARS",
        fecha=fecha,
    )

    async def scenario() -> None:
        client = TestMercadoPagoClient()
        client.simular_pago(pago)
        assert await client.consultar_pago("mp-pago-1") == pago
        assert await client.consultar_pago("mp-desconocido") is None

    _run(scenario())


def test_proveedor_real_deshabilitado_falla_de_forma_explicita(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MP_PROVIDER", "production")
    settings = Settings()
    with pytest.raises(RuntimeError, match="MP_PROVIDER"):
        get_mercadopago_client(settings)


def test_proveedor_test_no_abre_sockets(monkeypatch) -> None:
    """A network call would explode: the test double never touches the wire."""

    def explotar(*args, **kwargs):
        raise AssertionError("el proveedor de prueba intentó abrir la red")

    async def scenario() -> None:
        # Patched inside the running loop: on Windows, loop creation itself
        # uses a local socketpair and must not be intercepted.
        monkeypatch.setattr(socket.socket, "connect", explotar)
        monkeypatch.setattr(socket.socket, "connect_ex", explotar)
        client = TestMercadoPagoClient()
        preferencia = await client.crear_preferencia(
            cobro_id=uuid.uuid4(),
            monto=Decimal("15000.00"),
            descripcion="Tratamiento",
        )
        assert preferencia.preferencia_id.startswith("test-pref-")
        assert await client.consultar_pago("mp-pago-1") is None

    _run(scenario())
