"""C-15 report aggregates against a deterministic PostgreSQL dataset.

Every expected value is written by hand from the fixture description in
`reportes_helpers.setup_reportes`; none is recomputed with the SQL under test.
`EXPLAIN` was run manually against the same dataset (task 3.2) and the formulas
are documented in `ConsultaReportesRepository`.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.reportes import (
    ocupacion_porcentaje,
    tasa_ausentismo,
    tasa_no_asistencia,
)
from app.infrastructure.uow import UnitOfWork
from tests.integration.helpers import run
from tests.integration.reportes_helpers import setup_reportes

DESDE = date(2026, 11, 9)
HASTA = date(2026, 11, 13)
DESDE_UTC = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
HASTA_UTC = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)


def test_agenda_por_estado_recurso_y_minutos(session_factory) -> None:
    """Expected: 11 appointments; 1200/180 available and 360/60 occupied."""
    data = run(setup_reportes(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        principal = data["profesional"]
        segundo = data["profesional_dos"]
        sillon_a = data["sillon_a"]
        sillon_b = data["sillon_b"]

        async with UnitOfWork(session_factory) as uow:
            por_estado = await uow.reportes.agenda_por_estado(
                consultorio_id,
                desde=DESDE_UTC,
                hasta=HASTA_UTC,
            )
            assert por_estado == {
                "atendido": 5,
                "cancelado": 2,
                "ausente": 1,
                "reservado": 1,
                "confirmado": 1,
                "en_sala": 1,
            }
            assert sum(por_estado.values()) == 11

            por_profesional = await uow.reportes.agenda_por_profesional(
                consultorio_id,
                desde=DESDE_UTC,
                hasta=HASTA_UTC,
            )
            assert {
                fila["profesional_id"]: fila["cantidad"]
                for fila in por_profesional
            } == {principal.id: 9, segundo.id: 2}
            assert sum(
                fila["cantidad"] for fila in por_profesional
            ) == 11

            por_sillon = await uow.reportes.agenda_por_sillon(
                consultorio_id,
                desde=DESDE_UTC,
                hasta=HASTA_UTC,
            )
            assert {
                fila["sillon_id"]: fila["cantidad"] for fila in por_sillon
            } == {sillon_a.id: 9, sillon_b.id: 2}
            assert sum(fila["cantidad"] for fila in por_sillon) == 11

            disponibles = (
                await uow.reportes.minutos_disponibles_por_profesional(
                    consultorio_id, desde=DESDE, hasta=HASTA
                )
            )
            assert disponibles == {principal.id: 1200, segundo.id: 180}

            ocupados = await uow.reportes.minutos_ocupados_por_profesional(
                consultorio_id, desde=DESDE_UTC, hasta=HASTA_UTC
            )
            assert ocupados == {principal.id: 360, segundo.id: 60}

            sobreturnos = (
                await uow.reportes.minutos_sobreturno_por_profesional(
                    consultorio_id, desde=DESDE_UTC, hasta=HASTA_UTC
                )
            )
            assert sobreturnos == {principal.id: 60}

            solo_segundo = (
                await uow.reportes.minutos_ocupados_por_profesional(
                    consultorio_id,
                    desde=DESDE_UTC,
                    hasta=HASTA_UTC,
                    profesional_id=segundo.id,
                )
            )
            assert solo_segundo == {segundo.id: 60}

            assert ocupacion_porcentaje(
                ocupados[principal.id], disponibles[principal.id]
            ) == Decimal("30.00")
            assert ocupacion_porcentaje(
                ocupados[segundo.id], disponibles[segundo.id]
            ) == Decimal("33.33")

    run(scenario())


def test_ausentismo_conteos_y_tasas(session_factory) -> None:
    """Expected: 5 attended + 2 cancelled + 1 absent; 3 still active."""
    data = run(setup_reportes(session_factory))

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            resumen = await uow.reportes.resumen_ausentismo(
                data["consultorio_id"],
                desde=DESDE_UTC,
                hasta=HASTA_UTC,
            )
            assert resumen == {
                "atendidos": 5,
                "cancelados": 2,
                "ausentes": 1,
                "turnos_activos": 3,
            }
            assert tasa_ausentismo(
                resumen["atendidos"],
                resumen["cancelados"],
                resumen["ausentes"],
            ) == Decimal("0.38")
            assert tasa_no_asistencia(
                resumen["atendidos"],
                resumen["cancelados"],
                resumen["ausentes"],
            ) == Decimal("0.13")

            solo_segundo = await uow.reportes.resumen_ausentismo(
                data["consultorio_id"],
                desde=DESDE_UTC,
                hasta=HASTA_UTC,
                profesional_id=data["profesional_dos"].id,
            )
            assert solo_segundo == {
                "atendidos": 1,
                "cancelados": 1,
                "ausentes": 0,
                "turnos_activos": 0,
            }

    run(scenario())


def test_caja_por_medio_estado_movimientos_y_arqueos(
    session_factory,
) -> None:
    """Expected: 15000 cash + 8000 MP approved; expenses/debts reported apart."""
    data = run(setup_reportes(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        desde = data["caja_desde"]
        hasta = data["caja_hasta"]

        async with UnitOfWork(session_factory) as uow:
            por_medio = await uow.reportes.totales_aprobados_por_medio(
                consultorio_id, desde=desde, hasta=hasta
            )
            assert por_medio == {
                "efectivo": Decimal("15000.00"),
                "mercadopago": Decimal("8000.00"),
            }

            por_estado = await uow.reportes.conteo_cobros_por_estado(
                consultorio_id, desde=desde, hasta=hasta
            )
            assert por_estado == {
                "aprobado": 3,
                "pendiente": 1,
                "reembolsado": 1,
                "rechazado": 1,
                "perdido": 1,
            }

            movimientos = await uow.reportes.movimientos_por_tipo(
                consultorio_id, desde=desde, hasta=hasta
            )
            assert {
                (fila["tipo"], fila["medio"]): (
                    fila["cantidad"],
                    fila["total"],
                )
                for fila in movimientos
            } == {
                ("ingreso", "efectivo"): (1, Decimal("15000.00")),
                ("gasto", "efectivo"): (1, Decimal("3500.00")),
                ("deuda", "efectivo"): (1, Decimal("12000.00")),
                ("ingreso", "mercadopago"): (1, Decimal("8000.00")),
            }

            cajas = await uow.reportes.cajas_del_rango(
                consultorio_id, desde=desde, hasta=hasta
            )
            assert [caja.id for caja in cajas] == [
                data["caja_cerrada"],
                data["caja_abierta"],
            ]
            cerrada = cajas[0]
            assert cerrada.estado == "cerrada"
            assert cerrada.diferencia == Decimal("0.00")
            abierta = cajas[1]
            assert abierta.estado == "abierta"
            assert abierta.monto_sistema_efectivo is None

    run(scenario())


def test_liquidaciones_cruce_periodo_y_practicas(session_factory) -> None:
    """Expected: 2 headers (60000/3 + 20000/1), one soft-deleted line ignored."""
    data = run(setup_reportes(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        desde = data["caja_desde"]
        hasta = data["caja_hasta"]
        os_demo = data["obra_social_demo_id"]

        async with UnitOfWork(session_factory) as uow:
            cabeceras = await uow.reportes.liquidaciones_del_periodo(
                consultorio_id, desde=desde, hasta=hasta
            )
            assert {cabecera.id for cabecera in cabeceras} == {
                data["liquidacion_cerrada"],
                data["liquidacion_borrador"],
            }
            # October 20 – November 5 crosses the November range.
            cerrada = next(
                cabecera
                for cabecera in cabeceras
                if cabecera.id == data["liquidacion_cerrada"]
            )
            assert cerrada.desde == date(2026, 10, 20)
            assert cerrada.hasta == date(2026, 11, 5)

            agregados = (
                await uow.reportes.liquidaciones_por_obra_estado(
                    consultorio_id, desde=desde, hasta=hasta
                )
            )
            por_estado = {
                (fila["obra_social_id"], fila["estado"]): fila
                for fila in agregados
            }
            assert set(por_estado) == {
                (os_demo, "cerrada"),
                (os_demo, "borrador"),
            }
            cerrada_agregada = por_estado[(os_demo, "cerrada")]
            assert cerrada_agregada["cantidad_liquidaciones"] == 1
            assert cerrada_agregada["total_cobertura"] == Decimal(
                "60000.00"
            )
            assert cerrada_agregada["cantidad_practicas"] == 3
            borrador = por_estado[(os_demo, "borrador")]
            assert borrador["cantidad_liquidaciones"] == 1
            assert borrador["total_cobertura"] == Decimal("20000.00")
            assert borrador["cantidad_practicas"] == 1

            assert sum(
                fila["total_cobertura"] for fila in agregados
            ) == Decimal("80000.00")
            assert sum(
                fila["cantidad_practicas"] for fila in agregados
            ) == 4

            practicas = await uow.reportes.practicas_por_prestacion(
                consultorio_id, desde=desde, hasta=hasta
            )
            por_prestacion = {
                fila["prestacion_codigo"]: fila for fila in practicas
            }
            assert set(por_prestacion) == {"OBT", "CONS"}
            assert por_prestacion["OBT"]["cantidad"] == 3
            assert por_prestacion["OBT"]["cobertura"] == Decimal(
                "60000.00"
            )
            assert por_prestacion["CONS"]["cantidad"] == 1
            assert por_prestacion["CONS"]["cobertura"] == Decimal(
                "20000.00"
            )
            # The lines and the headers agree: 60000 + 20000 = 80000.
            assert sum(
                fila["cobertura"] for fila in practicas
            ) == Decimal("80000.00")

            sin_cruce = await uow.reportes.liquidaciones_del_periodo(
                consultorio_id,
                desde=date(2027, 1, 1),
                hasta=date(2027, 1, 31),
            )
            assert sin_cruce == []

    run(scenario())
