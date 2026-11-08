"""C-14 repositories: receipt by payment, sweep, atomic claim and settlement.

Every scenario uses the real migrated PostgreSQL database and only the public
repository methods exposed by `UnitOfWork` (R-04).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.uow import UnitOfWork
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.fiscal_helpers import (
    insertar_comprobante_db,
    insertar_envio_db,
    insertar_item_liquidacion_db,
    insertar_liquidacion_db,
    setup_fiscal,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.presupuestos_helpers import (
    insertar_item_db,
    insertar_presupuesto_db,
)

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_fiscal(session_factory))


async def _cobro(data: dict[str, object], session_factory) -> uuid.UUID:
    return await insertar_cobro_db(
        session_factory,
        consultorio_id=data["consultorio_id"],
        paciente_id=data["paciente_os_demo"].id,
        tipo="otro",
        medio="efectivo",
        estado="aprobado",
        monto="10000.00",
    )


def test_comprobante_por_cobro(session_factory) -> None:
    """Expected: the unique receipt of a payment is retrievable, others are not."""
    data = _setup(session_factory)

    async def scenario() -> None:
        cobro_uno = await _cobro(data, session_factory)
        cobro_dos = await _cobro(data, session_factory)
        comprobante_uno = await insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=cobro_uno,
            paciente_id=data["paciente_os_demo"].id,
            numero_interno=1,
        )
        await insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=cobro_dos,
            paciente_id=data["paciente_os_demo"].id,
            numero_interno=2,
        )

        async with UnitOfWork(session_factory) as uow:
            encontrado = await uow.comprobantes.get_by_cobro(cobro_uno)
            assert encontrado is not None
            assert encontrado.id == comprobante_uno
            assert encontrado.numero_interno == 1
            assert encontrado.estado == "pendiente"
            assert await uow.comprobantes.get_by_cobro(uuid.uuid4()) is None

    run(scenario())


def test_pendientes_vencidos_para_el_barrido(session_factory) -> None:
    """Expected: only due, unclaimed `pendiente` rows are swept (D4)."""
    data = _setup(session_factory)

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_os_demo"].id
        numero = 0

        async def comprobante(**kwargs: object) -> uuid.UUID:
            nonlocal numero
            numero += 1
            return await insertar_comprobante_db(
                session_factory,
                consultorio_id=consultorio_id,
                cobro_id=await _cobro(data, session_factory),
                paciente_id=paciente_id,
                numero_interno=numero,
                **kwargs,
            )

        sin_proximo = await comprobante()
        vencido = await comprobante(
            proximo_intento=AHORA - timedelta(minutes=1)
        )
        await comprobante(proximo_intento=AHORA + timedelta(minutes=10))
        await comprobante(estado="emitido")
        await comprobante(estado="fallido")
        await comprobante(reclamado_at=AHORA - timedelta(minutes=1))
        reclamado_vencido = await comprobante(
            reclamado_at=AHORA - timedelta(minutes=10)
        )

        async with UnitOfWork(session_factory) as uow:
            pendientes = await uow.comprobantes.list_pendientes_vencidos(
                AHORA
            )
            assert {comprobante.id for comprobante in pendientes} == {
                sin_proximo,
                vencido,
                reclamado_vencido,
            }

    run(scenario())


def test_claim_atomico_con_token_y_vencimiento(session_factory) -> None:
    """Business rule: only one worker owns a receipt for five minutes (D4)."""
    data = _setup(session_factory)

    async def scenario() -> None:
        comprobante_id = await insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=await _cobro(data, session_factory),
            paciente_id=data["paciente_os_demo"].id,
            numero_interno=1,
        )
        token_uno = uuid.uuid4()

        async with UnitOfWork(session_factory) as uow:
            reclamado = await uow.comprobantes.reclamar(
                comprobante_id, token=token_uno, ahora=AHORA
            )
            assert reclamado is not None
            assert reclamado.claim_token == token_uno
            assert reclamado.reclamado_at == AHORA

        # A live claim blocks a second worker.
        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.comprobantes.reclamar(
                    comprobante_id,
                    token=uuid.uuid4(),
                    ahora=AHORA + timedelta(minutes=1),
                )
                is None
            )

        # Once the five-minute claim expires, another worker may take it.
        token_dos = uuid.uuid4()
        async with UnitOfWork(session_factory) as uow:
            retomado = await uow.comprobantes.reclamar(
                comprobante_id,
                token=token_dos,
                ahora=AHORA + timedelta(minutes=6),
            )
            assert retomado is not None
            assert retomado.claim_token == token_dos

        # Future retry and terminal states are not claimable.
        futuro = await insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=await _cobro(data, session_factory),
            paciente_id=data["paciente_os_demo"].id,
            numero_interno=2,
            proximo_intento=AHORA + timedelta(minutes=10),
        )
        emitido = await insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=await _cobro(data, session_factory),
            paciente_id=data["paciente_os_demo"].id,
            numero_interno=3,
            estado="emitido",
        )
        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.comprobantes.reclamar(
                    futuro, token=uuid.uuid4(), ahora=AHORA
                )
                is None
            )
            assert (
                await uow.comprobantes.reclamar(
                    emitido, token=uuid.uuid4(), ahora=AHORA
                )
                is None
            )
            assert (
                await uow.comprobantes.reclamar(
                    uuid.uuid4(), token=uuid.uuid4(), ahora=AHORA
                )
                is None
            )

    run(scenario())


def test_secuencias_interna_y_fiscal_por_consultorio_y_punto_venta(
    session_factory,
) -> None:
    """Expected: gapless counters, independent for each point of sale."""
    data = _setup(session_factory)
    consultorio_id = data["consultorio_id"]

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.secuencias_comprobantes.siguiente_interno(
                    consultorio_id, 1
                )
                == 1
            )
            assert (
                await uow.secuencias_comprobantes.siguiente_interno(
                    consultorio_id, 1
                )
                == 2
            )
            assert (
                await uow.secuencias_comprobantes.siguiente_fiscal(
                    consultorio_id, 1
                )
                == 1
            )
            assert (
                await uow.secuencias_comprobantes.siguiente_fiscal(
                    consultorio_id, 1
                )
                == 2
            )
            assert (
                await uow.secuencias_comprobantes.siguiente_interno(
                    consultorio_id, 2
                )
                == 1
            )

    run(scenario())


def test_liquidacion_con_items_activos(session_factory) -> None:
    """Expected: the settlement detail hides soft-deleted lines."""
    data = _setup(session_factory)

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_os_demo"].id
        profesional_id = data["profesional"].id
        creado_por = data["actores"]["administrador"].id
        prestacion = data["prestaciones"]["CONS"]

        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            creado_por=creado_por,
            estado="aceptado",
        )
        item_uno = await insertar_item_db(
            session_factory,
            presupuesto_id=presupuesto_id,
            prestacion_id=prestacion.id,
        )
        item_dos = await insertar_item_db(
            session_factory,
            presupuesto_id=presupuesto_id,
            prestacion_id=prestacion.id,
            cobertura_item="2500.00",
            copago_item="7500.00",
        )
        cobro_id = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="tratamiento",
            medio="efectivo",
            estado="aprobado",
            monto="20000.00",
            presupuesto_id=presupuesto_id,
        )
        liquidacion_id = await insertar_liquidacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            obra_social_id=data["obra_social_demo_id"],
            creado_por=creado_por,
        )
        await insertar_item_liquidacion_db(
            session_factory,
            liquidacion_id=liquidacion_id,
            item_presupuesto_id=item_uno,
            presupuesto_id=presupuesto_id,
            cobro_id=cobro_id,
            prestacion_id=prestacion.id,
            cobertura_item="6000.00",
        )
        borrado = await insertar_item_liquidacion_db(
            session_factory,
            liquidacion_id=liquidacion_id,
            item_presupuesto_id=item_dos,
            presupuesto_id=presupuesto_id,
            cobro_id=cobro_id,
            prestacion_id=prestacion.id,
            cobertura_item="2500.00",
        )
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE items_liquidacion "
                    "SET is_active = false, deleted_at = now() "
                    "WHERE id = :id"
                ),
                {"id": borrado},
            )

        async with UnitOfWork(session_factory) as uow:
            liquidacion, items = await uow.liquidaciones.get_con_items(
                liquidacion_id
            )
            assert liquidacion is not None
            assert liquidacion.id == liquidacion_id
            assert liquidacion.estado == "borrador"
            assert [item.item_presupuesto_id for item in items] == [item_uno]

            inexistente, vacios = await uow.liquidaciones.get_con_items(
                uuid.uuid4()
            )
            assert inexistente is None and vacios == []

    run(scenario())


def test_items_ya_liquidados(session_factory) -> None:
    """Expected: the duplicate guard only reports live settlement lines."""
    data = _setup(session_factory)

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_os_demo"].id
        profesional_id = data["profesional"].id
        creado_por = data["actores"]["administrador"].id
        prestacion = data["prestaciones"]["CONS"]

        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            creado_por=creado_por,
            estado="aceptado",
        )
        cobro_id = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="tratamiento",
            medio="efectivo",
            estado="aprobado",
            monto="30000.00",
            presupuesto_id=presupuesto_id,
        )
        liquidacion_id = await insertar_liquidacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            obra_social_id=data["obra_social_demo_id"],
            creado_por=creado_por,
        )

        items = [
            await insertar_item_db(
                session_factory,
                presupuesto_id=presupuesto_id,
                prestacion_id=prestacion.id,
            )
            for _ in range(3)
        ]
        liquidados = []
        for item_presupuesto_id in items:
            liquidados.append(
                await insertar_item_liquidacion_db(
                    session_factory,
                    liquidacion_id=liquidacion_id,
                    item_presupuesto_id=item_presupuesto_id,
                    presupuesto_id=presupuesto_id,
                    cobro_id=cobro_id,
                    prestacion_id=prestacion.id,
                )
            )
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE items_liquidacion "
                    "SET is_active = false, deleted_at = now() "
                    "WHERE id = :id"
                ),
                {"id": liquidados[2]},
            )

        async with UnitOfWork(session_factory) as uow:
            ya = await uow.items_liquidacion.ids_ya_liquidados(items)
            assert ya == {items[0], items[1]}
            assert await uow.items_liquidacion.ids_ya_liquidados([]) == set()
            # A budget line never settled is absent.
            libre = await insertar_item_db(
                session_factory,
                presupuesto_id=presupuesto_id,
                prestacion_id=prestacion.id,
            )
            assert await uow.items_liquidacion.ids_ya_liquidados(
                [libre]
            ) == set()

    run(scenario())


def test_envio_por_canal_y_unicidad(session_factory) -> None:
    """Expected: one send per receipt and channel, readable by the use case."""
    data = _setup(session_factory)

    async def scenario() -> None:
        comprobante_id = await insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=await _cobro(data, session_factory),
            paciente_id=data["paciente_os_demo"].id,
            numero_interno=1,
            estado="emitido",
        )
        envio_id = await insertar_envio_db(
            session_factory, comprobante_id=comprobante_id
        )

        async with UnitOfWork(session_factory) as uow:
            envio = await uow.comprobantes_envios.get_por_canal(
                comprobante_id, "whatsapp"
            )
            assert envio is not None
            assert envio.id == envio_id
            assert envio.estado == "registrado"
            assert (
                await uow.comprobantes_envios.get_por_canal(
                    comprobante_id, "email"
                )
                is None
            )

        with pytest.raises(DBAPIError) as exc_info:
            await insertar_envio_db(
                session_factory, comprobante_id=comprobante_id
            )
        assert sqlstate(exc_info.value) == "23505"

    run(scenario())
