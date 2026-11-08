"""C-14 group 5.5: internal/fiscal numbering, concurrency and rollback."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.application.comprobantes import procesar_comprobante
from app.infrastructure.arca import TestArcaClient
from app.models import Comprobante
from tests.integration.comprobantes_helpers import (
    crear_comprobante_pendiente,
    fiscal_config,
    leer_comprobante,
    post_efectivo,
    secuencia_db,
    setup_comprobantes,
)
from tests.integration.helpers import run

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def test_dos_altas_concurrentes_obtienen_numeros_distintos_y_consecutivos(
    api_client, session_factory
) -> None:
    """Expected: the row lock serializes the counter, no duplicate number."""
    data = _setup(session_factory)

    def cobrar(_: int) -> int:
        body = post_efectivo(api_client, data, monto="1000.00")
        return body["id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        cobros = list(pool.map(cobrar, range(2)))

    async def numeros() -> list[int]:
        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(Comprobante.numero_interno).where(
                        Comprobante.cobro_id.in_(
                            [uuid.UUID(cobro) for cobro in cobros]
                        )
                    )
                )
            )

    assert sorted(run(numeros())) == [1, 2]


def test_transaccion_revertida_no_consume_numero(
    api_client, session_factory
) -> None:
    """Business error: a rolled-back creation leaves the next number free."""
    from decimal import Decimal

    from app.application.comprobantes import crear_para_cobro
    from app.infrastructure.uow import UnitOfWork
    from app.models import Cobro
    from tests.integration.comprobantes_helpers import hoy, paciente_db

    data = _setup(session_factory)

    async def rollback() -> None:
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
                uow, cobro=cobro, config=fiscal_config(), usuario_id=None
            )
            raise RuntimeError("rollback")

    with pytest.raises(RuntimeError):
        run(rollback())

    body = post_efectivo(api_client, data)

    async def leer():
        async with session_factory() as session:
            return await session.scalar(
                select(Comprobante).where(
                    Comprobante.cobro_id == uuid.UUID(body["id"])
                )
            )

    comprobante = run(leer())
    assert comprobante is not None and comprobante.numero_interno == 1


def test_numero_fiscal_se_asigna_al_persistir_el_exito(
    session_factory,
) -> None:
    """Expected: creation leaves fiscal numbering untouched until emission."""
    data = _setup(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )

    secuencia_antes = run(
        secuencia_db(session_factory, data["consultorio_id"])
    )
    assert secuencia_antes is None or secuencia_antes.ultimo_fiscal == 0
    pendiente = run(leer_comprobante(session_factory, comprobante_id))
    assert pendiente is not None and pendiente.numero_fiscal is None

    cliente = TestArcaClient()
    emitido = run(
        procesar_comprobante(
            session_factory,
            cliente,
            comprobante_id,
            config=fiscal_config(),
            ahora=AHORA,
        )
    )
    assert emitido is not None
    assert emitido.estado == "emitido"
    assert emitido.numero_fiscal == 1

    secuencia = run(secuencia_db(session_factory, data["consultorio_id"]))
    assert secuencia is not None and secuencia.ultimo_fiscal == 1


def test_numeracion_fiscal_es_consecutiva(session_factory) -> None:
    """Expected: two emissions get fiscal numbers 1 and 2."""
    data = _setup(session_factory)
    ids = [
        run(
            crear_comprobante_pendiente(
                session_factory, data, numero_interno=indice
            )
        )
        for indice in (1, 2)
    ]
    cliente = TestArcaClient()
    for comprobante_id in ids:
        emitido = run(
            procesar_comprobante(
                session_factory,
                cliente,
                comprobante_id,
                config=fiscal_config(),
                ahora=AHORA,
            )
        )
        assert emitido is not None
        assert emitido.estado == "emitido"

    async def numeros() -> list[int]:
        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(Comprobante.numero_fiscal).order_by(
                        Comprobante.numero_fiscal
                    )
                )
            )

    assert run(numeros()) == [1, 2]
