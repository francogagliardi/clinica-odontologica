"""Chairs and idempotent professional-chair habilitation (C-04)."""

import uuid

import pytest
from sqlalchemy import func, select

from app.models import ProfesionalSillon
from tests.integration.helpers import run
from tests.integration.recursos_helpers import (
    bearer,
    consultorio_demo_id,
    create_actor,
    create_profesional,
    create_sillon,
    seed_demo,
)


def _setup(session_factory) -> tuple[uuid.UUID, dict[str, object]]:
    run(seed_demo(session_factory))
    consultorio_id = run(consultorio_demo_id(session_factory))
    actores = {
        rol: run(create_actor(session_factory, rol))
        for rol in ("administrador", "odontologo", "recepcionista")
    }
    return consultorio_id, actores


def test_alta_de_sillon_y_listado(api_client, session_factory) -> None:
    """Expected: admin creates a chair and reception lists it (201/200)."""
    _consultorio, actores = _setup(session_factory)
    created = api_client.post(
        "/sillones",
        json={"nombre": "Box Nuevo"},
        headers=bearer(actores["administrador"]),
    )
    assert created.status_code == 201, created.text

    listed = api_client.get(
        "/sillones", headers=bearer(actores["recepcionista"])
    )
    assert listed.status_code == 200, listed.text
    assert "Box Nuevo" in {sillon["nombre"] for sillon in listed.json()}


def test_sillon_duplicado_devuelve_409(api_client, session_factory) -> None:
    """Business error: active chair names are unique per consultorio."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    assert (
        api_client.post(
            "/sillones", json={"nombre": "Box Dup"}, headers=headers
        ).status_code
        == 201
    )
    duplicated = api_client.post(
        "/sillones", json={"nombre": "Box Dup"}, headers=headers
    )
    assert duplicated.status_code == 409, duplicated.text


@pytest.mark.parametrize("rol", ["odontologo", "recepcionista"])
def test_escritura_de_sillones_por_no_administrador(
    api_client, session_factory, rol: str
) -> None:
    """Business error: only admin writes chairs and habilitations."""
    consultorio_id, actores = _setup(session_factory)
    sillon = run(create_sillon(session_factory, consultorio_id, "Box Rol"))
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-SILLON")
    )
    headers = bearer(actores[rol])

    assert (
        api_client.post(
            "/sillones", json={"nombre": "Box Prohibido"}, headers=headers
        ).status_code
        == 403
    )
    assert (
        api_client.delete(f"/sillones/{sillon.id}", headers=headers).status_code
        == 403
    )
    assert (
        api_client.post(
            f"/profesionales/{profesional.id}/sillones/{sillon.id}",
            headers=headers,
        ).status_code
        == 403
    )


def test_baja_logica_de_sillon_libera_el_nombre(
    api_client, session_factory
) -> None:
    """Edge: a soft-deleted chair frees its name and leaves the list."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = api_client.post(
        "/sillones", json={"nombre": "Box Libre"}, headers=headers
    )
    assert created.status_code == 201
    sillon_id = created.json()["id"]
    assert (
        api_client.delete(f"/sillones/{sillon_id}", headers=headers).status_code
        == 204
    )

    again = api_client.post(
        "/sillones", json={"nombre": "Box Libre"}, headers=headers
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] != sillon_id

    listed = api_client.get("/sillones", headers=headers)
    ids = {sillon["id"] for sillon in listed.json()}
    assert sillon_id not in ids
    assert again.json()["id"] in ids


def test_habilitacion_repetida_no_duplica(api_client, session_factory) -> None:
    """Edge: POST twice returns 204 twice and leaves exactly one link."""
    consultorio_id, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    sillon = run(create_sillon(session_factory, consultorio_id, "Box Idem"))
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-IDEM")
    )
    url = f"/profesionales/{profesional.id}/sillones/{sillon.id}"

    assert api_client.post(url, headers=headers).status_code == 204
    assert api_client.post(url, headers=headers).status_code == 204

    async def count() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(ProfesionalSillon)
                .where(
                    ProfesionalSillon.profesional_id == profesional.id,
                    ProfesionalSillon.sillon_id == sillon.id,
                )
            )

    assert run(count()) == 1

    habilitados = api_client.get(
        f"/profesionales/{profesional.id}/sillones", headers=headers
    )
    assert habilitados.status_code == 200
    assert [item["id"] for item in habilitados.json()] == [str(sillon.id)]

    assert api_client.delete(url, headers=headers).status_code == 204
    assert run(count()) == 0


def test_habilitacion_con_recurso_inexistente_o_inactivo(
    api_client, session_factory
) -> None:
    """Business error: unknown or soft-deleted resources cannot be linked."""
    consultorio_id, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-404")
    )
    sillon = run(create_sillon(session_factory, consultorio_id, "Box Baja"))

    assert (
        api_client.post(
            f"/profesionales/{uuid.uuid4()}/sillones/{sillon.id}",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            f"/profesionales/{profesional.id}/sillones/{uuid.uuid4()}",
            headers=headers,
        ).status_code
        == 404
    )

    assert (
        api_client.delete(f"/sillones/{sillon.id}", headers=headers).status_code
        == 204
    )
    assert (
        api_client.post(
            f"/profesionales/{profesional.id}/sillones/{sillon.id}",
            headers=headers,
        ).status_code
        == 404
    )
