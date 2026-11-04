"""Evolution endpoints: draft, signature, rectification and immutability.

C-11 slice 2 (tasks 5.1-5.4): the draft is editable, the signed evolution is
frozen in the API and in PostgreSQL, and a correction is always a new linked
evolution that never rewrites the original (RN-CL-04).
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.clinica_helpers import (
    auditorias,
    insertar_evolucion_db,
    setup_clinica,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_clinica(session_factory))


def _abrir(api_client, actor, paciente_id: uuid.UUID) -> dict[str, object]:
    response = api_client.post(
        "/historia-clinica",
        json={"paciente_id": str(paciente_id)},
        headers=bearer(actor),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _crear(
    api_client,
    actor,
    historia_id: str,
    texto: str = "Evolución de prueba",
    **extra: object,
):
    return api_client.post(
        f"/historia-clinica/{historia_id}/evoluciones",
        json={"texto": texto, **extra},
        headers=bearer(actor),
    )


def _firmar(api_client, actor, historia_id: str, evolucion_id: str, body=None):
    return api_client.post(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}/firmar",
        json={} if body is None else body,
        headers=bearer(actor),
    )


def _detalle(api_client, actor, historia_id: str, evolucion_id: str):
    return api_client.get(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
        headers=bearer(actor),
    )


def _editar(api_client, actor, historia_id: str, evolucion_id: str, texto=None):
    payload = {"texto": texto} if texto is not None else {}
    return api_client.put(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
        json=payload,
        headers=bearer(actor),
    )


def _descartar(api_client, actor, historia_id: str, evolucion_id: str):
    return api_client.delete(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
        headers=bearer(actor),
    )


def _audit_count(session_factory, accion: str) -> int:
    return len(run(auditorias(session_factory, accion)))


async def _sqlstate_async(
    session_factory, statement: str, params: dict[str, object]
) -> str | None:
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def _sqlstate_directo(
    session_factory, statement: str, params: dict[str, object]
) -> str | None:
    return run(_sqlstate_async(session_factory, statement, params))


def test_alta_de_borrador(api_client, session_factory) -> None:
    """Expected: a new evolution is a draft with the linked professional."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    created = _crear(api_client, odontologo, historia["id"])
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["historia_id"] == historia["id"]
    assert body["profesional_id"] == str(data["profesional"].id)
    assert body["creado_por"] == str(odontologo.id)
    assert body["texto"] == "Evolución de prueba"
    assert body["firmada"] is False
    assert body["firmada_por"] is None
    assert body["fecha_firma"] is None
    assert body["rectifica_a"] is None
    assert body["rectificada_por"] is None
    assert body["fecha"]

    assert _audit_count(session_factory, "evolucion.crear") == 1


def test_edicion_del_borrador_por_su_autor(api_client, session_factory) -> None:
    """Expected: the author edits the text and it is still a draft."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(api_client, odontologo, historia["id"]).json()

    updated = _editar(
        api_client,
        odontologo,
        historia["id"],
        evolucion["id"],
        "Texto corregido",
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["texto"] == "Texto corregido"
    assert updated.json()["firmada"] is False
    assert _audit_count(session_factory, "evolucion.editar") == 1


def test_firma_fija_autor_fecha_y_texto(api_client, session_factory) -> None:
    """Expected: signing freezes the text and records who/when."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(
        api_client, odontologo, historia["id"], "Texto que se firma"
    ).json()

    signed = _firmar(
        api_client, odontologo, historia["id"], evolucion["id"]
    )
    assert signed.status_code == 200, signed.text
    body = signed.json()
    assert body["firmada"] is True
    assert body["firmada_por"] == str(odontologo.id)
    assert body["fecha_firma"] is not None
    assert body["texto"] == "Texto que se firma"
    assert _audit_count(session_factory, "evolucion.firmar") == 1


def test_firma_repetida_es_idempotente(api_client, session_factory) -> None:
    """Edge: signing twice returns 200 without touching the signature data."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(api_client, odontologo, historia["id"]).json()

    first = _firmar(api_client, odontologo, historia["id"], evolucion["id"])
    assert first.status_code == 200, first.text
    second = _firmar(api_client, odontologo, historia["id"], evolucion["id"])
    assert second.status_code == 200, second.text
    assert second.json()["fecha_firma"] == first.json()["fecha_firma"]
    assert second.json()["firmada_por"] == first.json()["firmada_por"]
    assert _audit_count(session_factory, "evolucion.firmar") == 1


def test_firma_con_cuerpo_inesperado_422(api_client, session_factory) -> None:
    """Business error: signature accepts no fields, not even texto/fecha_firma."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(api_client, odontologo, historia["id"]).json()

    for extra in ({"texto": "colado"}, {"fecha_firma": "2026-11-04T10:00:00Z"}):
        rejected = _firmar(
            api_client,
            odontologo,
            historia["id"],
            evolucion["id"],
            body=extra,
        )
        assert rejected.status_code == 422, (extra, rejected.text)

    detalle = _detalle(
        api_client, odontologo, historia["id"], evolucion["id"]
    )
    assert detalle.json()["firmada"] is False


def test_firmada_rechaza_edicion_y_borrado_403(
    api_client, session_factory
) -> None:
    """Business error: the API refuses to touch a signed evolution."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(
        api_client, odontologo, historia["id"], "Texto firmado"
    ).json()
    assert _firmar(
        api_client, odontologo, historia["id"], evolucion["id"]
    ).status_code == 200

    intento = _editar(
        api_client, odontologo, historia["id"], evolucion["id"], "Alterado"
    )
    assert intento.status_code == 403, intento.text
    borrado = _descartar(
        api_client, odontologo, historia["id"], evolucion["id"]
    )
    assert borrado.status_code == 403, borrado.text

    detalle = _detalle(
        api_client, odontologo, historia["id"], evolucion["id"]
    )
    assert detalle.status_code == 200
    assert detalle.json()["texto"] == "Texto firmado"
    assert _audit_count(session_factory, "evolucion.editar") == 0
    assert _audit_count(session_factory, "evolucion.descartar") == 0


def test_firmada_rechaza_update_y_delete_directo_p0001(
    api_client, session_factory
) -> None:
    """Business error: PostgreSQL also blocks direct SQL on signed rows."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(
        api_client, odontologo, historia["id"], "Original"
    ).json()
    assert _firmar(
        api_client, odontologo, historia["id"], evolucion["id"]
    ).status_code == 200

    assert _sqlstate_directo(
        session_factory,
        "UPDATE evoluciones SET texto = 'adulterado' WHERE id = :id",
        {"id": uuid.UUID(evolucion["id"])},
    ) == "P0001"
    assert _sqlstate_directo(
        session_factory,
        "DELETE FROM evoluciones WHERE id = :id",
        {"id": uuid.UUID(evolucion["id"])},
    ) == "P0001"

    detalle = _detalle(
        api_client, odontologo, historia["id"], evolucion["id"]
    )
    assert detalle.json()["texto"] == "Original"


def test_descarte_de_borrador_204(api_client, session_factory) -> None:
    """Expected: a draft can be discarded; it disappears from the listing."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    evolucion = _crear(api_client, odontologo, historia["id"]).json()

    deleted = _descartar(
        api_client, odontologo, historia["id"], evolucion["id"]
    )
    assert deleted.status_code == 204, deleted.text

    listado = api_client.get(
        f"/historia-clinica/{historia['id']}/evoluciones",
        headers=bearer(odontologo),
    )
    assert listado.status_code == 200
    assert listado.json() == []
    assert _audit_count(session_factory, "evolucion.descartar") == 1


def test_rectificatoria_enlazada_y_original_intacta(
    api_client, session_factory
) -> None:
    """Expected: a signed evolution is corrected by a new linked evolution."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    original = _crear(
        api_client, odontologo, historia["id"], "Texto original"
    ).json()
    assert _firmar(
        api_client, odontologo, historia["id"], original["id"]
    ).status_code == 200

    rectificatoria = _crear(
        api_client,
        odontologo,
        historia["id"],
        "Texto rectificado",
        rectifica_a=original["id"],
    )
    assert rectificatoria.status_code == 201, rectificatoria.text
    body = rectificatoria.json()
    assert body["rectifica_a"] == original["id"]
    assert body["firmada"] is False
    assert body["rectificada_por"] is None

    original_antes = _detalle(
        api_client, odontologo, historia["id"], original["id"]
    ).json()
    assert original_antes["texto"] == "Texto original"
    assert original_antes["firmada"] is True
    assert original_antes["rectificada_por"] is None
    assert _audit_count(session_factory, "evolucion.rectificar") == 1
    assert _audit_count(session_factory, "evolucion.crear") == 1

    assert _firmar(
        api_client, odontologo, historia["id"], body["id"]
    ).status_code == 200

    original_despues = _detalle(
        api_client, odontologo, historia["id"], original["id"]
    ).json()
    assert original_despues["texto"] == "Texto original"
    assert original_despues["rectificada_por"] == body["id"]


def test_rectificar_borrador_422(api_client, session_factory) -> None:
    """Business error: only signed evolutions can be rectified."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    borrador = _crear(api_client, odontologo, historia["id"]).json()

    rechazada = _crear(
        api_client,
        odontologo,
        historia["id"],
        "No debería crearse",
        rectifica_a=borrador["id"],
    )
    assert rechazada.status_code == 422, rechazada.text
    assert _audit_count(session_factory, "evolucion.rectificar") == 0


def test_rectificar_evolucion_de_otra_historia_422(
    api_client, session_factory
) -> None:
    """Business error: a rectification cannot cross clinical histories."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia_a = _abrir(api_client, odontologo, data["paciente_propio"].id)
    historia_b = _abrir(api_client, odontologo, data["paciente_en_sala"].id)
    firmada_b = _crear(
        api_client, odontologo, historia_b["id"], "Otra historia"
    ).json()
    assert _firmar(
        api_client, odontologo, historia_b["id"], firmada_b["id"]
    ).status_code == 200

    rechazada = _crear(
        api_client,
        odontologo,
        historia_a["id"],
        "Cruzada",
        rectifica_a=firmada_b["id"],
    )
    assert rechazada.status_code == 422, rechazada.text


def test_rectificar_inexistente_404(api_client, session_factory) -> None:
    """Business error: unknown reference is 404, not 422."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    response = _crear(
        api_client,
        odontologo,
        historia["id"],
        "Huérfana",
        rectifica_a=str(uuid.uuid4()),
    )
    assert response.status_code == 404, response.text


def test_segunda_rectificatoria_activa_409_y_23505(
    api_client, session_factory
) -> None:
    """Business rule: only one active correction per signed evolution."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    original = _crear(api_client, odontologo, historia["id"], "Original").json()
    assert _firmar(
        api_client, odontologo, historia["id"], original["id"]
    ).status_code == 200

    primera = _crear(
        api_client,
        odontologo,
        historia["id"],
        "Primera",
        rectifica_a=original["id"],
    )
    assert primera.status_code == 201, primera.text
    segunda = _crear(
        api_client,
        odontologo,
        historia["id"],
        "Segunda",
        rectifica_a=original["id"],
    )
    assert segunda.status_code == 409, segunda.text

    with pytest.raises(IntegrityError) as error:
        run(
            insertar_evolucion_db(
                session_factory,
                historia_id=uuid.UUID(historia["id"]),
                profesional_id=data["profesional"].id,
                creado_por=odontologo.id,
                texto="Directa",
                rectifica_a=uuid.UUID(original["id"]),
            )
        )
    assert sqlstate(error.value) == "23505"


def test_cadena_de_rectificatorias(api_client, session_factory) -> None:
    """Edge: a signed rectification can itself be corrected, link by link."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    original = _crear(api_client, odontologo, historia["id"], "V1").json()
    assert _firmar(
        api_client, odontologo, historia["id"], original["id"]
    ).status_code == 200

    r1 = _crear(
        api_client,
        odontologo,
        historia["id"],
        "V2",
        rectifica_a=original["id"],
    ).json()
    assert _firmar(
        api_client, odontologo, historia["id"], r1["id"]
    ).status_code == 200

    r2 = _crear(
        api_client,
        odontologo,
        historia["id"],
        "V3",
        rectifica_a=r1["id"],
    )
    assert r2.status_code == 201, r2.text
    r2_body = r2.json()
    assert _firmar(
        api_client, odontologo, historia["id"], r2_body["id"]
    ).status_code == 200

    r1_leida = _detalle(
        api_client, odontologo, historia["id"], r1["id"]
    ).json()
    assert r1_leida["rectificada_por"] == r2_body["id"]
    assert r1_leida["texto"] == "V2"

    original_leida = _detalle(
        api_client, odontologo, historia["id"], original["id"]
    ).json()
    assert original_leida["rectificada_por"] == r1["id"]
    assert original_leida["texto"] == "V1"


def test_rbac_de_evoluciones(api_client, session_factory) -> None:
    """RBAC: dentist writes own; assistant edits in-room drafts; others read."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    borrador = _crear(api_client, odontologo, historia["id"]).json()

    asistente = data["actores"]["asistente"]
    ajeno = data["odontologo_ajeno"]

    for rol in ("administrador", "recepcionista", "auditor"):
        lectura = api_client.get(
            f"/historia-clinica/{historia['id']}/evoluciones",
            headers=bearer(data["actores"][rol]),
        )
        assert lectura.status_code == 200, (rol, lectura.text)
        assert _crear(
            api_client, data["actores"][rol], historia["id"]
        ).status_code == 403

    # Patient is reservado, not in the chair: assistant cannot read/edit.
    assert api_client.get(
        f"/historia-clinica/{historia['id']}/evoluciones",
        headers=bearer(asistente),
    ).status_code == 403
    assert _editar(
        api_client, asistente, historia["id"], borrador["id"], "Asistente"
    ).status_code == 403

    # Foreign dentist and no token.
    assert _crear(api_client, ajeno, historia["id"]).status_code == 403
    firmada = _crear(api_client, odontologo, historia["id"]).json()
    assert _firmar(
        api_client, odontologo, historia["id"], firmada["id"]
    ).status_code == 200
    assert _firmar(
        api_client, ajeno, historia["id"], firmada["id"]
    ).status_code == 403
    assert _crear(api_client, odontologo, historia["id"]).status_code == 201
    sin_token = api_client.get(
        f"/historia-clinica/{historia['id']}/evoluciones"
    )
    assert sin_token.status_code == 401

    # In-room assistant may read and edit a draft, but never create or sign.
    historia_sala = _abrir(
        api_client, odontologo, data["paciente_en_sala"].id
    )
    borrador_sala = _crear(
        api_client, odontologo, historia_sala["id"], "Borrador en sala"
    ).json()
    assert api_client.get(
        f"/historia-clinica/{historia_sala['id']}/evoluciones",
        headers=bearer(asistente),
    ).status_code == 200
    editado = _editar(
        api_client,
        asistente,
        historia_sala["id"],
        borrador_sala["id"],
        "Editado por asistente",
    )
    assert editado.status_code == 200, editado.text
    assert editado.json()["texto"] == "Editado por asistente"
    assert _crear(
        api_client, asistente, historia_sala["id"]
    ).status_code == 403
    assert _firmar(
        api_client, asistente, historia_sala["id"], borrador_sala["id"]
    ).status_code == 403


def test_evolucion_de_otra_historia_404(api_client, session_factory) -> None:
    """Business error: the evolution id must belong to the path's history."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia_a = _abrir(api_client, odontologo, data["paciente_propio"].id)
    historia_b = _abrir(api_client, odontologo, data["paciente_en_sala"].id)
    evolucion_a = _crear(api_client, odontologo, historia_a["id"]).json()

    response = _detalle(
        api_client, odontologo, historia_b["id"], evolucion_a["id"]
    )
    assert response.status_code == 404, response.text
