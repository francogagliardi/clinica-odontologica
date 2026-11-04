"""Budget RBAC matrix: D9 ownership and the read-only backoffice roles."""

import uuid

from tests.integration.helpers import run
from tests.integration.presupuestos_helpers import setup_presupuestos
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def _payload(
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    prestaciones,
    codigo: str = "CONS",
) -> dict[str, object]:
    return {
        "paciente_id": str(paciente_id),
        "profesional_id": str(profesional_id),
        "items": [
            {"prestacion_id": str(prestaciones[codigo].id), "cantidad": 1}
        ],
    }


def _alta(api_client, actor, paciente_id, profesional_id, prestaciones, codigo="CONS"):
    return api_client.post(
        "/presupuestos",
        json=_payload(paciente_id, profesional_id, prestaciones, codigo),
        headers=bearer(actor),
    )


def _crear_ajeno(api_client, data) -> str:
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_ajeno"].id,
        data["profesional_ajeno"].id,
        data["prestaciones"],
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def test_administrador_crud_sobre_cualquier_profesional(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])

    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_ajeno"].id,
        data["profesional_ajeno"].id,
        data["prestaciones"],
    )
    assert creado.status_code == 201, creado.text
    presupuesto_id = creado.json()["id"]

    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_id}", headers=headers
        ).status_code
        == 200
    )
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=_payload(
                data["paciente_ajeno"].id,
                data["profesional_ajeno"].id,
                data["prestaciones"],
                codigo="OBT",
            ),
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        api_client.patch(
            f"/presupuestos/{presupuesto_id}/estado",
            json={"estado": "aceptado"},
            headers=headers,
        ).status_code
        == 200
    )

    borrador = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_ajeno"].id,
        data["profesional_ajeno"].id,
        data["prestaciones"],
    )
    assert (
        api_client.delete(
            f"/presupuestos/{borrador.json()['id']}", headers=headers
        ).status_code
        == 204
    )


def test_odontologo_crea_solo_para_su_paciente_y_profesional(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    propio = _alta(
        api_client,
        odontologo,
        data["paciente_propio"].id,
        data["profesional"].id,
        data["prestaciones"],
    )
    assert propio.status_code == 201, propio.text

    paciente_ajeno = _alta(
        api_client,
        odontologo,
        data["paciente_ajeno"].id,
        data["profesional"].id,
        data["prestaciones"],
    )
    assert paciente_ajeno.status_code == 403, paciente_ajeno.text

    profesional_ajeno = _alta(
        api_client,
        odontologo,
        data["paciente_propio"].id,
        data["profesional_ajeno"].id,
        data["prestaciones"],
    )
    assert profesional_ajeno.status_code == 403, profesional_ajeno.text


def test_odontologo_sin_fila_en_profesionales_403(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    sin_fila = data["odontologo_sin_profesional"]

    creado = _alta(
        api_client,
        sin_fila,
        data["paciente_propio"].id,
        data["profesional"].id,
        data["prestaciones"],
    )
    assert creado.status_code == 403, creado.text

    listado = api_client.get(
        "/presupuestos", headers=bearer(sin_fila)
    )
    assert listado.status_code == 403, listado.text


def test_recepcion_lee_y_no_escribe(api_client, session_factory) -> None:
    data = _setup(session_factory)
    recepcion = data["actores"]["recepcionista"]
    presupuesto_id = _crear_ajeno(api_client, data)

    assert (
        api_client.get("/presupuestos", headers=bearer(recepcion)).status_code
        == 200
    )
    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_id}", headers=bearer(recepcion)
        ).status_code
        == 200
    )

    assert (
        _alta(
            api_client,
            data["actores"]["recepcionista"],
            data["paciente_os_demo"].id,
            data["profesional"].id,
            data["prestaciones"],
        ).status_code
        == 403
    )
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=_payload(
                data["paciente_os_demo"].id,
                data["profesional"].id,
                data["prestaciones"],
            ),
            headers=bearer(recepcion),
        ).status_code
        == 403
    )
    assert (
        api_client.patch(
            f"/presupuestos/{presupuesto_id}/estado",
            json={"estado": "aceptado"},
            headers=bearer(recepcion),
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            f"/presupuestos/{presupuesto_id}", headers=bearer(recepcion)
        ).status_code
        == 403
    )


def test_asistente_y_auditor_leen_y_no_escriben(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    presupuesto_id = _crear_ajeno(api_client, data)

    for rol in ("asistente", "auditor"):
        actor = data["actores"][rol]
        headers = bearer(actor)
        assert (
            api_client.get("/presupuestos", headers=headers).status_code
            == 200
        ), rol
        assert (
            api_client.get(
                f"/presupuestos/{presupuesto_id}", headers=headers
            ).status_code
            == 200
        ), rol
        assert (
            _alta(
                api_client,
                actor,
                data["paciente_os_demo"].id,
                data["profesional"].id,
                data["prestaciones"],
            ).status_code
            == 403
        ), rol
        assert (
            api_client.patch(
                f"/presupuestos/{presupuesto_id}/estado",
                json={"estado": "aceptado"},
                headers=headers,
            ).status_code
            == 403
        ), rol
        assert (
            api_client.delete(
                f"/presupuestos/{presupuesto_id}", headers=headers
            ).status_code
            == 403
        ), rol


def test_paciente_sin_turno_vigente_403(api_client, session_factory) -> None:
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["odontologo"],
        data["paciente_sin_turno"].id,
        data["profesional"].id,
        data["prestaciones"],
    )
    assert respuesta.status_code == 403, respuesta.text


def test_presupuesto_de_otro_odontologo_403(api_client, session_factory) -> None:
    data = _setup(session_factory)
    presupuesto_id = _crear_ajeno(api_client, data)
    headers = bearer(data["actores"]["odontologo"])

    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_id}", headers=headers
        ).status_code
        == 403
    )
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=_payload(
                data["paciente_propio"].id,
                data["profesional"].id,
                data["prestaciones"],
            ),
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        api_client.patch(
            f"/presupuestos/{presupuesto_id}/estado",
            json={"estado": "aceptado"},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            f"/presupuestos/{presupuesto_id}", headers=headers
        ).status_code
        == 403
    )


def test_odontologo_edita_su_propio_presupuesto(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["odontologo"])
    creado = _alta(
        api_client,
        data["actores"]["odontologo"],
        data["paciente_propio"].id,
        data["profesional"].id,
        data["prestaciones"],
    )
    presupuesto_id = creado.json()["id"]

    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_id}", headers=headers
        ).status_code
        == 200
    )
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=_payload(
                data["paciente_propio"].id,
                data["profesional"].id,
                data["prestaciones"],
                codigo="OBT",
            ),
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        api_client.patch(
            f"/presupuestos/{presupuesto_id}/estado",
            json={"estado": "aceptado"},
            headers=headers,
        ).status_code
        == 200
    )


def test_sin_token_todos_los_endpoints_401(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    presupuesto_id = _crear_ajeno(api_client, data)
    payload = _payload(
        data["paciente_os_demo"].id,
        data["profesional"].id,
        data["prestaciones"],
    )

    assert api_client.get("/presupuestos").status_code == 401
    assert (
        api_client.get(f"/presupuestos/{presupuesto_id}").status_code == 401
    )
    assert api_client.post("/presupuestos", json=payload).status_code == 401
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}", json=payload
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            f"/presupuestos/{presupuesto_id}/recalcular", json={}
        ).status_code
        == 401
    )
    assert (
        api_client.patch(
            f"/presupuestos/{presupuesto_id}/estado",
            json={"estado": "aceptado"},
        ).status_code
        == 401
    )
    assert (
        api_client.delete(f"/presupuestos/{presupuesto_id}").status_code
        == 401
    )
