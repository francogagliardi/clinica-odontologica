"""C-15 agenda and occupation report (tasks 4.1/4.2, design D8/D9/D13).

The dataset has exactly 3 attended + 1 cancelled + 1 absent appointments, two
professionals and two chairs. Professional one has 480 available minutes and
240 occupied minutes, i.e. the 50.00 % scenario of the spec.
"""

import uuid
from datetime import date, datetime

from tests.integration.helpers import run
from tests.integration.reportes_helpers import setup_agenda_reporte
from tests.integration.recursos_helpers import bearer, create_profesional

DESDE = date(2026, 11, 9)
HASTA = date(2026, 11, 9)
PARAMS = {"desde": DESDE.isoformat(), "hasta": HASTA.isoformat()}


def _get(api_client, data, actor: str = "administrador", **params):
    return api_client.get(
        "/reportes/agenda",
        params={**PARAMS, **params},
        headers=bearer(data["actores"][actor]),
    )


def test_totales_por_estado_recurso_y_ocupacion_50(
    api_client, session_factory
) -> None:
    data = run(setup_agenda_reporte(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["total_turnos"] == 5
    assert cuerpo["por_estado"] == {
        "reservado": 0,
        "confirmado": 0,
        "en_sala": 0,
        "atendido": 3,
        "cancelado": 1,
        "ausente": 1,
    }
    assert cuerpo["cancelaciones"] == 1
    assert cuerpo["zona_horaria"] == "UTC-3"

    profesional = str(data["profesional"].id)
    segundo = str(data["profesional_dos"].id)
    por_profesional = {
        fila["profesional_id"]: fila
        for fila in cuerpo["por_profesional"]
    }
    assert por_profesional[profesional]["turnos"] == 4
    assert por_profesional[profesional]["minutos_disponibles"] == 480
    assert por_profesional[profesional]["minutos_ocupados"] == 240
    assert por_profesional[profesional]["minutos_sobreturno"] == 0
    assert por_profesional[profesional]["ocupacion_porcentaje"] == "50.00"
    assert por_profesional[profesional]["sin_agenda"] is False
    assert por_profesional[segundo]["turnos"] == 1
    assert por_profesional[segundo]["minutos_disponibles"] == 240
    assert por_profesional[segundo]["minutos_ocupados"] == 0
    assert por_profesional[segundo]["ocupacion_porcentaje"] == "0.00"

    por_sillon = {
        fila["sillon_id"]: fila["turnos"] for fila in cuerpo["por_sillon"]
    }
    assert por_sillon == {
        str(data["sillon_a"].id): 4,
        str(data["sillon_b"].id): 1,
    }
    assert sum(fila["turnos"] for fila in cuerpo["por_profesional"]) == 5
    assert sum(fila["turnos"] for fila in cuerpo["por_sillon"]) == 5

    assert cuerpo["total_detalle"] == 5
    assert cuerpo["detalle_truncado"] is False
    assert len(cuerpo["detalle"]) == 5
    assert cuerpo["filtros"]["limite"] == 500


def test_sobreturnos_no_inflan_la_ocupacion(api_client, session_factory) -> None:
    data = run(setup_agenda_reporte(session_factory, con_sobreturno=True))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    profesional = str(data["profesional"].id)
    fila = next(
        item
        for item in cuerpo["por_profesional"]
        if item["profesional_id"] == profesional
    )
    assert fila["minutos_ocupados"] == 240
    assert fila["minutos_sobreturno"] == 120
    assert fila["ocupacion_porcentaje"] == "50.00"
    assert cuerpo["total_turnos"] == 6
    assert cuerpo["por_estado"]["atendido"] == 4


def test_rango_de_62_dias_se_acepta_y_63_se_rechaza(
    api_client, session_factory
) -> None:
    data = run(setup_agenda_reporte(session_factory))

    aceptado = _get(
        api_client,
        data,
        desde="2026-01-01",
        hasta="2026-03-04",
    )
    assert aceptado.status_code == 200, aceptado.text

    rechazado = _get(
        api_client,
        data,
        desde="2026-01-01",
        hasta="2026-03-05",
    )
    assert rechazado.status_code == 422, rechazado.text

    invertido = _get(
        api_client,
        data,
        desde="2026-11-10",
        hasta="2026-11-09",
    )
    assert invertido.status_code == 422, invertido.text


def test_turno_de_las_2330_utc3_se_cuenta_en_el_dia_local(
    api_client, session_factory
) -> None:
    data = run(setup_agenda_reporte(session_factory))

    respuesta = _get(
        api_client, data, desde="2026-11-04", hasta="2026-11-04"
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["total_turnos"] == 1
    assert len(cuerpo["detalle"]) == 1
    detalle = cuerpo["detalle"][0]
    assert detalle["turno_id"] == str(data["turnos"]["local_2330"])
    assert detalle["fecha_local"] == "2026-11-04"

    siguiente = _get(
        api_client, data, desde="2026-11-05", hasta="2026-11-05"
    )
    assert siguiente.status_code == 200
    assert siguiente.json()["total_turnos"] == 0


def test_filtro_por_estado_y_por_sillon(
    api_client, session_factory
) -> None:
    data = run(setup_agenda_reporte(session_factory))

    atendidos = _get(api_client, data, estado="atendido")
    assert atendidos.status_code == 200, atendidos.text
    cuerpo = atendidos.json()
    assert cuerpo["total_turnos"] == 3
    assert cuerpo["por_estado"]["atendido"] == 3
    assert sum(cuerpo["por_estado"].values()) == 3
    assert cuerpo["total_detalle"] == 3
    assert {
        fila["estado"] for fila in cuerpo["detalle"]
    } == {"atendido"}

    por_sillon = _get(
        api_client,
        data,
        sillon_id=str(data["sillon_b"].id),
    )
    assert por_sillon.status_code == 200, por_sillon.text
    assert por_sillon.json()["total_turnos"] == 1


def test_filtro_por_profesional_y_profesionales_invalidos(
    api_client, session_factory
) -> None:
    data = run(setup_agenda_reporte(session_factory))

    propio = _get(
        api_client,
        data,
        profesional_id=str(data["profesional"].id),
    )
    assert propio.status_code == 200, propio.text
    cuerpo = propio.json()
    assert cuerpo["total_turnos"] == 4
    assert {
        fila["profesional_id"] for fila in cuerpo["detalle"]
    } == {str(data["profesional"].id)}

    inexistente = _get(
        api_client, data, profesional_id=str(uuid.uuid4())
    )
    assert inexistente.status_code == 404, inexistente.text

    # A professional without configured days still answers a coherent 0.00.
    sin_agenda = run(
        create_profesional(
            session_factory,
            data["consultorio_id"],
            "MP-REP-AG-SIN",
            dias_atencion=(5, 6),
            hora_desde=datetime.min.time(),
            hora_hasta=datetime.max.time(),
        )
    )
    vacio = _get(
        api_client, data, profesional_id=str(sin_agenda.id)
    )
    assert vacio.status_code == 200, vacio.text
    fila = vacio.json()["por_profesional"][0]
    assert fila["minutos_disponibles"] == 0
    assert fila["ocupacion_porcentaje"] == "0.00"
    assert fila["sin_agenda"] is True
