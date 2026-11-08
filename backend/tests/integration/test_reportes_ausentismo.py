"""C-15 absence report (tasks 4.3/4.4, design D8/D9/D13).

Six attended, two cancelled and two absent appointments yield the 0.40 / 0.20
rates of the spec; the five active appointments stay outside the rates.
"""

from datetime import date

from tests.integration.helpers import run
from tests.integration.reportes_helpers import setup_ausentismo_reporte
from tests.integration.recursos_helpers import bearer

DESDE = date(2026, 11, 9)
HASTA = date(2026, 11, 9)
PARAMS = {"desde": DESDE.isoformat(), "hasta": HASTA.isoformat()}


def _get(api_client, data, actor: str = "administrador", **params):
    return api_client.get(
        "/reportes/ausentismo",
        params={**PARAMS, **params},
        headers=bearer(data["actores"][actor]),
    )


def test_tasas_sobre_turnos_cerrados_y_activos_aparte(
    api_client, session_factory
) -> None:
    data = run(setup_ausentismo_reporte(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["atendidos"] == 6
    assert cuerpo["cancelados"] == 2
    assert cuerpo["ausentes"] == 2
    assert cuerpo["turnos_activos"] == 5
    assert cuerpo["tasa_ausentismo"] == "0.40"
    assert cuerpo["tasa_no_asistencia"] == "0.20"
    assert cuerpo["sin_cierres"] is False

    assert cuerpo["total_detalle"] == 10
    assert cuerpo["detalle_truncado"] is False
    assert len(cuerpo["detalle"]) == 10
    assert {
        fila["estado"] for fila in cuerpo["detalle"]
    } == {"atendido", "cancelado", "ausente"}

    por_profesional = {
        fila["profesional_id"]: fila
        for fila in cuerpo["por_profesional"]
    }
    propio = por_profesional[str(data["profesional"].id)]
    assert propio == {
        "profesional_id": str(data["profesional"].id),
        "atendidos": 3,
        "cancelados": 1,
        "ausentes": 1,
        "turnos_activos": 3,
        "tasa_ausentismo": "0.40",
        "tasa_no_asistencia": "0.20",
        "sin_cierres": False,
    }
    ajeno = por_profesional[str(data["profesional_dos"].id)]
    assert ajeno["atendidos"] == 3
    assert ajeno["cancelados"] == 1
    assert ajeno["ausentes"] == 1
    assert ajeno["turnos_activos"] == 2


def test_rango_sin_cierres_no_divide_por_cero(
    api_client, session_factory
) -> None:
    data = run(setup_ausentismo_reporte(session_factory))
    respuesta = _get(
        api_client,
        data,
        desde="2026-12-01",
        hasta="2026-12-02",
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["atendidos"] == 0
    assert cuerpo["cancelados"] == 0
    assert cuerpo["ausentes"] == 0
    assert cuerpo["turnos_activos"] == 0
    assert cuerpo["tasa_ausentismo"] == "0.00"
    assert cuerpo["tasa_no_asistencia"] == "0.00"
    assert cuerpo["sin_cierres"] is True
    assert cuerpo["total_detalle"] == 0
    assert cuerpo["detalle"] == []
    assert cuerpo["por_profesional"] == []


def test_detalle_con_identidad_y_fecha_local(
    api_client, session_factory
) -> None:
    data = run(setup_ausentismo_reporte(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    ausente = next(
        fila
        for fila in cuerpo["detalle"]
        if fila["turno_id"] == str(data["turnos"]["p1_ausente"])
    )
    assert ausente["paciente_id"] == str(data["paciente"].id)
    assert ausente["profesional_id"] == str(data["profesional"].id)
    assert ausente["estado"] == "ausente"
    assert ausente["fecha_local"] == "2026-11-09"
    assert ausente["inicio"].startswith("2026-11-09T12:00:00")


def test_filtro_por_profesional(api_client, session_factory) -> None:
    data = run(setup_ausentismo_reporte(session_factory))
    respuesta = _get(
        api_client,
        data,
        profesional_id=str(data["profesional"].id),
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["atendidos"] == 3
    assert cuerpo["cancelados"] == 1
    assert cuerpo["ausentes"] == 1
    assert cuerpo["turnos_activos"] == 3
    assert cuerpo["tasa_ausentismo"] == "0.40"
    assert cuerpo["tasa_no_asistencia"] == "0.20"
    assert {
        fila["profesional_id"] for fila in cuerpo["detalle"]
    } == {str(data["profesional"].id)}
    assert {
        fila["profesional_id"]
        for fila in cuerpo["por_profesional"]
    } == {str(data["profesional"].id)}
