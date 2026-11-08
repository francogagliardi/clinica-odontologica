"""C-14 group 9.3: coherent, non-overlapping settlement periods (D9)."""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import DBAPIError

from tests.integration.fiscal_helpers import insertar_liquidacion_db
from tests.integration.helpers import run, sqlstate
from tests.integration.liquidaciones_helpers import (
    contar_liquidaciones,
    crear_escenario,
    post_liquidacion,
    setup_liquidaciones,
)
from tests.integration.presupuestos_helpers import desactivar_convenio


def _setup(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def test_periodo_de_un_solo_dia_es_valido(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    dia = date(2026, 11, 4)
    run(crear_escenario(session_factory, data, fecha_cobro=dia))

    respuesta = post_liquidacion(api_client, data, desde=dia, hasta=dia)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["desde"] == "2026-11-04"
    assert respuesta.json()["hasta"] == "2026-11-04"


def test_fechas_invertidas_devuelve_422_sin_cabecera(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    run(crear_escenario(session_factory, data))

    respuesta = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 11, 10),
        hasta=date(2026, 11, 1),
    )
    assert respuesta.status_code == 422, respuesta.text
    assert run(contar_liquidaciones(session_factory)) == 0


def test_solapamiento_devuelve_409(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    run(crear_escenario(session_factory, data))
    primero = post_liquidacion(api_client, data)
    assert primero.status_code == 201, primero.text

    segundo = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 11, 15),
        hasta=date(2026, 12, 5),
    )
    assert segundo.status_code == 409, segundo.text
    assert run(contar_liquidaciones(session_factory)) == 1


def test_solapamiento_por_sql_directo_falla_con_23p01(
    session_factory,
) -> None:
    data = _setup(session_factory)
    run(
        insertar_liquidacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            obra_social_id=data["obra_social_demo_id"],
            creado_por=data["actores"]["administrador"].id,
            desde=date(2026, 11, 1),
            hasta=date(2026, 11, 30),
        )
    )

    async def scenario() -> str | None:
        try:
            await insertar_liquidacion_db(
                session_factory,
                consultorio_id=data["consultorio_id"],
                obra_social_id=data["obra_social_demo_id"],
                creado_por=data["actores"]["administrador"].id,
                desde=date(2026, 11, 30),
                hasta=date(2026, 12, 15),
            )
        except DBAPIError as error:
            return sqlstate(error)
        return None

    assert run(scenario()) == "23P01"


def test_periodos_contiguos_se_aceptan(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    run(
        crear_escenario(
            session_factory, data, fecha_cobro=date(2026, 11, 30)
        )
    )
    primero = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 11, 1),
        hasta=date(2026, 11, 30),
    )
    assert primero.status_code == 201, primero.text

    run(
        crear_escenario(
            session_factory, data, fecha_cobro=date(2026, 12, 1)
        )
    )
    segundo = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 31),
    )
    assert segundo.status_code == 201, segundo.text
    assert run(contar_liquidaciones(session_factory)) == 2


def test_obra_social_inexistente_o_inactiva_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    run(crear_escenario(session_factory, data))
    inexistente = post_liquidacion(
        api_client, data, obra_social_id=uuid.uuid4()
    )
    assert inexistente.status_code == 404, inexistente.text

    run(
        desactivar_convenio(
            session_factory, data["obra_social_demo_id"]
        )
    )
    inactiva = post_liquidacion(api_client, data)
    assert inactiva.status_code == 404, inactiva.text
    assert run(contar_liquidaciones(session_factory)) == 0
