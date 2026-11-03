"""Insurance agreements: CRUD, RBAC, unique names and local rules (C-05)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.integration.helpers import run, sqlstate
from tests.integration.pacientes_helpers import obra_social_payload
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
        "/obras-sociales", json=payload, headers=bearer(actor)
    )


async def _insertar_obra_social_sql(
    session_factory, consultorio_id: uuid.UUID, nombre: str
) -> None:
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO obras_sociales "
                "(id, consultorio_id, nombre, reglas_cobertura) "
                "VALUES (:id, :consultorio_id, :nombre, '{}'::jsonb)"
            ),
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "nombre": nombre,
            },
        )


def test_alta_y_lectura_por_odontologo(api_client, session_factory) -> None:
    """Expected: admin creates and the dentist reads the agreement."""
    _consultorio, actores = _setup(session_factory)

    created = _create(
        api_client, actores["administrador"], obra_social_payload("OS Demo 2")
    )
    assert created.status_code == 201, created.text
    assert created.json()["nombre"] == "OS Demo 2"
    assert created.json()["nomenclador_ref"] == "NOM-TEST"

    listed = api_client.get(
        "/obras-sociales", headers=bearer(actores["odontologo"])
    )
    assert listed.status_code == 200, listed.text
    assert "OS Demo 2" in [item["nombre"] for item in listed.json()]


def test_nombre_duplicado_sin_distinguir_mayusculas(
    api_client, session_factory
) -> None:
    """Business error: active agreement names are unique per consultorio."""
    consultorio_id, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    assert _create(api_client, actores["administrador"], obra_social_payload("OS Dup")).status_code == 201
    duplicated = _create(
        api_client, actores["administrador"], obra_social_payload("os dup")
    )
    assert duplicated.status_code == 409, duplicated.text

    with pytest.raises(IntegrityError) as error:
        run(
            _insertar_obra_social_sql(
                session_factory, consultorio_id, "OS DUP"
            )
        )
    assert sqlstate(error.value) == "23505"


def test_baja_logica_libera_el_nombre(api_client, session_factory) -> None:
    """Edge: a soft-deleted name can be reused and disappears from the list."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])

    created = _create(
        api_client, actores["administrador"], obra_social_payload("OS Libre")
    )
    obra_social_id = created.json()["id"]
    assert (
        api_client.delete(
            f"/obras-sociales/{obra_social_id}", headers=headers
        ).status_code
        == 204
    )
    again = _create(
        api_client, actores["administrador"], obra_social_payload("OS Libre")
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] != obra_social_id

    listed = api_client.get("/obras-sociales", headers=headers)
    assert obra_social_id not in [item["id"] for item in listed.json()]


def test_recepcion_edita_pero_no_crea_ni_borra(
    api_client, session_factory
) -> None:
    """Business error: literal matrix column for Obras sociales."""
    _consultorio, actores = _setup(session_factory)
    recepcion = bearer(actores["recepcionista"])

    assert (
        api_client.post(
            "/obras-sociales",
            json=obra_social_payload("OS Recep"),
            headers=recepcion,
        ).status_code
        == 403
    )
    created = _create(
        api_client, actores["administrador"], obra_social_payload("OS Recep")
    )
    updated = api_client.put(
        f"/obras-sociales/{created.json()['id']}",
        json=obra_social_payload("OS Recep Editada"),
        headers=recepcion,
    )
    assert updated.status_code == 200, updated.text
    assert (
        api_client.delete(
            f"/obras-sociales/{created.json()['id']}", headers=recepcion
        ).status_code
        == 403
    )


def test_asistente_sin_acceso_al_modulo(api_client, session_factory) -> None:
    """Business error: the assistant has no Obras sociales column."""
    _consultorio, actores = _setup(session_factory)
    assert (
        api_client.get(
            "/obras-sociales", headers=bearer(actores["asistente"])
        ).status_code
        == 403
    )


def test_convenio_inexistente_o_dado_de_baja(
    api_client, session_factory
) -> None:
    """Business error: reading/editing an unknown agreement is 404."""
    _consultorio, actores = _setup(session_factory)
    headers = bearer(actores["administrador"])
    missing = uuid.uuid4()

    assert (
        api_client.get(f"/obras-sociales/{missing}", headers=headers).status_code
        == 404
    )
    assert (
        api_client.put(
            f"/obras-sociales/{missing}",
            json=obra_social_payload(),
            headers=headers,
        ).status_code
        == 404
    )


def test_obras_sociales_sin_token_devuelve_401(
    api_client, session_factory
) -> None:
    """Business error: coverage rules are never public."""
    _consultorio, _actores = _setup(session_factory)
    assert api_client.get("/obras-sociales").status_code == 401
    assert (
        api_client.post(
            "/obras-sociales", json=obra_social_payload()
        ).status_code
        == 401
    )


def test_reglas_completas_se_normalizan(api_client, session_factory) -> None:
    """Expected: codes are uppercased and percentages preserved."""
    _consultorio, actores = _setup(session_factory)
    payload = obra_social_payload("OS Reglas")
    payload["reglas_cobertura"] = {
        "cobertura_porcentaje": 60,
        "copago_porcentaje": 40,
        "prestaciones_cubiertas": ["cons", "lim"],
        "requiere_autorizacion": True,
    }

    created = _create(api_client, actores["administrador"], payload)
    assert created.status_code == 201, created.text
    reglas = created.json()["reglas_cobertura"]
    assert reglas["prestaciones_cubiertas"] == ["CONS", "LIM"]
    assert reglas["requiere_autorizacion"] is True


@pytest.mark.parametrize(
    ("mutacion", "detalle"),
    [
        ({"cobertura_porcentaje": 70, "copago_porcentaje": 40}, "100"),
        ({"cobertura_porcentaje": 101}, "100"),
        ({"copago_porcentaje": -1}, "0"),
        (
            {"prestaciones_cubiertas": ["NOEXISTE"]},
            "catálogo",
        ),
        ({"prestaciones_cubiertas": ["CONS", "cons"]}, "repet"),
    ],
)
def test_reglas_invalidas_devuelven_422(
    api_client, session_factory, mutacion: dict[str, object], detalle: str
) -> None:
    """Edge: every invalid rule shape is rejected with a precise detail."""
    _consultorio, actores = _setup(session_factory)
    payload = obra_social_payload("OS Invalida")
    payload["reglas_cobertura"] = {
        "cobertura_porcentaje": 50,
        "copago_porcentaje": 50,
        "prestaciones_cubiertas": ["CONS"],
        **mutacion,
    }

    response = _create(api_client, actores["administrador"], payload)
    assert response.status_code == 422, response.text
    assert detalle.lower() in response.text.lower()


def test_reglas_con_forma_invalida_devuelven_422(
    api_client, session_factory
) -> None:
    """Edge: rules must be a JSON object, not a list or scalar."""
    _consultorio, actores = _setup(session_factory)
    payload = obra_social_payload("OS Forma")
    payload["reglas_cobertura"] = ["CONS"]

    assert (
        _create(api_client, actores["administrador"], payload).status_code == 422
    )


def test_convenio_sin_reglas_acepta_objeto_vacio(
    api_client, session_factory
) -> None:
    """Edge: rules can be defined after the agreement exists."""
    _consultorio, actores = _setup(session_factory)
    payload = obra_social_payload("OS Vacia")
    payload.pop("reglas_cobertura")

    created = _create(api_client, actores["administrador"], payload)
    assert created.status_code == 201, created.text
    assert created.json()["reglas_cobertura"]["prestaciones_cubiertas"] == []


def test_validacion_externa_rechazada_y_falso_por_defecto(
    api_client, session_factory
) -> None:
    """Business error + edge: v1 only supports local rules."""
    _consultorio, actores = _setup(session_factory)
    externa = obra_social_payload("OS Externa")
    externa["validacion_externa"] = True
    rejected = _create(api_client, actores["administrador"], externa)
    assert rejected.status_code == 422, rejected.text
    assert "validación externa" in rejected.text.lower()

    local = obra_social_payload("OS Local")
    local.pop("validacion_externa")
    accepted = _create(api_client, actores["administrador"], local)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["validacion_externa"] is False

    explicito = obra_social_payload("OS Local Explicita")
    explicito["validacion_externa"] = False
    assert (
        _create(api_client, actores["administrador"], explicito).status_code
        == 201
    )
