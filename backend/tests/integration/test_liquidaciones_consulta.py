"""C-14 group 9.7: settlement listing, detail and strict filters."""

import uuid
from datetime import date

from tests.integration.helpers import run
from tests.integration.liquidaciones_helpers import (
    crear_escenario,
    crear_paciente_os,
    post_liquidacion,
    setup_liquidaciones,
)
from tests.integration.presupuestos_helpers import crear_convenio
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def _crear_dos_liquidaciones(api_client, session_factory, data):
    run(crear_escenario(session_factory, data))
    noviembre = post_liquidacion(api_client, data)
    assert noviembre.status_code == 201, noviembre.text

    otra_os = run(
        crear_convenio(
            session_factory,
            data["consultorio_id"],
            nombre=f"OS Consulta {uuid.uuid4().hex[:5]}",
            reglas_cobertura={
                "cobertura_porcentaje": 60,
                "prestaciones_cubiertas": ["CONS"],
            },
        )
    )
    paciente = run(
        crear_paciente_os(
            session_factory, data, obra_social_id=otra_os.id
        )
    )
    run(
        crear_escenario(
            session_factory,
            data,
            paciente_id=paciente.id,
            fecha_cobro=date(2026, 12, 5),
        )
    )
    diciembre = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 31),
        obra_social_id=otra_os.id,
    )
    assert diciembre.status_code == 201, diciembre.text
    return noviembre.json(), diciembre.json(), otra_os


def test_listado_por_obra_social_estado_y_periodo(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    noviembre, diciembre, otra_os = _crear_dos_liquidaciones(
        api_client, session_factory, data
    )
    headers = bearer(data["actores"]["auditor"])

    def get(**params):
        return api_client.get(
            "/obras-sociales/liquidaciones", params=params, headers=headers
        )

    assert get().status_code == 200
    assert len(get().json()) == 2

    por_os = get(obra_social_id=str(data["obra_social_demo_id"]))
    assert [fila["id"] for fila in por_os.json()] == [noviembre["id"]]

    por_otra_os = get(obra_social_id=str(otra_os.id))
    assert [fila["id"] for fila in por_otra_os.json()] == [diciembre["id"]]

    assert [
        fila["id"] for fila in get(estado="borrador").json()
    ] == [diciembre["id"], noviembre["id"]]
    assert get(estado="cerrada").json() == []

    por_periodo = get(
        desde=date(2026, 12, 1).isoformat(),
        hasta=date(2026, 12, 31).isoformat(),
    )
    assert [fila["id"] for fila in por_periodo.json()] == [diciembre["id"]]


def test_ficha_incluye_items_y_totales(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    run(crear_escenario(session_factory, data))
    creada = post_liquidacion(api_client, data)
    assert creada.status_code == 201, creada.text

    respuesta = api_client.get(
        f"/obras-sociales/liquidaciones/{creada.json()['id']}",
        headers=bearer(data["actores"]["odontologo"]),
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["id"] == creada.json()["id"]
    assert len(cuerpo["items"]) == 1
    assert cuerpo["total_cobertura"] == "6000.00"
    assert cuerpo["cantidad_practicas"] == 1


def test_ficha_inexistente_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = api_client.get(
        f"/obras-sociales/liquidaciones/{uuid.uuid4()}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 404, respuesta.text


def test_filtro_no_declarado_devuelve_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = api_client.get(
        "/obras-sociales/liquidaciones",
        params={"inventado": "1"},
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 422, respuesta.text
