"""C-15 settlement report (tasks 5.3/5.4, design D8/D9/D13).

One closed settlement (60000.00, 3 practices: OBT×2 + CONS) and one draft
(20000.00, 1 practice: LIM) of OS Demo. The closed period crosses October and
November; a soft-deleted line must never add to the aggregate.
"""

from tests.integration.helpers import run
from tests.integration.reportes_helpers import setup_liquidaciones_reporte
from tests.integration.recursos_helpers import bearer

from decimal import Decimal

NOVIEMBRE = {"desde": "2026-11-01", "hasta": "2026-11-30"}


def _get(api_client, data, actor: str = "administrador", **params):
    return api_client.get(
        "/reportes/liquidaciones",
        params={**NOVIEMBRE, **params},
        headers=bearer(data["actores"][actor]),
    )


def test_agregados_por_estado_obra_social_y_prestacion(
    api_client, session_factory
) -> None:
    data = run(setup_liquidaciones_reporte(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["cantidad_liquidaciones"] == 2
    assert cuerpo["total_cobertura"] == "80000.00"
    assert cuerpo["cantidad_practicas"] == 4
    assert cuerpo["total_detalle"] == 2
    assert cuerpo["detalle_truncado"] is False
    assert len(cuerpo["detalle"]) == 2

    por_estado = {
        fila["estado"]: fila for fila in cuerpo["por_estado"]
    }
    assert set(por_estado) == {"cerrada", "borrador"}
    assert por_estado["cerrada"]["obra_social_id"] == str(
        data["obra_social_demo_id"]
    )
    assert por_estado["cerrada"]["obra_social_nombre"] == "OS Demo"
    assert por_estado["cerrada"]["cantidad_liquidaciones"] == 1
    assert por_estado["cerrada"]["total_cobertura"] == "60000.00"
    assert por_estado["cerrada"]["cantidad_practicas"] == 3
    assert por_estado["borrador"]["cantidad_liquidaciones"] == 1
    assert por_estado["borrador"]["total_cobertura"] == "20000.00"
    assert por_estado["borrador"]["cantidad_practicas"] == 1

    assert len(cuerpo["por_obra_social"]) == 1
    obra = cuerpo["por_obra_social"][0]
    assert obra["obra_social_id"] == str(data["obra_social_demo_id"])
    assert obra["obra_social_nombre"] == "OS Demo"
    assert obra["cantidad_liquidaciones"] == 2
    assert obra["total_cobertura"] == "80000.00"
    assert obra["cantidad_practicas"] == 4

    por_prestacion = {
        fila["prestacion_codigo"]: fila
        for fila in cuerpo["por_prestacion"]
    }
    assert por_prestacion["OBT"]["cantidad"] == 2
    assert por_prestacion["OBT"]["cobertura"] == "40000.00"
    assert por_prestacion["CONS"]["cantidad"] == 1
    assert por_prestacion["CONS"]["cobertura"] == "20000.00"
    assert por_prestacion["LIM"]["cantidad"] == 1
    assert por_prestacion["LIM"]["cobertura"] == "20000.00"
    assert sum(
        Decimal(fila["cobertura"]) for fila in cuerpo["por_prestacion"]
    ) == Decimal(cuerpo["total_cobertura"])


def test_cruce_de_periodo_octubre_noviembre(
    api_client, session_factory
) -> None:
    data = run(setup_liquidaciones_reporte(session_factory))
    octubre = _get(
        api_client,
        data,
        desde="2026-10-01",
        hasta="2026-10-31",
    )
    assert octubre.status_code == 200, octubre.text
    cuerpo = octubre.json()

    assert cuerpo["cantidad_liquidaciones"] == 1
    assert cuerpo["total_cobertura"] == "60000.00"
    assert cuerpo["cantidad_practicas"] == 3
    assert cuerpo["detalle"][0]["liquidacion_id"] == str(
        data["liquidacion_cerrada"]
    )
    assert cuerpo["detalle"][0]["desde"] == "2026-10-20"
    assert cuerpo["detalle"][0]["hasta"] == "2026-11-05"


def test_rango_vacio_devuelve_ceros_sin_listas(
    api_client, session_factory
) -> None:
    data = run(setup_liquidaciones_reporte(session_factory))
    respuesta = _get(
        api_client,
        data,
        desde="2027-01-01",
        hasta="2027-01-31",
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["cantidad_liquidaciones"] == 0
    assert cuerpo["total_cobertura"] == "0.00"
    assert cuerpo["cantidad_practicas"] == 0
    assert cuerpo["por_estado"] == []
    assert cuerpo["por_obra_social"] == []
    assert cuerpo["por_prestacion"] == []
    assert cuerpo["detalle"] == []
    assert cuerpo["total_detalle"] == 0


def test_obra_social_de_otro_consultorio_devuelve_404(
    api_client, session_factory
) -> None:
    data = run(setup_liquidaciones_reporte(session_factory))
    respuesta = _get(
        api_client,
        data,
        obra_social_id=str(data["obra_social_ajena_id"]),
    )
    assert respuesta.status_code == 404, respuesta.text


def test_filtro_por_estado_excluye_el_borrador(
    api_client, session_factory
) -> None:
    data = run(setup_liquidaciones_reporte(session_factory))
    respuesta = _get(api_client, data, estado="cerrada")
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["cantidad_liquidaciones"] == 1
    assert cuerpo["total_cobertura"] == "60000.00"
    assert cuerpo["cantidad_practicas"] == 3
    assert {fila["estado"] for fila in cuerpo["por_estado"]} == {"cerrada"}
    por_prestacion = {
        fila["prestacion_codigo"]: fila
        for fila in cuerpo["por_prestacion"]
    }
    assert set(por_prestacion) == {"OBT", "CONS"}
    assert por_prestacion["OBT"]["cantidad"] == 2
    assert por_prestacion["CONS"]["cantidad"] == 1


def test_item_con_baja_logica_no_suma(
    api_client, session_factory
) -> None:
    data = run(setup_liquidaciones_reporte(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    por_prestacion = {
        fila["prestacion_codigo"]: fila
        for fila in cuerpo["por_prestacion"]
    }
    # The deleted OBT line had cantidad 5 and cobertura 99999.00.
    assert por_prestacion["OBT"]["cantidad"] == 2
    assert por_prestacion["OBT"]["cobertura"] == "40000.00"
    assert cuerpo["total_cobertura"] == "80000.00"
    assert cuerpo["cantidad_practicas"] == 4
