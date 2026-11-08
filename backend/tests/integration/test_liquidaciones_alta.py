"""C-14 group 9.1: settlement creation, selection and traceability (D9)."""

import uuid
from datetime import date

from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.helpers import run
from tests.integration.liquidaciones_helpers import (
    crear_escenario,
    crear_paciente_os,
    contar_liquidaciones,
    leer_liquidacion,
    post_liquidacion,
    setup_liquidaciones,
)
from tests.integration.presupuestos_helpers import crear_convenio
from tests.integration.fiscal_helpers import (
    insertar_item_liquidacion_db,
    insertar_liquidacion_db,
)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def test_alta_con_item_trazable_y_total_correcto(
    api_client, session_factory
) -> None:
    """Expected: 201 draft with one line traced to budget/item/payment."""
    data = _setup(session_factory)
    escenario = run(crear_escenario(session_factory, data))

    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "borrador"
    assert cuerpo["total_cobertura"] == "6000.00"
    assert cuerpo["cantidad_practicas"] == 1
    assert cuerpo["cerrada_por"] is None and cuerpo["cerrada_at"] is None
    assert len(cuerpo["items"]) == 1

    item = cuerpo["items"][0]
    assert item["item_presupuesto_id"] == str(escenario["item_id"])
    assert item["presupuesto_id"] == str(escenario["presupuesto_id"])
    assert item["cobro_id"] == str(escenario["cobro_id"])
    assert item["prestacion_id"] == str(escenario["prestacion_id"])
    assert item["prestacion_codigo"] == "CONS"
    assert item["cantidad"] == 1
    assert item["cobertura_item"] == "6000.00"

    liquidacion = run(
        leer_liquidacion(session_factory, uuid.UUID(cuerpo["id"]))
    )
    assert liquidacion is not None
    assert str(liquidacion.total_cobertura) == "6000.00"
    assert liquidacion.cantidad_practicas == 1


def test_periodo_sin_practicas_devuelve_422_sin_cabecera(
    api_client, session_factory
) -> None:
    """Business error: no approved treatment payment means no settlement."""
    data = _setup(session_factory)
    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 422, respuesta.text
    assert run(contar_liquidaciones(session_factory)) == 0


def test_pagos_parciales_no_duplican_la_practica(
    api_client, session_factory
) -> None:
    """Expected: two payments of the same budget yield one settled line."""
    data = _setup(session_factory)
    escenario = run(crear_escenario(session_factory, data))
    run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="tratamiento",
            medio="efectivo",
            estado="aprobado",
            monto="3000.00",
            presupuesto_id=escenario["presupuesto_id"],
            fecha_operacion=date(2026, 11, 6),
        )
    )

    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert len(cuerpo["items"]) == 1
    assert cuerpo["total_cobertura"] == "6000.00"
    assert cuerpo["cantidad_practicas"] == 1


def test_item_ya_liquidado_no_se_incluye_otra_vez(
    api_client, session_factory
) -> None:
    """Business rule: a live settlement line excludes the budget line (D9)."""
    data = _setup(session_factory)
    ya_liquidado = run(crear_escenario(session_factory, data))
    nuevo = run(crear_escenario(session_factory, data))
    otra_os = run(
        crear_convenio(
            session_factory,
            data["consultorio_id"],
            nombre=f"OS Paralela {uuid.uuid4().hex[:5]}",
            reglas_cobertura={
                "cobertura_porcentaje": 60,
                "prestaciones_cubiertas": ["CONS"],
            },
        )
    )
    liquidacion_paralela = run(
        insertar_liquidacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            obra_social_id=otra_os.id,
            creado_por=data["actores"]["administrador"].id,
            desde=data["desde"],
            hasta=data["hasta"],
        )
    )
    run(
        insertar_item_liquidacion_db(
            session_factory,
            liquidacion_id=liquidacion_paralela,
            item_presupuesto_id=ya_liquidado["item_id"],
            presupuesto_id=ya_liquidado["presupuesto_id"],
            cobro_id=ya_liquidado["cobro_id"],
            prestacion_id=ya_liquidado["prestacion_id"],
        )
    )

    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    items = respuesta.json()["items"]
    assert [item["item_presupuesto_id"] for item in items] == [
        str(nuevo["item_id"])
    ]
    assert respuesta.json()["total_cobertura"] == "6000.00"


def test_items_sin_cobertura_o_de_otra_obra_social_se_excluyen(
    api_client, session_factory
) -> None:
    """Business rule: only covered lines of the settlement's insurance enter."""
    data = _setup(session_factory)
    cubierto = run(crear_escenario(session_factory, data))
    run(
        crear_escenario(
            session_factory,
            data,
            cobertura_item="0.00",
            copago_item="10000.00",
        )
    )

    otra_os = run(
        crear_convenio(
            session_factory,
            data["consultorio_id"],
            nombre=f"OS Ajena {uuid.uuid4().hex[:5]}",
            reglas_cobertura={
                "cobertura_porcentaje": 60,
                "prestaciones_cubiertas": ["CONS"],
            },
        )
    )
    paciente_ajeno = run(
        crear_paciente_os(
            session_factory, data, obra_social_id=otra_os.id
        )
    )
    run(
        crear_escenario(
            session_factory, data, paciente_id=paciente_ajeno.id
        )
    )

    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    items = respuesta.json()["items"]
    assert [item["item_presupuesto_id"] for item in items] == [
        str(cubierto["item_id"])
    ]


def test_presupuesto_sin_cobro_aprobado_en_el_periodo_se_excluye(
    api_client, session_factory
) -> None:
    """Business rule: a budget without an approved payment in the period waits."""
    data = _setup(session_factory)
    valido = run(crear_escenario(session_factory, data))
    run(
        crear_escenario(
            session_factory, data, con_cobro=False
        )
    )
    run(
        crear_escenario(
            session_factory,
            data,
            fecha_cobro=date(2026, 12, 5),
        )
    )
    run(
        crear_escenario(
            session_factory, data, estado="borrador"
        )
    )

    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    items = respuesta.json()["items"]
    assert [item["item_presupuesto_id"] for item in items] == [
        str(valido["item_id"])
    ]
    assert respuesta.json()["total_cobertura"] == "6000.00"


def test_cantidad_de_practicas_cuenta_lineas_y_suma_coberturas(
    api_client, session_factory
) -> None:
    """Expected: `cantidad_practicas` is COUNT(*) and the total is SUM()."""
    data = _setup(session_factory)
    run(
        crear_escenario(
            session_factory,
            data,
            cantidad=2,
            cobertura_item="12000.00",
            copago_item="8000.00",
        )
    )
    run(
        crear_escenario(
            session_factory,
            data,
            prestacion="OBT",
            cobertura_item="15000.00",
            copago_item="10000.00",
        )
    )

    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["cantidad_practicas"] == 2
    assert cuerpo["total_cobertura"] == "27000.00"
    codigos = sorted(item["prestacion_codigo"] for item in cuerpo["items"])
    assert codigos == ["CONS", "OBT"]
