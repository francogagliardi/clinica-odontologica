"""C-15 exportation RBAC and tenant/ownership isolation (tasks 8.5/8.6)."""

import uuid

from app.main import app
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import bearer
from tests.integration.reportes_helpers import (
    insertar_exportacion_db,
    setup_rbac_reporte,
)

URL = "/exportaciones"


def _setup(session_factory):
    return run(setup_rbac_reporte(session_factory))


def _post(api_client, data, payload, actor: str | None):
    headers = bearer(data["actores"][actor]) if actor else {}
    return api_client.post(URL, json=payload, headers=headers)


def _get(api_client, data, path, actor: str | None):
    headers = bearer(data["actores"][actor]) if actor else {}
    return api_client.get(path, headers=headers)


def test_administrador_exporta_ambos_alcances(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    paciente = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(data["paciente"].id)},
        "administrador",
    )
    consultorio = _post(
        api_client, data, {"alcance": "consultorio"}, "administrador"
    )
    assert paciente.status_code == 202, paciente.text
    assert consultorio.status_code == 202, consultorio.text


def test_odontologo_solo_pacientes_propios(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    propio = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(data["paciente"].id)},
        "odontologo",
    )
    assert propio.status_code == 202, propio.text

    consultorio = _post(
        api_client, data, {"alcance": "consultorio"}, "odontologo"
    )
    assert consultorio.status_code == 403, consultorio.text

    sin_vinculo = run(
        create_paciente(
            session_factory,
            data["consultorio_id"],
            nombre="Sin",
            apellido="Vinculo",
            dni="42888111",
            telefono="+5491177773111",
        )
    )
    ajeno = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(sin_vinculo.id)},
        "odontologo",
    )
    assert ajeno.status_code == 403, ajeno.text


def test_recepcion_asistente_auditor_403_y_sin_token_401(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    payload = {"alcance": "consultorio"}
    for actor in ("recepcionista", "asistente", "auditor"):
        respuesta = _post(api_client, data, payload, actor)
        assert respuesta.status_code == 403, (actor, respuesta.text)
    assert _post(api_client, data, payload, None).status_code == 401

    for actor in ("recepcionista", "asistente", "auditor"):
        assert _get(api_client, data, URL, actor).status_code == 403
    assert _get(api_client, data, URL, None).status_code == 401


def test_listado_estado_y_archivo_ajenos_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    admin = data["actores"]["administrador"]
    consultorio_id = data["consultorio_id"]

    ajeno_id = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=admin.id,
            alcance="consultorio",
        )
    )
    status_ajeno = _get(
        api_client, data, f"{URL}/{ajeno_id}", "odontologo"
    )
    assert status_ajeno.status_code == 404, status_ajeno.text
    archivo_ajeno = _get(
        api_client, data, f"{URL}/{ajeno_id}/archivo", "odontologo"
    )
    assert archivo_ajeno.status_code == 404, archivo_ajeno.text

    listado = _get(api_client, data, URL, "odontologo")
    assert listado.status_code == 200
    assert listado.json() == []

    propio = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(data["paciente"].id)},
        "odontologo",
    )
    assert propio.status_code == 202, propio.text
    propio_id = propio.json()["id"]

    propio_estado = _get(
        api_client, data, f"{URL}/{propio_id}", "odontologo"
    )
    assert propio_estado.status_code == 200
    listado_propio = _get(api_client, data, URL, "odontologo").json()
    assert [fila["id"] for fila in listado_propio] == [propio_id]

    admin_listado = _get(api_client, data, URL, "administrador").json()
    assert {fila["id"] for fila in admin_listado} >= {
        str(ajeno_id),
        propio_id,
    }


def test_estado_y_archivo_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    from tests.integration.clinica_helpers import otro_consultorio

    otro = run(otro_consultorio(session_factory))
    ajeno_id = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=otro["consultorio_id"],
            solicitado_por=data["actores"]["administrador"].id,
            alcance="consultorio",
        )
    )
    for sufijo in ("", "/archivo"):
        respuesta = _get(
            api_client, data, f"{URL}/{ajeno_id}{sufijo}", "administrador"
        )
        assert respuesta.status_code == 404, (sufijo, respuesta.text)


def test_listado_filtra_por_estado_y_alcance(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    admin = data["actores"]["administrador"]
    paciente_job = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            solicitado_por=admin.id,
            alcance="paciente",
            paciente_id=data["paciente"].id,
        )
    )
    consultorio_job = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            solicitado_por=admin.id,
            alcance="consultorio",
            estado="fallida",
        )
    )

    por_alcance = _get(
        api_client,
        data,
        f"{URL}?alcance=consultorio",
        "administrador",
    )
    assert por_alcance.status_code == 200
    assert [fila["id"] for fila in por_alcance.json()] == [
        str(consultorio_job)
    ]
    por_estado = _get(
        api_client, data, f"{URL}?estado=fallida", "administrador"
    )
    assert [fila["id"] for fila in por_estado.json()] == [
        str(consultorio_job)
    ]
    invalido = _get(
        api_client, data, f"{URL}?estado=otro", "administrador"
    )
    assert invalido.status_code == 422
    extra = _get(
        api_client, data, f"{URL}?foo=bar", "administrador"
    )
    assert extra.status_code == 422
