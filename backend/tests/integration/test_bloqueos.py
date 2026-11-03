"""Blocks: XOR resource, valid range, ownership and overlap tolerance (C-04)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.integration.helpers import run
from tests.integration.recursos_helpers import (
    bearer,
    consultorio_demo_id,
    create_actor,
    create_profesional,
    create_sillon,
    seed_demo,
)

DESDE = datetime(2026, 11, 3, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
HASTA = DESDE + timedelta(hours=2)


def _payload(
    *,
    profesional_id: uuid.UUID | None = None,
    sillon_id: uuid.UUID | None = None,
    desde: datetime = DESDE,
    hasta: datetime = HASTA,
) -> dict[str, object]:
    return {
        "profesional_id": str(profesional_id) if profesional_id else None,
        "sillon_id": str(sillon_id) if sillon_id else None,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "motivo": "Licencia",
    }


def _setup(session_factory) -> dict[str, object]:
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
    propio = run(
        create_profesional(
            session_factory,
            consultorio_id,
            "MP-PROPIO",
            usuario_id=actores["odontologo"].id,
        )
    )
    ajeno = run(
        create_profesional(session_factory, consultorio_id, "MP-AJENO")
    )
    sillon = run(create_sillon(session_factory, consultorio_id, "Box Bloqueo"))
    return {
        "actores": actores,
        "propio": propio,
        "ajeno": ajeno,
        "sillon": sillon,
    }


def test_recepcion_crea_bloqueo_de_profesional(
    api_client, session_factory
) -> None:
    """Expected: reception creates a professional block and reads it (201/200)."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["recepcionista"])

    created = api_client.post(
        "/bloqueos",
        json=_payload(profesional_id=ctx["propio"].id),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    bloqueo = created.json()
    assert bloqueo["profesional_id"] == str(ctx["propio"].id)
    assert bloqueo["sillon_id"] is None

    listed = api_client.get(
        f"/bloqueos?profesional_id={ctx['propio'].id}", headers=headers
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [bloqueo["id"]]


def test_bloqueo_con_dos_o_ningun_recurso(
    api_client, session_factory
) -> None:
    """Business error: exactly one resource must be informed (XOR)."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["administrador"])

    assert (
        api_client.post(
            "/bloqueos",
            json=_payload(
                profesional_id=ctx["propio"].id,
                sillon_id=ctx["sillon"].id,
            ),
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        api_client.post(
            "/bloqueos", json=_payload(), headers=headers
        ).status_code
        == 422
    )


def test_rango_temporal_invalido(api_client, session_factory) -> None:
    """Business error: hasta must be strictly after desde."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["administrador"])

    for hasta in (DESDE, DESDE - timedelta(minutes=1)):
        response = api_client.post(
            "/bloqueos",
            json=_payload(
                profesional_id=ctx["propio"].id, hasta=hasta
            ),
            headers=headers,
        )
        assert response.status_code == 422, response.text


def test_bloqueo_con_recurso_inexistente_o_inactivo(
    api_client, session_factory
) -> None:
    """Business error: unknown or soft-deleted resources return 404."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["administrador"])

    assert (
        api_client.post(
            "/bloqueos",
            json=_payload(profesional_id=uuid.uuid4()),
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/bloqueos",
            json=_payload(sillon_id=uuid.uuid4()),
            headers=headers,
        ).status_code
        == 404
    )

    assert (
        api_client.delete(
            f"/sillones/{ctx['sillon'].id}", headers=headers
        ).status_code
        == 204
    )
    assert (
        api_client.post(
            "/bloqueos",
            json=_payload(sillon_id=ctx["sillon"].id),
            headers=headers,
        ).status_code
        == 404
    )


def test_bloqueos_solapados_se_permiten(api_client, session_factory) -> None:
    """Edge: overlapping blocks are stored and both exclude the range."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["administrador"])
    primero = _payload(profesional_id=ctx["propio"].id)
    segundo = _payload(
        profesional_id=ctx["propio"].id,
        desde=DESDE + timedelta(hours=1),
        hasta=HASTA + timedelta(hours=1),
    )

    assert (
        api_client.post("/bloqueos", json=primero, headers=headers).status_code
        == 201
    )
    assert (
        api_client.post("/bloqueos", json=segundo, headers=headers).status_code
        == 201
    )


def test_odontologo_gestiona_su_propio_profesional(
    api_client, session_factory
) -> None:
    """Expected: a dentist creates and deletes a block of their professional."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["odontologo"])

    created = api_client.post(
        "/bloqueos",
        json=_payload(profesional_id=ctx["propio"].id),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert (
        api_client.delete(
            f"/bloqueos/{created.json()['id']}", headers=headers
        ).status_code
        == 204
    )


def test_odontologo_no_bloquea_a_otro_profesional(
    api_client, session_factory
) -> None:
    """Business error: ownership is limited to their own professional."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"]["odontologo"])
    assert (
        api_client.post(
            "/bloqueos",
            json=_payload(profesional_id=ctx["ajeno"].id),
            headers=headers,
        ).status_code
        == 403
    )

    # Deleting someone else's block is also denied.
    admin = bearer(ctx["actores"]["administrador"])
    created = api_client.post(
        "/bloqueos",
        json=_payload(profesional_id=ctx["ajeno"].id),
        headers=admin,
    )
    assert created.status_code == 201
    assert (
        api_client.delete(
            f"/bloqueos/{created.json()['id']}", headers=headers
        ).status_code
        == 403
    )


def test_odontologo_no_bloquea_sillones(api_client, session_factory) -> None:
    """Business error: ownership is defined over a professional, not a chair."""
    ctx = _setup(session_factory)
    response = api_client.post(
        "/bloqueos",
        json=_payload(sillon_id=ctx["sillon"].id),
        headers=bearer(ctx["actores"]["odontologo"]),
    )
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("rol", ["asistente", "auditor"])
def test_asistente_y_auditor_no_escriben_bloqueos(
    api_client, session_factory, rol: str
) -> None:
    """Business error: assistants and auditors are read-only for blocks."""
    ctx = _setup(session_factory)
    headers = bearer(ctx["actores"][rol])
    assert (
        api_client.post(
            "/bloqueos",
            json=_payload(profesional_id=ctx["propio"].id),
            headers=headers,
        ).status_code
        == 403
    )
    assert api_client.get("/bloqueos", headers=headers).status_code == 200


def test_odontologo_no_reclama_profesional_sin_usuario(
    api_client, session_factory
) -> None:
    """Edge: a professional without linked user cannot be claimed."""
    ctx = _setup(session_factory)
    response = api_client.post(
        "/bloqueos",
        json=_payload(profesional_id=ctx["ajeno"].id),
        headers=bearer(ctx["actores"]["odontologo"]),
    )
    assert response.status_code == 403, response.text
