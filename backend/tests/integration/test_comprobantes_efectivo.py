"""C-14 group 5.1: cash receipts, pending MP and gapless numbering."""

import uuid
from decimal import Decimal

import pytest

from app.api.deps import get_redis
from app.application.comprobantes import crear_para_cobro
from app.domain.fiscal import decodificar_qr
from app.infrastructure.mercadopago import TestMercadoPagoClient
from app.infrastructure.uow import UnitOfWork
from app.main import app
from tests.integration.clinica_helpers import auditorias
from tests.integration.cobros_helpers import mp_override
from tests.integration.comprobantes_helpers import (
    FakeRedis,
    comprobante_de_cobro,
    contar_comprobantes,
    fiscal_config,
    hoy,
    paciente_db,
    post_cobro,
    post_efectivo,
    secuencia_db,
    setup_comprobantes,
)
from tests.integration.helpers import run


def _setup(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def test_cobro_efectivo_aprobado_crea_comprobante_pendiente(
    api_client, session_factory
) -> None:
    """Expected: 201 plus one pending receipt with number, type, amount and QR."""
    data = _setup(session_factory)
    body = post_efectivo(api_client, data)

    async def leer():
        return await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )

    comprobante = run(leer())
    assert comprobante is not None
    assert comprobante.estado == "pendiente"
    assert comprobante.tipo == "B"
    assert comprobante.ambiente == "homologacion"
    assert comprobante.numero_interno == 1
    assert comprobante.punto_venta == 1
    assert comprobante.importe_total == Decimal("15000.00")
    assert comprobante.fecha_emision == hoy()
    assert comprobante.cae is None
    assert comprobante.numero_fiscal is None
    assert comprobante.qr_fiscal is None

    paciente = paciente_db(data)
    assert comprobante.receptor_nombre == (
        f"{paciente.apellido}, {paciente.nombre}"
    )
    assert comprobante.receptor_documento == paciente.dni
    assert comprobante.receptor_tipo_documento == "DNI"
    assert comprobante.condicion_fiscal_receptor == "consumidor_final"
    assert comprobante.condicion_fiscal_emisor == (
        "responsable_inscripto"
    )

    datos_qr = decodificar_qr(comprobante.qr_interno)
    assert datos_qr["tipo"] == "INTERNO"
    assert datos_qr["comprobante_id"] == str(comprobante.id)
    assert datos_qr["numero_interno"] == 1
    assert Decimal(str(datos_qr["importe"])) == Decimal("15000.00")


def test_cobro_efectivo_encola_el_id_en_arca_emitir(
    api_client, session_factory
) -> None:
    """Expected: creation is best-effort enqueued for the worker (D4)."""
    data = _setup(session_factory)
    fake = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: fake
    try:
        body = post_efectivo(api_client, data)
    finally:
        app.dependency_overrides.pop(get_redis, None)

    async def leer_id():
        comprobante = await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )
        assert comprobante is not None
        return str(comprobante.id)

    comprobante_id = run(leer_id())
    assert ("arca:emitir", comprobante_id) in fake.items


def test_cobro_mp_pendiente_no_crea_comprobante(
    api_client, session_factory
) -> None:
    """Business error: only an approval creates the receipt."""
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
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["estado"] == "pendiente"

    async def leer():
        return await comprobante_de_cobro(
            session_factory, uuid.UUID(respuesta.json()["id"])
        )

    assert run(leer()) is None
    assert run(contar_comprobantes(session_factory)) == 0


def test_alta_rechazada_no_consume_numeracion(
    api_client, session_factory
) -> None:
    """Business error: a rolled-back creation leaves the counter untouched."""
    data = _setup(session_factory)

    async def rollback() -> None:
        from app.models import Cobro

        async with UnitOfWork(session_factory) as uow:
            cobro = Cobro(
                id=uuid.uuid4(),
                consultorio_id=data["consultorio_id"],
                paciente_id=paciente_db(data).id,
                tipo="otro",
                medio="efectivo",
                estado="aprobado",
                monto=Decimal("15000.00"),
                fecha_operacion=hoy(),
            )
            uow.session.add(cobro)
            await uow.session.flush()
            await crear_para_cobro(
                uow,
                cobro=cobro,
                config=fiscal_config(),
                usuario_id=None,
            )
            raise RuntimeError("la transacción se revierte")

    with pytest.raises(RuntimeError):
        run(rollback())

    assert run(contar_comprobantes(session_factory)) == 0
    secuencia = run(secuencia_db(session_factory, data["consultorio_id"]))
    assert secuencia is None or secuencia.ultimo_interno == 0

    body = post_efectivo(api_client, data)

    async def leer():
        return await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )

    comprobante = run(leer())
    assert comprobante is not None
    assert comprobante.numero_interno == 1


def test_creacion_idempotente_no_duplica_ni_audita(
    session_factory,
) -> None:
    """Edge: a second attempt returns the existing receipt (D1/D5)."""
    data = _setup(session_factory)

    async def scenario() -> None:
        from app.models import Cobro

        async with UnitOfWork(session_factory) as uow:
            cobro = Cobro(
                id=uuid.uuid4(),
                consultorio_id=data["consultorio_id"],
                paciente_id=paciente_db(data).id,
                tipo="otro",
                medio="efectivo",
                estado="aprobado",
                monto=Decimal("15000.00"),
                fecha_operacion=hoy(),
            )
            uow.session.add(cobro)
            await uow.session.flush()
            primero = await crear_para_cobro(
                uow, cobro=cobro, config=fiscal_config(), usuario_id=None
            )
            segundo = await crear_para_cobro(
                uow, cobro=cobro, config=fiscal_config(), usuario_id=None
            )
            assert segundo.id == primero.id
            assert segundo.numero_interno == primero.numero_interno

        assert await contar_comprobantes(session_factory) == 1
        assert len(await auditorias(session_factory, "comprobante.crear")) == 1

    run(scenario())
