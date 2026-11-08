"""C-13 repositories: live deposit, approved sum, register and row locking."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.repositories import CajaDiariaRepository
from app.infrastructure.uow import UnitOfWork
from tests.integration.caja_helpers import (
    FECHA_CAJA,
    insertar_caja_db,
    insertar_cobro_db,
    insertar_movimiento_db,
    setup_caja,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.presupuestos_helpers import insertar_presupuesto_db


def _setup(session_factory) -> dict[str, object]:
    return run(setup_caja(session_factory))


def test_sena_viva_por_turno_ignora_estados_resueltos(session_factory) -> None:
    """Expected: only `pendiente|aprobado|perdido` count as a live deposit."""
    data = _setup(session_factory)

    async def scenario() -> None:
        turno_id = data["turnos"]["propio"]
        rechazada = await insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_propio"].id,
            tipo="sena",
            medio="mercadopago",
            estado="rechazado",
            monto="8000.00",
            turno_id=turno_id,
        )
        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.cobros.get_sena_viva_por_turno(turno_id) is None
            )

        viva = await insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_propio"].id,
            tipo="sena",
            medio="mercadopago",
            estado="pendiente",
            monto="8000.00",
            turno_id=turno_id,
        )
        async with UnitOfWork(session_factory) as uow:
            encontrada = await uow.cobros.get_sena_viva_por_turno(turno_id)
            assert encontrada is not None
            assert encontrada.id == viva
            assert encontrada.id != rechazada

    run(scenario())


def test_suma_tratamientos_aprobados_por_presupuesto(session_factory) -> None:
    """Expected: rejected/pending payments and other budgets do not add up."""
    data = _setup(session_factory)

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_propio"].id
        profesional_id = data["profesional"].id
        creado_por = data["actores"]["odontologo"].id
        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            creado_por=creado_por,
            estado="aceptado",
        )
        otro_presupuesto = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            creado_por=creado_por,
            estado="aceptado",
        )
        for monto, estado, medio in (
            ("20000.00", "aprobado", "efectivo"),
            ("5000.00", "aprobado", "efectivo"),
            ("999.00", "rechazado", "efectivo"),
            ("777.00", "pendiente", "mercadopago"),
        ):
            await insertar_cobro_db(
                session_factory,
                consultorio_id=consultorio_id,
                paciente_id=paciente_id,
                tipo="tratamiento",
                medio=medio,
                estado=estado,
                monto=monto,
                presupuesto_id=presupuesto_id,
            )
        await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="tratamiento",
            medio="efectivo",
            estado="aprobado",
            monto="12345.00",
            presupuesto_id=otro_presupuesto,
        )

        async with UnitOfWork(session_factory) as uow:
            assert await uow.cobros.sumar_tratamientos_aprobados(
                presupuesto_id
            ) == Decimal("25000.00")
            assert await uow.cobros.sumar_tratamientos_aprobados(
                otro_presupuesto
            ) == Decimal("12345.00")

    run(scenario())


def test_caja_por_consultorio_y_fecha(session_factory) -> None:
    """Expected: one register per local day, NULL for a day never opened."""
    data = _setup(session_factory)

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            caja = await uow.cajas.get_por_consultorio_fecha(
                data["consultorio_id"], FECHA_CAJA
            )
            assert caja is not None
            assert caja.id == data["caja_id"]
            assert caja.estado == "abierta"
            assert caja.fecha == FECHA_CAJA

            inexistente = await uow.cajas.get_por_consultorio_fecha(
                data["consultorio_id"], date(2026, 11, 9)
            )
            assert inexistente is None

        otra_fecha = date(2026, 11, 5)
        otra_id = await insertar_caja_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            fecha=otra_fecha,
        )
        async with UnitOfWork(session_factory) as uow:
            encontrada = await uow.cajas.get_por_consultorio_fecha(
                data["consultorio_id"], otra_fecha
            )
            assert encontrada is not None
            assert encontrada.id == otra_id

    run(scenario())


def test_movimientos_por_caja(session_factory) -> None:
    """Expected: movements are scoped to their own register."""
    data = _setup(session_factory)

    async def scenario() -> None:
        otra_caja = await insertar_caja_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            fecha=date(2026, 11, 5),
        )
        ingreso = await insertar_movimiento_db(
            session_factory,
            caja_id=data["caja_id"],
            tipo="ingreso",
            monto="15000.00",
        )
        gasto = await insertar_movimiento_db(
            session_factory,
            caja_id=data["caja_id"],
            tipo="gasto",
            concepto="Insumos",
            monto="3500.00",
        )
        ajeno = await insertar_movimiento_db(
            session_factory,
            caja_id=otra_caja,
            tipo="deuda",
            monto="12000.00",
        )

        async with UnitOfWork(session_factory) as uow:
            movimientos = await uow.movimientos_caja.list_by_caja(
                data["caja_id"]
            )
            assert {movimiento.id for movimiento in movimientos} == {
                ingreso,
                gasto,
            }
            assert ajeno not in {movimiento.id for movimiento in movimientos}

    run(scenario())


def test_listado_de_cobros_con_filtros(session_factory) -> None:
    """Expected: consultorio scope plus declared filters, newest first."""
    data = _setup(session_factory)

    async def scenario() -> None:
        base = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
        primero = await insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_propio"].id,
            tipo="otro",
            medio="efectivo",
            estado="aprobado",
            monto="1000.00",
            fecha_operacion=date(2026, 11, 4),
        )
        segundo = await insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_propio"].id,
            tipo="otro",
            medio="mercadopago",
            estado="pendiente",
            monto="2000.00",
            fecha_operacion=date(2026, 11, 5),
        )
        # Touch `updated_at` so "newest first" is deterministic.
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE cobros SET created_at = :created_at WHERE id = :id"
                ),
                {"created_at": base, "id": primero},
            )
            await session.execute(
                text(
                    "UPDATE cobros SET created_at = :created_at WHERE id = :id"
                ),
                {"created_at": base, "id": segundo},
            )

        async with UnitOfWork(session_factory) as uow:
            todos = await uow.cobros.list_filtrado(data["consultorio_id"])
            assert {cobro.id for cobro in todos} == {primero, segundo}

            por_medio = await uow.cobros.list_filtrado(
                data["consultorio_id"], medio="mercadopago"
            )
            assert [cobro.id for cobro in por_medio] == [segundo]

            por_estado = await uow.cobros.list_filtrado(
                data["consultorio_id"], estado="aprobado"
            )
            assert [cobro.id for cobro in por_estado] == [primero]

            por_fecha = await uow.cobros.list_filtrado(
                data["consultorio_id"],
                fecha_desde=date(2026, 11, 5),
                fecha_hasta=date(2026, 11, 5),
            )
            assert [cobro.id for cobro in por_fecha] == [segundo]

    run(scenario())


def test_cierre_bloquea_la_fila_con_for_update(session_factory) -> None:
    """Business rule: a concurrent closing attempt cannot read the row locked."""
    data = _setup(session_factory)
    consultorio_id = data["consultorio_id"]

    async def scenario() -> None:
        async with session_factory() as primera:
            async with primera.begin():
                caja = await CajaDiariaRepository(
                    primera
                ).get_por_consultorio_fecha(
                    consultorio_id, FECHA_CAJA, for_update=True
                )
                assert caja is not None

                async with session_factory() as segunda:
                    await segunda.execute(
                        text("SET LOCAL lock_timeout = '150ms'")
                    )
                    with pytest.raises(DBAPIError) as exc_info:
                        await CajaDiariaRepository(
                            segunda
                        ).get_por_consultorio_fecha(
                            consultorio_id, FECHA_CAJA, for_update=True
                        )
                    assert sqlstate(exc_info.value) == "55P03"

    run(scenario())
