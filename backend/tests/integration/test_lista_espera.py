"""Waiting-list CRUD: alta, listado, baja and RBAC (C-10, tasks 2.1/2.3)."""

import uuid
from datetime import datetime, timedelta

import pytest

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import Consultorio
from tests.integration.helpers import run
from tests.integration.lista_espera_helpers import insertar_entrada
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import (
    bearer,
    create_profesional,
)
from tests.integration.turnos_helpers import prestacion_id, setup_turnos


def _hora(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, 9, hora, minuto, tzinfo=ARGENTINA_OFFSET)


def _setup(session_factory) -> dict[str, object]:
    base = run(setup_turnos(session_factory))
    base["cons"] = run(prestacion_id(session_factory, "CONS"))
    base["endo"] = run(prestacion_id(session_factory, "ENDO"))
    base["paciente2"] = run(
        create_paciente(
            session_factory,
            base["consultorio_id"],
            nombre="Bruno",
            apellido="Lista",
            dni="42111222",
            telefono="+5491100000002",
        )
    )
    return base


def _payload(base, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "paciente_id": str(base["paciente"].id),
        "prestacion_id": str(base["cons"]),
        "profesional_id": None,
    }
    payload.update(overrides)
    return payload


def _alta(api_client, base, actor: str = "recepcionista", **overrides):
    return api_client.post(
        "/lista-espera",
        json=_payload(base, **overrides),
        headers=bearer(base["actores"][actor]),
    )


def _listar(api_client, base, actor: str = "recepcionista", **params):
    return api_client.get(
        "/lista-espera",
        params=params,
        headers=bearer(base["actores"][actor]),
    )


def _baja(api_client, base, entrada_id, actor: str = "recepcionista"):
    return api_client.delete(
        f"/lista-espera/{entrada_id}",
        headers=bearer(base["actores"][actor]),
    )


async def _crear_consultorio(session_factory) -> uuid.UUID:
    async with session_factory() as session, session.begin():
        consultorio = Consultorio(
            id=uuid.uuid4(),
            nombre="Otra Clinica",
            slug=f"otra-{uuid.uuid4().hex[:8]}",
            plazo_cancelacion_horas=24,
        )
        session.add(consultorio)
        await session.flush()
        consultorio_id = consultorio.id
    return consultorio_id


def _otro_consultorio(session_factory) -> dict[str, object]:
    consultorio_id = run(_crear_consultorio(session_factory))
    paciente = run(
        create_paciente(
            session_factory,
            consultorio_id,
            nombre="Ajeno",
            apellido="Tenant",
            dni="43111333",
            telefono="+5491100000003",
        )
    )
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-AJENO")
    )
    return {
        "consultorio_id": consultorio_id,
        "paciente": paciente,
        "profesional": profesional,
    }


# --- Alta -------------------------------------------------------------------


def test_alta_valida_toma_el_siguiente_orden(api_client, session_factory) -> None:
    """Expected: 201, pendiente and a growing identity order (RN-TU-05)."""
    base = _setup(session_factory)

    primera = _alta(api_client, base)
    assert primera.status_code == 201, primera.text
    assert primera.json()["estado"] == "pendiente"
    assert primera.json()["oferta_inicio"] is None
    assert primera.json()["turno_id"] is None

    segunda = _alta(
        api_client, base, paciente_id=str(base["paciente2"].id)
    )
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["orden"] > primera.json()["orden"]


@pytest.mark.parametrize("con_profesional", [False, True])
def test_alta_duplicada_devuelve_409(
    api_client, session_factory, con_profesional: bool
) -> None:
    """Business error: a patient waits once per service/professional."""
    base = _setup(session_factory)
    extra = (
        {"profesional_id": str(base["profesional"].id)}
        if con_profesional
        else {}
    )
    assert _alta(api_client, base, **extra).status_code == 201
    duplicada = _alta(api_client, base, **extra)
    assert duplicada.status_code == 409, duplicada.text
    assert len(_listar(api_client, base).json()) == 1


@pytest.mark.parametrize(
    "campo", ["paciente_id", "prestacion_id", "profesional_id"]
)
def test_alta_con_recurso_inexistente_devuelve_404(
    api_client, session_factory, campo: str
) -> None:
    """Business error: every referenced resource must exist in the tenant."""
    base = _setup(session_factory)
    respuesta = _alta(api_client, base, **{campo: str(uuid.uuid4())})
    assert respuesta.status_code == 404, respuesta.text


def test_alta_con_paciente_o_profesional_inactivo_devuelve_404(
    api_client, session_factory
) -> None:
    """Business error: soft-deleted resources cannot enter the queue."""
    base = _setup(session_factory)
    admin = bearer(base["actores"]["administrador"])
    assert (
        api_client.delete(
            f"/pacientes/{base['paciente'].id}", headers=admin
        ).status_code
        == 204
    )
    assert _alta(api_client, base).status_code == 404

    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-BAJA-LISTA"
        )
    )
    assert (
        api_client.delete(
            f"/profesionales/{otro_profesional.id}", headers=admin
        ).status_code
        == 204
    )
    assert (
        _alta(
            api_client,
            base,
            profesional_id=str(otro_profesional.id),
        ).status_code
        == 404
    )


def test_alta_de_recurso_de_otro_consultorio_devuelve_404(
    api_client, session_factory
) -> None:
    """Business error: the tenant boundary is enforced on alta (D11)."""
    base = _setup(session_factory)
    ajeno = _otro_consultorio(session_factory)

    assert (
        _alta(
            api_client, base, paciente_id=str(ajeno["paciente"].id)
        ).status_code
        == 404
    )
    assert (
        _alta(
            api_client,
            base,
            profesional_id=str(ajeno["profesional"].id),
        ).status_code
        == 404
    )


def test_alta_con_cuerpo_invalido_devuelve_422(
    api_client, session_factory
) -> None:
    """Edge: missing service, server-derived fields or extra keys are rejected."""
    base = _setup(session_factory)
    headers = bearer(base["actores"]["recepcionista"])

    sin_prestacion = _payload(base)
    del sin_prestacion["prestacion_id"]
    assert (
        api_client.post(
            "/lista-espera", json=sin_prestacion, headers=headers
        ).status_code
        == 422
    )
    for extra in ({"orden": 5}, {"estado": "ofrecido"}, {"campo_extra": 1}):
        assert (
            api_client.post(
                "/lista-espera",
                json=_payload(base, **extra),
                headers=headers,
            ).status_code
            == 422
        ), extra


# --- Listado y detalle ------------------------------------------------------


def test_listado_ordenado_y_con_filtros(api_client, session_factory) -> None:
    """Expected: FIFO order plus the declared filters and strict boundary."""
    base = _setup(session_factory)
    primera = _alta(api_client, base).json()
    segunda = _alta(
        api_client, base, paciente_id=str(base["paciente2"].id)
    ).json()
    tercera = _alta(
        api_client,
        base,
        prestacion_id=str(base["endo"]),
        profesional_id=str(base["profesional"].id),
    ).json()

    listado = _listar(api_client, base)
    assert listado.status_code == 200, listado.text
    assert [item["id"] for item in listado.json()] == [
        primera["id"],
        segunda["id"],
        tercera["id"],
    ]

    de_endo = _listar(api_client, base, prestacion_id=str(base["endo"]))
    assert [item["id"] for item in de_endo.json()] == [tercera["id"]]

    del_profesional = _listar(
        api_client, base, profesional_id=str(base["profesional"].id)
    )
    assert [item["id"] for item in del_profesional.json()] == [tercera["id"]]

    pendientes = _listar(api_client, base, estado="pendiente")
    assert len(pendientes.json()) == 3

    assert (
        _listar(api_client, base, convertido="si").status_code == 422
    )
    assert _listar(api_client, base, estado="inventado").status_code == 422


def test_detalle_de_una_entrada(api_client, session_factory) -> None:
    """Expected 200; unknown id is 404."""
    base = _setup(session_factory)
    entrada = _alta(api_client, base).json()

    detalle = api_client.get(
        f"/lista-espera/{entrada['id']}",
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["paciente_id"] == str(base["paciente"].id)
    assert detalle.json()["orden"] == entrada["orden"]

    inexistente = api_client.get(
        f"/lista-espera/{uuid.uuid4()}",
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert inexistente.status_code == 404


# --- Baja -------------------------------------------------------------------


def test_baja_de_pendiente_la_quita_y_libera_el_duplicado(
    api_client, session_factory
) -> None:
    """Expected: logical delete hides it and frees the partial unique index."""
    base = _setup(session_factory)
    entrada = _alta(api_client, base).json()

    baja = _baja(api_client, base, entrada["id"])
    assert baja.status_code == 200, baja.text
    assert baja.json()["is_active"] is False
    assert _listar(api_client, base).json() == []

    assert _alta(api_client, base).status_code == 201


def test_baja_de_una_entrada_ofrecida_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: an in-flight offer cannot be withdrawn."""
    base = _setup(session_factory)
    inicio = _hora(9)
    entrada_id = run(
        insertar_entrada(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente"].id,
            prestacion_id=base["cons"],
            estado="ofrecido",
            oferta_profesional_id=base["profesional"].id,
            oferta_sillon_id=base["sillon"].id,
            oferta_inicio=inicio,
            oferta_fin=inicio + timedelta(minutes=30),
            oferta_expira_en=datetime.now(
                ARGENTINA_OFFSET
            ) + timedelta(minutes=30),
        )
    )

    respuesta = _baja(api_client, base, entrada_id)
    assert respuesta.status_code == 409, respuesta.text
    detalle = api_client.get(
        f"/lista-espera/{entrada_id}",
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert detalle.json()["estado"] == "ofrecido"


def test_baja_de_una_entrada_inexistente_devuelve_404(
    api_client, session_factory
) -> None:
    """Business error: unknown or soft-deleted entries are not found."""
    base = _setup(session_factory)
    assert _baja(api_client, base, uuid.uuid4()).status_code == 404


# --- RBAC y aislamiento -----------------------------------------------------


def test_recepcion_administra_la_lista(api_client, session_factory) -> None:
    """Expected: reception creates, lists and withdraws (D11)."""
    base = _setup(session_factory)
    entrada = _alta(api_client, base)
    assert entrada.status_code == 201
    assert _listar(api_client, base).status_code == 200
    assert _baja(api_client, base, entrada.json()["id"]).status_code == 200


def test_odontologo_solo_lee_sus_propias_entradas(
    api_client, session_factory
) -> None:
    """Business error: the dentist cannot write and only sees own entries."""
    base = _setup(session_factory)
    propia = _alta(
        api_client,
        base,
        profesional_id=str(base["profesional"].id),
    ).json()
    sin_profesional = _alta(
        api_client, base, paciente_id=str(base["paciente2"].id)
    ).json()

    assert (
        _alta(api_client, base, actor="odontologo").status_code == 403
    )
    assert (
        _baja(api_client, base, propia["id"], actor="odontologo").status_code
        == 403
    )

    listado = _listar(api_client, base, actor="odontologo")
    assert listado.status_code == 200
    assert [item["id"] for item in listado.json()] == [propia["id"]]

    ajeno = api_client.get(
        f"/lista-espera/{sin_profesional['id']}",
        headers=bearer(base["actores"]["odontologo"]),
    )
    assert ajeno.status_code == 404


@pytest.mark.parametrize("rol", ["asistente", "auditor"])
def test_asistente_y_auditor_solo_leen(
    api_client, session_factory, rol: str
) -> None:
    """Business error: read-only roles can list but not mutate (D11)."""
    base = _setup(session_factory)
    entrada = _alta(api_client, base).json()

    assert _listar(api_client, base, actor=rol).status_code == 200
    assert _alta(api_client, base, actor=rol).status_code == 403
    assert _baja(api_client, base, entrada["id"], actor=rol).status_code == 403


def test_sin_token_devuelve_401(api_client, session_factory) -> None:
    """Business error: the waiting list is never public."""
    base = _setup(session_factory)
    entrada = _alta(api_client, base).json()

    assert api_client.get("/lista-espera").status_code == 401
    assert (
        api_client.post("/lista-espera", json=_payload(base)).status_code
        == 401
    )
    assert (
        api_client.delete(f"/lista-espera/{entrada['id']}").status_code == 401
    )


def test_entrada_de_otro_consultorio_no_es_visible(
    api_client, session_factory
) -> None:
    """Business error: cross-tenant access responds 404, never leaks data."""
    base = _setup(session_factory)
    ajeno = _otro_consultorio(session_factory)
    entrada_id = run(
        insertar_entrada(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente"].id,
            prestacion_id=base["cons"],
            profesional_id=ajeno["profesional"].id,
        )
    )
    admin = bearer(base["actores"]["administrador"])

    assert (
        api_client.get(f"/lista-espera/{entrada_id}", headers=admin).status_code
        == 404
    )
    assert (
        api_client.delete(f"/lista-espera/{entrada_id}", headers=admin).status_code
        == 404
    )
    assert _listar(api_client, base, actor="administrador").json() == []
