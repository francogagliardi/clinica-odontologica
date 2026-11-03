"""Professionals: CRUD, RBAC, partial uniqueness and agenda validation (C-04)."""

import uuid

import pytest

from tests.integration.helpers import run
from tests.integration.recursos_helpers import (
    bearer,
    consultorio_demo_id,
    create_actor,
    create_profesional,
    seed_demo,
)

AGENDA_CONFIG = {
    "duracion_base_min": 60,
    "dias_atencion": [0, 1, 2, 3, 4],
    "hora_desde": "09:00:00",
    "hora_hasta": "12:00:00",
}


def _payload(matricula: str = "MP-001") -> dict[str, object]:
    return {
        "matricula": matricula,
        "usuario_id": None,
        "especialidades": ["general"],
        "agenda_config": dict(AGENDA_CONFIG),
    }


def _setup(session_factory) -> tuple[uuid.UUID, dict[str, object]]:
    run(seed_demo(session_factory))
    consultorio_id = run(consultorio_demo_id(session_factory))
    actores = {
        rol: run(create_actor(session_factory, rol))
        for rol in (
            "administrador",
            "odontologo",
            "recepcionista",
            "asistente",
            "auditor",
        )
    }
    return consultorio_id, actores


def test_alta_de_profesional_y_lectura_por_recepcion(
    api_client, session_factory
) -> None:
    """Expected: admin creates and reception reads the professional (201/200)."""
    _consultorio, actores = _setup(session_factory)

    created = api_client.post(
        "/profesionales",
        json=_payload(),
        headers=bearer(actores["administrador"]),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["matricula"] == "MP-001"
    assert body["agenda_config"]["duracion_base_min"] == 60
    assert body["agenda_config"]["dias_atencion"] == [0, 1, 2, 3, 4]

    listed = api_client.get(
        "/profesionales", headers=bearer(actores["recepcionista"])
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [body["id"]]


def test_matricula_duplicada_devuelve_409(api_client, session_factory) -> None:
    """Business error: two active professionals cannot share a matrícula."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    assert (
        api_client.post(
            "/profesionales", json=_payload("MP-DUP"), headers=headers
        ).status_code
        == 201
    )
    duplicated = api_client.post(
        "/profesionales", json=_payload("MP-DUP"), headers=headers
    )
    assert duplicated.status_code == 409, duplicated.text


@pytest.mark.parametrize(
    "rol", ["odontologo", "recepcionista", "asistente", "auditor"]
)
def test_escritura_por_rol_no_administrador_devuelve_403(
    api_client, session_factory, rol: str
) -> None:
    """Business error: only the configuration role writes professionals."""
    consultorio_id, actores = _setup(session_factory)
    existente = run(
        create_profesional(session_factory, consultorio_id, "MP-EXIST")
    )
    headers = bearer(actores[rol])

    assert (
        api_client.post(
            "/profesionales", json=_payload("MP-ROL"), headers=headers
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            f"/profesionales/{existente.id}", headers=headers
        ).status_code
        == 403
    )


def test_baja_logica_libera_la_matricula(api_client, session_factory) -> None:
    """Edge: a soft-deleted value can be reused and disappears from the list."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = api_client.post(
        "/profesionales", json=_payload("MP-LIBRE"), headers=headers
    )
    assert created.status_code == 201
    profesional_id = created.json()["id"]

    assert (
        api_client.delete(
            f"/profesionales/{profesional_id}", headers=headers
        ).status_code
        == 204
    )
    again = api_client.post(
        "/profesionales", json=_payload("MP-LIBRE"), headers=headers
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] != profesional_id

    listed = api_client.get("/profesionales", headers=headers)
    ids = {item["id"] for item in listed.json()}
    assert profesional_id not in ids
    assert again.json()["id"] in ids


@pytest.mark.parametrize(
    "mutacion",
    [
        {"duracion_base_min": 0},
        {"duracion_base_min": -15},
        {"dias_atencion": []},
        {"dias_atencion": [0, 7]},
        {"dias_atencion": [1, 1]},
        {"hora_desde": "12:00:00", "hora_hasta": "09:00:00"},
        {"hora_desde": "12:00:00", "hora_hasta": "12:00:00"},
    ],
)
def test_agenda_invalida_devuelve_422(
    api_client, session_factory, mutacion: dict[str, object]
) -> None:
    """Edge: every invalid agenda shape is rejected at the boundary."""
    _consultorio, actores = _setup(session_factory)
    payload = _payload("MP-AGENDA")
    payload["agenda_config"] = {**AGENDA_CONFIG, **mutacion}

    response = api_client.post(
        "/profesionales",
        json=payload,
        headers=bearer(actores["administrador"]),
    )
    assert response.status_code == 422, response.text


def test_usuario_ya_vinculado_devuelve_409(
    api_client, session_factory
) -> None:
    """Edge: one active professional per user; unknown users are 404."""
    consultorio_id, actores = _setup(session_factory)
    odontologo = actores["odontologo"]
    headers = bearer(actores["administrador"])
    run(
        create_profesional(
            session_factory,
            consultorio_id,
            "MP-USER-1",
            usuario_id=odontologo.id,
        )
    )

    payload = _payload("MP-USER-2")
    payload["usuario_id"] = str(odontologo.id)
    duplicated = api_client.post(
        "/profesionales", json=payload, headers=headers
    )
    assert duplicated.status_code == 409, duplicated.text

    payload["usuario_id"] = str(uuid.uuid4())
    missing = api_client.post("/profesionales", json=payload, headers=headers)
    assert missing.status_code == 404, missing.text


def test_actualizacion_de_profesional(api_client, session_factory) -> None:
    """Expected: PUT updates the agenda without duplicating the row."""
    consultorio_id, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-UPD")
    )

    payload = _payload("MP-UPD")
    payload["agenda_config"] = {
        **AGENDA_CONFIG,
        "duracion_base_min": 45,
        "dias_atencion": [5],
    }
    updated = api_client.put(
        f"/profesionales/{profesional.id}", json=payload, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["agenda_config"]["duracion_base_min"] == 45
    assert updated.json()["agenda_config"]["dias_atencion"] == [5]
