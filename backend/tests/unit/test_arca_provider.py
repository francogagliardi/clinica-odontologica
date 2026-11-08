"""C-14 simulated ARCA provider: determinism, injectable failure, no network (D3).

The double must satisfy the same `Protocol` a real adapter would and must prove
by test that it neither opens a socket nor reads a certificate (R-12).
"""

import asyncio
import socket
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.fiscal import fecha_emision_local
from app.infrastructure.arca import (
    ArcaError,
    DatosReceptor,
    ResultadoEmision,
    TestArcaClient,
    get_arca_client,
)


def _receptor() -> DatosReceptor:
    return DatosReceptor(nombre="Demo, Paciente", documento="42112001")


async def _emitir(cliente: TestArcaClient, clave: str) -> ResultadoEmision:
    return await cliente.emitir(
        clave_idempotencia=clave,
        tipo="B",
        punto_venta=1,
        importe=Decimal("10000.00"),
        receptor=_receptor(),
    )


def test_cae_simulado_es_de_catorce_digitos_y_determinista() -> None:
    cliente = TestArcaClient()

    async def scenario() -> None:
        primero = await _emitir(cliente, "comprobante-estable")
        segundo = await _emitir(cliente, "comprobante-estable")
        assert len(primero.cae) == 14
        assert primero.cae.isdigit()
        assert primero.cae == segundo.cae
        assert len(cliente.llamadas) == 2

    asyncio.run(scenario())


def test_claves_distintas_derivan_cae_distinto() -> None:
    cliente = TestArcaClient()

    async def scenario() -> None:
        uno = await _emitir(cliente, "comprobante-1")
        otro = await _emitir(cliente, "comprobante-2")
        assert uno.cae != otro.cae

    asyncio.run(scenario())


def test_vencimiento_del_cae_es_a_diez_dias() -> None:
    cliente = TestArcaClient()

    async def scenario() -> None:
        resultado = await _emitir(cliente, "comprobante-vencimiento")
        hoy = fecha_emision_local(datetime.now(timezone.utc))
        assert (resultado.cae_vencimiento - hoy).days == 10

    asyncio.run(scenario())


def test_fallo_inyectable_no_emite_y_se_recupera_despues() -> None:
    cliente = TestArcaClient()
    cliente.simular_fallo(1)

    async def scenario() -> None:
        with pytest.raises(ArcaError, match="simulado"):
            await _emitir(cliente, "comprobante-fallido")
        recuperado = await _emitir(cliente, "comprobante-fallido")
        assert recuperado.cae.isdigit()
        assert len(recuperado.cae) == 14

    asyncio.run(scenario())


def test_proveedor_no_disponible_falla_de_forma_explicita() -> None:
    cliente = TestArcaClient(disponible=False)

    async def scenario() -> None:
        with pytest.raises(ArcaError, match="no disponible"):
            await _emitir(cliente, "comprobante-sin-servicio")

    asyncio.run(scenario())


def test_proveedor_distinto_de_test_falla_sin_emitir() -> None:
    with pytest.raises(RuntimeError, match="ARCA_PROVIDER"):
        get_arca_client(SimpleNamespace(arca_provider="produccion"))


def test_get_arca_client_test_devuelve_el_doble() -> None:
    cliente = get_arca_client(SimpleNamespace(arca_provider="test"))
    assert isinstance(cliente, TestArcaClient)


def test_emision_simulada_no_abre_sockets() -> None:
    """Expected: no network path exists in the trial provider."""

    async def scenario() -> None:
        cliente = TestArcaClient()
        resultado = await _emitir(cliente, "comprobante-sin-red")
        assert resultado.cae.isdigit()

    def _prohibido(*args: object, **kwargs: object) -> None:
        raise AssertionError("el cliente de prueba no debe abrir red")

    original_socket = socket.socket
    original_connect = socket.create_connection
    loop = asyncio.new_event_loop()  # created before forbidding sockets
    try:
        socket.socket = _prohibido  # type: ignore[assignment]
        socket.create_connection = _prohibido  # type: ignore[assignment]
        loop.run_until_complete(scenario())
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_connect  # type: ignore[assignment]
        loop.close()


def test_cliente_de_prueba_no_lee_certificados() -> None:
    """The fake settings have no cert path: touching one would raise."""
    cliente = get_arca_client(SimpleNamespace(arca_provider="test"))

    async def scenario() -> None:
        resultado = await _emitir(cliente, "comprobante-sin-certificado")
        assert len(resultado.cae) == 14

    asyncio.run(scenario())
