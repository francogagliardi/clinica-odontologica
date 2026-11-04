"""Informed consents: versioned catalogue, server-side hashes and append-only.

C-11 slice 2 (tasks 8.1-8.3): the client sends only tipo + texto_version, the
server resolves the canonical text, computes the digests and records the act;
correcting means registering another act, never updating the row.
"""

import hashlib
import uuid
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.domain import consentimientos
from app.infrastructure.uow import UnitOfWork
from tests.integration.clinica_helpers import (
    auditorias,
    otro_consultorio,
    setup_clinica,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_clinica(session_factory))


def _crear(
    api_client,
    actor,
    paciente_id: uuid.UUID,
    *,
    tipo: str = "procedimiento_invasivo",
    texto_version: str = "v1-2026-11",
    **extra: object,
):
    return api_client.post(
        f"/pacientes/{paciente_id}/consentimientos",
        json={"tipo": tipo, "texto_version": texto_version, **extra},
        headers=bearer(actor),
    )


def _listar(api_client, actor, paciente_id: uuid.UUID):
    return api_client.get(
        f"/pacientes/{paciente_id}/consentimientos", headers=bearer(actor)
    )


def _borrar_paciente(session_factory, paciente_id: uuid.UUID) -> None:
    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(paciente_id)
            assert paciente is not None
            await uow.pacientes.soft_delete(paciente)

    run(scenario())


async def _sqlstate_async(session_factory, statement, params):
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_registro_valido_calcula_hashes_en_el_servidor(
    api_client, session_factory
) -> None:
    """Expected: texto_hash/firma_ref are derived from the canonical text."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    created = _crear(api_client, odontologo, paciente.id)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["paciente_id"] == str(paciente.id)
    assert body["tipo"] == "procedimiento_invasivo"
    assert body["texto_version"] == "v1-2026-11"
    assert body["registrado_por"] == str(odontologo.id)
    assert "firma_imagen" not in body

    texto = consentimientos.texto_canonico("v1-2026-11")
    assert body["texto_hash"] == hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()
    fecha = datetime.fromisoformat(body["fecha"])
    _, firma_esperada = consentimientos.calcular_hashes(
        version="v1-2026-11", paciente_id=paciente.id, fecha=fecha
    )
    assert body["firma_ref"] == firma_esperada
    assert body["firma_ref"].startswith("sha256:")
    assert len(run(auditorias(session_factory, "consentimiento.registrar"))) == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"texto": "texto adulterado"},
        {"texto_hash": "a" * 64},
        {"firma_ref": "sha256:" + "b" * 64},
    ],
)
def test_cliente_no_puede_enviar_texto_ni_firmas(
    api_client, session_factory, extra: dict[str, str]
) -> None:
    """Business error: the server owns the wording and the digests."""
    data = _setup(session_factory)
    response = _crear(
        api_client,
        data["actores"]["odontologo"],
        data["paciente_propio"].id,
        **extra,
    )
    assert response.status_code == 422, response.text
    assert _listar(
        api_client,
        data["actores"]["administrador"],
        data["paciente_propio"].id,
    ).json() == []


def test_tipo_o_version_invalidos_422(api_client, session_factory) -> None:
    """Business error: tipo and texto_version are validated server-side."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    assert _crear(
        api_client, odontologo, paciente.id, tipo="otro"
    ).status_code == 422
    assert _crear(
        api_client, odontologo, paciente.id, texto_version="v0"
    ).status_code == 422


def test_paciente_inexistente_baja_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    """Business error: only an active patient of this consultorio is valid."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    assert _crear(
        api_client, odontologo, uuid.uuid4()
    ).status_code == 404

    ajeno = run(otro_consultorio(session_factory))
    assert _crear(
        api_client, odontologo, ajeno["paciente_id"]
    ).status_code == 404

    _borrar_paciente(session_factory, data["paciente_propio"].id)
    assert _crear(
        api_client, odontologo, data["paciente_propio"].id
    ).status_code == 404


def test_dos_consentimientos_del_mismo_tipo_y_version(
    api_client, session_factory
) -> None:
    """Expected: both are independent acts, listed newest first."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    primero = _crear(api_client, odontologo, paciente.id)
    segundo = _crear(api_client, odontologo, paciente.id)
    assert primero.status_code == 201, primero.text
    assert segundo.status_code == 201, segundo.text
    assert primero.json()["id"] != segundo.json()["id"]

    listado = _listar(
        api_client, data["actores"]["recepcionista"], paciente.id
    )
    assert listado.status_code == 200, listado.text
    bodies = listado.json()
    assert len(bodies) == 2
    assert bodies[0]["fecha"] >= bodies[1]["fecha"]


def test_update_y_delete_directo_p0001(api_client, session_factory) -> None:
    """Business error: a consent is append-only in PostgreSQL too."""
    data = _setup(session_factory)
    created = _crear(
        api_client, data["actores"]["odontologo"], data["paciente_propio"].id
    ).json()
    consentimiento_id = uuid.UUID(created["id"])

    assert run(
        _sqlstate_async(
            session_factory,
            "UPDATE consentimientos SET tipo = 'otro' WHERE id = :id",
            {"id": consentimiento_id},
        )
    ) == "P0001"
    assert run(
        _sqlstate_async(
            session_factory,
            "DELETE FROM consentimientos WHERE id = :id",
            {"id": consentimiento_id},
        )
    ) == "P0001"

    listado = _listar(
        api_client,
        data["actores"]["recepcionista"],
        data["paciente_propio"].id,
    )
    assert len(listado.json()) == 1


def test_rbac_de_consentimientos(api_client, session_factory) -> None:
    """RBAC: only the owning dentist writes; readers read their scope."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    for rol in ("administrador", "recepcionista", "auditor", "asistente"):
        assert _crear(
            api_client, data["actores"][rol], paciente.id
        ).status_code == 403, rol

    assert _crear(
        api_client, data["odontologo_ajeno"], paciente.id
    ).status_code == 403

    sin_token = api_client.post(
        f"/pacientes/{paciente.id}/consentimientos",
        json={"tipo": "procedimiento_invasivo", "texto_version": "v1-2026-11"},
    )
    assert sin_token.status_code == 401

    assert _crear(api_client, odontologo, paciente.id).status_code == 201

    for rol in ("administrador", "recepcionista", "auditor"):
        assert _listar(
            api_client, data["actores"][rol], paciente.id
        ).status_code == 200

    assert _listar(
        api_client, data["actores"]["asistente"], paciente.id
    ).status_code == 403

    en_sala = data["paciente_en_sala"]
    assert _crear(api_client, odontologo, en_sala.id).status_code == 201
    assert _listar(
        api_client, data["actores"]["asistente"], en_sala.id
    ).status_code == 200


def test_listado_de_paciente_inexistente_404(
    api_client, session_factory
) -> None:
    """Business error: listing an unknown patient is not an empty list."""
    data = _setup(session_factory)
    response = _listar(
        api_client, data["actores"]["administrador"], uuid.uuid4()
    )
    assert response.status_code == 404, response.text
