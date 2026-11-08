"""C-15 report boundaries (tasks 6.1/6.2, design D8/D13).

The detail is capped but the totals are computed over the whole range; the
order is stable (`inicio, id`) and every undeclared filter is rejected.
"""

from tests.integration.helpers import run
from tests.integration.reportes_helpers import (
    setup_bordes_reporte,
    setup_orden_reporte,
)
from tests.integration.recursos_helpers import bearer

ENERO_A_MARZO = {"desde": "2026-01-01", "hasta": "2026-03-01"}


def _get(api_client, data, path: str, actor: str = "administrador", **params):
    return api_client.get(
        path,
        params=params,
        headers=bearer(data["actores"][actor]),
    )


def test_limite_500_sobre_1200_filas_con_totales_completos(
    api_client, session_factory
) -> None:
    data = run(setup_bordes_reporte(session_factory))

    agenda = _get(
        api_client, data, "/reportes/agenda", **ENERO_A_MARZO, limite=500
    )
    assert agenda.status_code == 200, agenda.text
    cuerpo = agenda.json()
    assert cuerpo["total_turnos"] == 1200
    assert cuerpo["por_estado"]["atendido"] == 1200
    assert cuerpo["total_detalle"] == 1200
    assert cuerpo["detalle_truncado"] is True
    assert len(cuerpo["detalle"]) == 500

    ausentismo = _get(
        api_client,
        data,
        "/reportes/ausentismo",
        **ENERO_A_MARZO,
        limite=500,
    )
    assert ausentismo.status_code == 200, ausentismo.text
    cuerpo_ausentismo = ausentismo.json()
    assert cuerpo_ausentismo["atendidos"] == 1200
    assert cuerpo_ausentismo["cancelados"] == 0
    assert cuerpo_ausentismo["ausentes"] == 0
    assert cuerpo_ausentismo["tasa_ausentismo"] == "0.00"
    assert cuerpo_ausentismo["total_detalle"] == 1200
    assert cuerpo_ausentismo["detalle_truncado"] is True
    assert len(cuerpo_ausentismo["detalle"]) == 500

    completo = _get(
        api_client, data, "/reportes/agenda", **ENERO_A_MARZO, limite=1000
    )
    assert completo.status_code == 200
    assert len(completo.json()["detalle"]) == 1000
    assert completo.json()["total_detalle"] == 1200


def test_limite_y_fechas_invalidas_devuelven_422(
    api_client, session_factory
) -> None:
    data = run(setup_bordes_reporte(session_factory))

    for limite in (0, 1001):
        respuesta = _get(
            api_client,
            data,
            "/reportes/agenda",
            **ENERO_A_MARZO,
            limite=limite,
        )
        assert respuesta.status_code == 422, (limite, respuesta.text)

    sin_desde = _get(
        api_client, data, "/reportes/agenda", hasta="2026-01-31"
    )
    assert sin_desde.status_code == 422

    invertido = _get(
        api_client,
        data,
        "/reportes/agenda",
        desde="2026-01-31",
        hasta="2026-01-01",
    )
    assert invertido.status_code == 422


def test_filtros_no_declarados_devuelven_422_en_los_cuatro(
    api_client, session_factory
) -> None:
    data = run(setup_bordes_reporte(session_factory))

    for path in (
        "/reportes/agenda",
        "/reportes/ausentismo",
        "/reportes/caja",
        "/reportes/liquidaciones",
    ):
        respuesta = _get(
            api_client,
            data,
            path,
            **ENERO_A_MARZO,
            filtro_inventado="x",
        )
        assert respuesta.status_code == 422, (path, respuesta.text)
        assert "Unexpected query parameters" in respuesta.text


def test_orden_estable_por_inicio_e_id(api_client, session_factory) -> None:
    data = run(setup_orden_reporte(session_factory))
    params = {"desde": "2026-11-09", "hasta": "2026-11-09"}

    primera = _get(api_client, data, "/reportes/agenda", **params)
    segunda = _get(api_client, data, "/reportes/agenda", **params)
    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text

    detalle = primera.json()["detalle"]
    assert len(detalle) == 2
    assert [fila["inicio"] for fila in detalle] == [
        "2026-11-09T09:00:00-03:00",
        "2026-11-09T09:00:00-03:00",
    ]
    claves = [(fila["inicio"], fila["turno_id"]) for fila in detalle]
    assert claves == sorted(claves)
    assert [
        fila["turno_id"] for fila in segunda.json()["detalle"]
    ] == [fila["turno_id"] for fila in detalle]


def test_metadatos_comunes_de_la_consulta(
    api_client, session_factory
) -> None:
    data = run(setup_bordes_reporte(session_factory))
    respuesta = _get(
        api_client, data, "/reportes/agenda", **ENERO_A_MARZO, limite=10
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["zona_horaria"] == "UTC-3"
    assert cuerpo["desde"] == "2026-01-01"
    assert cuerpo["hasta"] == "2026-03-01"
    assert cuerpo["generado_en"].endswith("-03:00")
    assert cuerpo["filtros"]["limite"] == 10
    assert cuerpo["filtros"]["profesional_id"] is None
