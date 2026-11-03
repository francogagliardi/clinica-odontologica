"""Patients: registry, bounded search, coverage and RBAC (C-05)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.integration.helpers import run, sqlstate
from tests.integration.pacientes_helpers import (
    create_obra_social,
    create_paciente,
    obra_social_payload,
    paciente_payload,
)
from tests.integration.recursos_helpers import (
    bearer,
    consultorio_demo_id,
    create_actor,
    seed_demo,
)

ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)


def _setup(session_factory) -> tuple[uuid.UUID, dict[str, object]]:
    run(seed_demo(session_factory))
    consultorio_id = run(consultorio_demo_id(session_factory))
    actores = {
        rol: run(create_actor(session_factory, rol)) for rol in ROLES
    }
    return consultorio_id, actores


def _create(api_client, actor, payload: dict[str, object]):
    return api_client.post(
        "/pacientes", json=payload, headers=bearer(actor)
    )


async def _insertar_paciente_sql(
    session_factory, consultorio_id: uuid.UUID, dni: str
) -> None:
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO pacientes "
                "(id, consultorio_id, nombre, apellido, dni, telefono) "
                "VALUES (:id, :consultorio_id, 'Sql', 'Directo', :dni, "
                "'+5491100000000')"
            ),
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "dni": dni,
            },
        )


def test_alta_normaliza_y_devuelve_la_ficha(api_client, session_factory) -> None:
    """Expected: DNI/phone are canonical and the ficha is readable."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = api_client.post(
        "/pacientes",
        json=paciente_payload(dni="40.111.222", telefono="+54 9 11 4444-5555"),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["dni"] == "40111222"
    assert body["telefono"] == "+5491144445555"
    assert body["obra_social_id"] is None
    assert body["nro_afiliado"] is None

    ficha = api_client.get(
        f"/pacientes/{body['id']}", headers=bearer(actores["recepcionista"])
    )
    assert ficha.status_code == 200, ficha.text
    assert ficha.json() == body


def test_dni_duplicado_en_api_y_por_sql_directo(
    api_client, session_factory
) -> None:
    """Business error: one active patient per DNI in the consultorio."""
    consultorio_id, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    assert _create(api_client, actores["administrador"], paciente_payload()).status_code == 201
    duplicated = _create(
        api_client,
        actores["administrador"],
        paciente_payload(dni="40.111.222", telefono="11 4444-6666"),
    )
    assert duplicated.status_code == 409, duplicated.text

    with pytest.raises(IntegrityError) as error:
        run(_insertar_paciente_sql(session_factory, consultorio_id, "40111222"))
    assert sqlstate(error.value) == "23505"


def test_baja_logica_libera_el_dni(api_client, session_factory) -> None:
    """Edge: a soft-deleted patient frees the DNI and disappears."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = _create(api_client, actores["administrador"], paciente_payload())
    assert created.status_code == 201
    paciente_id = created.json()["id"]

    assert (
        api_client.delete(f"/pacientes/{paciente_id}", headers=headers).status_code
        == 204
    )
    again = _create(api_client, actores["administrador"], paciente_payload())
    assert again.status_code == 201, again.text
    assert again.json()["id"] != paciente_id
    assert (
        api_client.get(f"/pacientes/{paciente_id}", headers=headers).status_code
        == 404
    )


@pytest.mark.parametrize("telefono", ["", "   ", None])
def test_telefono_ausente_bloquea_el_alta(
    api_client, session_factory, telefono: str | None
) -> None:
    """Business error: WhatsApp is the clinic channel, so phone is required."""
    _consultorio, actores = _setup(session_factory)
    payload = paciente_payload()
    if telefono is None:
        payload.pop("telefono")
    else:
        payload["telefono"] = telefono

    assert (
        _create(api_client, actores["administrador"], payload).status_code == 422
    )


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("dni", "123456"),
        ("dni", "123456789"),
        ("dni", "4011122A"),
        ("telefono", "541144445555"),
        ("telefono", "114444555"),
        ("telefono", "abc"),
    ],
)
def test_formatos_invalidos_devuelven_422(
    api_client, session_factory, campo: str, valor: str
) -> None:
    """Edge: every invalid identity shape is rejected at the boundary."""
    _consultorio, actores = _setup(session_factory)
    payload = paciente_payload()
    payload[campo] = valor

    assert (
        _create(api_client, actores["administrador"], payload).status_code == 422
    )


def test_edicion_de_paciente_y_404(api_client, session_factory) -> None:
    """Expected: PUT updates editable data; unknown ids are 404."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = _create(api_client, actores["administrador"], paciente_payload())
    paciente_id = created.json()["id"]
    payload = paciente_payload()
    payload.update({"nombre": "Ana María", "notas": "Actualizado"})

    updated = api_client.put(
        f"/pacientes/{paciente_id}", json=payload, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["nombre"] == "Ana María"
    assert updated.json()["dni"] == "40111222"

    missing = api_client.put(
        f"/pacientes/{uuid.uuid4()}", json=payload, headers=headers
    )
    assert missing.status_code == 404, missing.text


def test_busqueda_por_apellido_case_insensitive_y_ordenada(
    api_client, session_factory
) -> None:
    """Expected: prefix search ignores case and orders by surname, name."""
    consultorio_id, actores = _setup(session_factory)
    run(
        create_paciente(
            session_factory,
            consultorio_id,
            nombre="Bruno",
            apellido="Gomez",
            dni="40222333",
            telefono="+5491144440001",
        )
    )
    run(
        create_paciente(
            session_factory,
            consultorio_id,
            nombre="Ana",
            apellido="Gonzalez",
            dni="40333444",
            telefono="+5491144440002",
        )
    )
    run(
        create_paciente(
            session_factory,
            consultorio_id,
            nombre="Carla",
            apellido="Perez",
            dni="40444555",
            telefono="+5491144440003",
        )
    )
    headers = bearer(actores["recepcionista"])

    lower = api_client.get(
        "/pacientes", params={"apellido": "go"}, headers=headers
    )
    upper = api_client.get(
        "/pacientes", params={"apellido": "GO"}, headers=headers
    )
    assert lower.status_code == 200, lower.text
    assert [item["apellido"] for item in lower.json()] == ["Gomez", "Gonzalez"]
    assert upper.json() == lower.json()


def test_busqueda_por_dni_y_telefono_formateados(
    api_client, session_factory
) -> None:
    """Expected: search normalizes the same way as the write path."""
    consultorio_id, actores = _setup(session_factory)
    run(
        create_paciente(
            session_factory,
            consultorio_id,
            nombre="Ana",
            apellido="Gonzalez",
            dni="40555666",
            telefono="+5491155556666",
        )
    )
    headers = bearer(actores["recepcionista"])

    by_dni = api_client.get(
        "/pacientes",
        params={"dni": "40.555.666"},
        headers=headers,
    )
    by_phone = api_client.get(
        "/pacientes",
        params={"telefono": "+54 9 11 5555-6666"},
        headers=headers,
    )
    assert by_dni.status_code == 200, by_dni.text
    assert [item["dni"] for item in by_dni.json()] == ["40555666"]
    assert by_phone.json() == by_dni.json()


def test_busqueda_combina_filtros_con_and(api_client, session_factory) -> None:
    """Edge: filters are ANDed, so a mismatch returns an empty list."""
    consultorio_id, actores = _setup(session_factory)
    run(
        create_paciente(
            session_factory,
            consultorio_id,
            nombre="Ana",
            apellido="Gonzalez",
            dni="40666777",
            telefono="+5491166667777",
        )
    )
    headers = bearer(actores["recepcionista"])

    match = api_client.get(
        "/pacientes",
        params={"apellido": "gon", "dni": "40666777"},
        headers=headers,
    )
    mismatch = api_client.get(
        "/pacientes",
        params={"apellido": "gon", "dni": "40999888"},
        headers=headers,
    )
    assert [item["dni"] for item in match.json()] == ["40666777"]
    assert mismatch.json() == []


def test_busqueda_sin_criterio_o_con_parametro_extra(
    api_client, session_factory
) -> None:
    """Error/edge: no full dump and no silent unknown filters."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["recepcionista"])

    assert api_client.get("/pacientes", headers=headers).status_code == 422
    extra = api_client.get(
        "/pacientes", params={"nombre": "Ana"}, headers=headers
    )
    assert extra.status_code == 422, extra.text


def test_busqueda_sin_coincidencias_y_bajas_excluidas(
    api_client, session_factory
) -> None:
    """Edge: empty result is 200 and soft-deleted patients never show up."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    created = _create(
        api_client,
        actores["administrador"],
        paciente_payload(dni="40777888", apellido="Baja"),
    )
    assert created.status_code == 201

    found = api_client.get(
        "/pacientes",
        params={"apellido": "baja"},
        headers=headers,
    )
    assert len(found.json()) == 1

    api_client.delete(
        f"/pacientes/{created.json()['id']}", headers=headers
    )
    after = api_client.get(
        "/pacientes",
        params={"apellido": "baja"},
        headers=headers,
    )
    assert after.status_code == 200
    assert after.json() == []


def test_indice_de_apellido_se_usa_para_prefijos(
    session_factory,
) -> None:
    """R-05: the expression index serves the prefix search with seqscan off."""

    async def explain() -> list[str]:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(text("SET LOCAL enable_seqscan = off"))
                result = await session.execute(
                    text(
                        "EXPLAIN SELECT id FROM pacientes "
                        "WHERE lower(apellido) LIKE 'go%'"
                    )
                )
                return [row[0] for row in result]

    plan = "\n".join(run(explain()))
    assert "ix_pacientes_apellido_lower" in plan, plan


def test_alta_con_obra_social_y_afiliado(api_client, session_factory) -> None:
    """Expected: coverage and affiliate are returned in the ficha."""
    consultorio_id, actores = _setup(session_factory)
    obra_social = run(create_obra_social(session_factory, consultorio_id))
    payload = paciente_payload(
        dni="40888999",
        obra_social_id=str(obra_social.id),
        nro_afiliado="AF-0001",
    )

    created = _create(api_client, actores["administrador"], payload)
    assert created.status_code == 201, created.text
    assert created.json()["obra_social_id"] == str(obra_social.id)
    assert created.json()["nro_afiliado"] == "AF-0001"


def test_obra_social_inexistente_o_dada_de_baja(
    api_client, session_factory
) -> None:
    """Business error: coverage must point to an active agreement."""
    consultorio_id, actores = _setup(session_factory)
    inexistente = paciente_payload(
        dni="40999000", obra_social_id=str(uuid.uuid4())
    )
    assert (
        _create(api_client, actores["administrador"], inexistente).status_code
        == 404
    )

    obra_social = run(
        create_obra_social(session_factory, consultorio_id, "OS Baja")
    )

    async def baja() -> None:
        from datetime import datetime, timezone

        from app.models import ObraSocial

        async with session_factory() as session, session.begin():
            row = await session.get(ObraSocial, obra_social.id)
            assert row is not None
            row.deleted_at = datetime.now(timezone.utc)
            row.is_active = False

    run(baja())
    payload = paciente_payload(
        dni="40999001", obra_social_id=str(obra_social.id)
    )
    response = _create(api_client, actores["administrador"], payload)
    assert response.status_code == 404, response.text


def test_afiliado_sin_obra_social_devuelve_422(
    api_client, session_factory
) -> None:
    """Business error: an affiliate number without agreement is incoherent."""
    _consultorio, actores = _setup(session_factory)
    payload = paciente_payload(dni="41000111", nro_afiliado="AF-9")
    assert (
        _create(api_client, actores["administrador"], payload).status_code == 422
    )


def test_quitar_y_cambiar_cobertura(api_client, session_factory) -> None:
    """Edge: removing coverage clears the affiliate; changing it keeps it."""
    consultorio_id, actores = _setup(session_factory)
    primera = run(create_obra_social(session_factory, consultorio_id, "OS Uno"))
    segunda = run(create_obra_social(session_factory, consultorio_id, "OS Dos"))
    headers = bearer(actores["administrador"])

    created = _create(
        api_client,
        actores["administrador"],
        paciente_payload(
            dni="41111222",
            obra_social_id=str(primera.id),
            nro_afiliado="AF-1",
        ),
    )
    paciente_id = created.json()["id"]

    conservando = paciente_payload(
        dni="41111222", obra_social_id=None, nro_afiliado="AF-1"
    )
    assert (
        api_client.put(
            f"/pacientes/{paciente_id}", json=conservando, headers=headers
        ).status_code
        == 422
    )

    cambiando = paciente_payload(
        dni="41111222",
        obra_social_id=str(segunda.id),
        nro_afiliado="AF-1",
    )
    changed = api_client.put(
        f"/pacientes/{paciente_id}", json=cambiando, headers=headers
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["obra_social_id"] == str(segunda.id)
    assert changed.json()["nro_afiliado"] == "AF-1"

    sin_cobertura = paciente_payload(
        dni="41111222", obra_social_id=None, nro_afiliado=None
    )
    cleared = api_client.put(
        f"/pacientes/{paciente_id}", json=sin_cobertura, headers=headers
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["obra_social_id"] is None
    assert cleared.json()["nro_afiliado"] is None


def test_recepcion_crea_y_edita_pacientes(api_client, session_factory) -> None:
    """Expected: reception operates the registry."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["recepcionista"])

    created = _create(api_client, actores["recepcionista"], paciente_payload())
    assert created.status_code == 201, created.text
    payload = paciente_payload(notas="Editado por recepción")
    updated = api_client.put(
        f"/pacientes/{created.json()['id']}", json=payload, headers=headers
    )
    assert updated.status_code == 200, updated.text


@pytest.mark.parametrize("rol", ["odontologo", "asistente", "auditor"])
def test_roles_clinicos_no_escriben_pacientes(
    api_client, session_factory, rol: str
) -> None:
    """Business error: only admin/reception write the registry."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores[rol])
    created = _create(api_client, actores["administrador"], paciente_payload())

    assert (
        api_client.post("/pacientes", json=paciente_payload(), headers=headers).status_code
        == 403
    )
    assert (
        api_client.put(
            f"/pacientes/{created.json()['id']}",
            json=paciente_payload(),
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            f"/pacientes/{created.json()['id']}", headers=headers
        ).status_code
        == 403
    )


def test_solo_administrador_da_de_baja(api_client, session_factory) -> None:
    """Business error: reception cannot delete; admin can."""
    _consultorio, actores = _setup(session_factory)
    created = _create(api_client, actores["administrador"], paciente_payload())
    paciente_id = created.json()["id"]

    assert (
        api_client.delete(
            f"/pacientes/{paciente_id}",
            headers=bearer(actores["recepcionista"]),
        ).status_code
        == 403
    )
    assert (
        api_client.delete(
            f"/pacientes/{paciente_id}",
            headers=bearer(actores["administrador"]),
        ).status_code
        == 204
    )


def test_pacientes_sin_token_devuelve_401(api_client, session_factory) -> None:
    """Business error: patient data is never public."""
    _consultorio, _actores = _setup(session_factory)
    assert api_client.get("/pacientes", params={"dni": "40111222"}).status_code == 401
    assert api_client.post("/pacientes", json=paciente_payload()).status_code == 401
