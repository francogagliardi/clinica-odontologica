"""Clinical attachments: multipart upload, security and authenticated download.

C-11 slice 2 (tasks 7.1-7.4): BYTEA in PostgreSQL, 5 MB ceiling, MIME allow-list
with magic-byte verification, sanitised filename and a download that never
exposes server paths.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.uow import UnitOfWork
from tests.integration.clinica_helpers import (
    auditorias,
    insertar_historia_db,
    otro_consultorio,
    setup_clinica,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.recursos_helpers import bearer

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
PDF = b"%PDF-1.7\n" + b"\x00" * 8
LIMITE = 5 * 1024 * 1024


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


def _subir(
    api_client,
    actor,
    historia_id,
    *,
    nombre: str = "foto.png",
    contenido: bytes = PNG,
    mime: str = "image/png",
    extra: dict[str, object] | None = None,
):
    data: dict[str, object] = {}
    if historia_id is not None:
        data["historia_id"] = str(historia_id)
    if extra:
        data.update(extra)
    return api_client.post(
        "/adjuntos",
        data=data,
        files={"archivo": (nombre, contenido, mime)},
        headers=bearer(actor),
    )


async def _adjunto_db(session_factory, adjunto_id: str):
    async with UnitOfWork(session_factory) as uow:
        return await uow.adjuntos.get(uuid.UUID(adjunto_id))


async def _sqlstate_async(session_factory, statement, params):
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_subida_png_persiste_los_bytes(api_client, session_factory) -> None:
    """Expected: a real PNG is stored byte by byte in PostgreSQL."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    created = _subir(api_client, odontologo, historia["id"])
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["historia_id"] == historia["id"]
    assert body["nombre"] == "foto.png"
    assert body["mime"] == "image/png"
    assert body["tamano"] == len(PNG)
    assert body["subido_por"] == str(odontologo.id)

    fila = run(_adjunto_db(session_factory, body["id"]))
    assert fila is not None and fila.contenido == PNG
    assert len(run(auditorias(session_factory, "adjunto.crear"))) == 1


def test_subida_pdf_valida(api_client, session_factory) -> None:
    """Expected: PDF is the other real clinical document type allowed."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    created = _subir(
        api_client,
        odontologo,
        historia["id"],
        nombre="informe.pdf",
        contenido=PDF,
        mime="application/pdf",
    )
    assert created.status_code == 201, created.text
    assert created.json()["mime"] == "application/pdf"


def test_multipart_sin_historia_o_con_parte_extra_422(
    api_client, session_factory
) -> None:
    """Business error: the multipart contract is strict."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    sin_historia = api_client.post(
        "/adjuntos",
        files={"archivo": ("foto.png", PNG, "image/png")},
        headers=bearer(odontologo),
    )
    assert sin_historia.status_code == 422, sin_historia.text

    uuid_invalido = _subir(
        api_client, odontologo, historia["id"], extra={"historia_id": "x"}
    )
    assert uuid_invalido.status_code == 422, uuid_invalido.text

    parte_extra = _subir(
        api_client, odontologo, historia["id"], extra={"extra": "sorpresa"}
    )
    assert parte_extra.status_code == 422, parte_extra.text


def test_historia_inexistente_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    """Business error: attachments only hang from an active own history."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    inexistente = _subir(api_client, odontologo, uuid.uuid4())
    assert inexistente.status_code == 404, inexistente.text

    ajeno = run(otro_consultorio(session_factory))
    historia_ajena = run(
        insertar_historia_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente_id"],
            abierta_por=data["actores"]["administrador"].id,
        )
    )
    otra = _subir(api_client, odontologo, historia_ajena)
    assert otra.status_code == 404, otra.text


@pytest.mark.parametrize(
    ("nombre", "contenido", "mime"),
    [
        ("malware.exe", PNG, "application/x-msdownload"),
        ("pagina.html", b"<html></html>", "text/html"),
        ("malware.exe", PNG, "image/png"),
        ("foto.png", PDF, "image/png"),
        ("foto.png", b"PK\x03\x04datos", "image/png"),
    ],
)
def test_contenido_no_permitido_422(
    api_client, session_factory, nombre: str, contenido: bytes, mime: str
) -> None:
    """Business error: MIME allow-list, extension and magic bytes must agree."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    rejected = _subir(
        api_client,
        odontologo,
        historia["id"],
        nombre=nombre,
        contenido=contenido,
        mime=mime,
    )
    assert rejected.status_code == 422, (nombre, mime, rejected.text)


def test_archivo_mayor_a_cinco_mb_422(api_client, session_factory) -> None:
    """Business error: the API rejects before persisting an oversized file."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    grande = b"%PDF" + b"0" * LIMITE

    rejected = _subir(
        api_client,
        odontologo,
        historia["id"],
        nombre="grande.pdf",
        contenido=grande,
        mime="application/pdf",
    )
    assert rejected.status_code == 422, rejected.text

    listado = api_client.get(
        f"/historia-clinica/{historia['id']}/adjuntos",
        headers=bearer(odontologo),
    )
    assert listado.json() == []


def test_check_de_tamano_rechaza_insert_directo(
    api_client, session_factory
) -> None:
    """Business error: PostgreSQL also caps the size at 5 MB."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    estado = run(
        _sqlstate_async(
            session_factory,
            "INSERT INTO adjuntos "
            "(id, historia_id, nombre, mime, tamano, contenido, subido_por) "
            "VALUES (:id, :historia_id, 'grande.pdf', "
            "'application/pdf', :tamano, :contenido, :usuario)",
            {
                "id": uuid.uuid4(),
                "historia_id": uuid.UUID(historia["id"]),
                "tamano": LIMITE + 1,
                "contenido": b"x",
                "usuario": odontologo.id,
            },
        )
    )
    assert estado == "23514"


def test_nombre_con_path_traversal_se_sanea(
    api_client, session_factory
) -> None:
    """Business error: a traversal name is stored as a plain basename."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    created = _subir(
        api_client,
        odontologo,
        historia["id"],
        nombre="..\\..\\etc\\passwd",
    )
    assert created.status_code == 201, created.text
    assert created.json()["nombre"] == "passwd"

    descarga = api_client.get(
        f"/adjuntos/{created.json()['id']}", headers=bearer(odontologo)
    )
    disposition = descarga.headers["content-disposition"]
    assert "passwd" in disposition
    assert ".." not in disposition
    assert "/" not in disposition and "\\" not in disposition


def test_descarga_autenticada_devuelve_bytes_y_headers(
    api_client, session_factory
) -> None:
    """Expected: same MIME/bytes, attachment and nosniff."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    created = _subir(api_client, odontologo, historia["id"]).json()

    descarga = api_client.get(
        f"/adjuntos/{created['id']}", headers=bearer(odontologo)
    )
    assert descarga.status_code == 200, descarga.text
    assert descarga.content == PNG
    assert descarga.headers["content-type"].startswith("image/png")
    assert descarga.headers["x-content-type-options"] == "nosniff"
    assert descarga.headers["content-disposition"].startswith("attachment")


def test_descarga_sin_token_o_inexistente(api_client, session_factory) -> None:
    """Business error: no token is 401; unknown id is 404."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    created = _subir(api_client, odontologo, historia["id"]).json()

    sin_token = api_client.get(f"/adjuntos/{created['id']}")
    assert sin_token.status_code == 401
    inexistente = api_client.get(
        f"/adjuntos/{uuid.uuid4()}", headers=bearer(odontologo)
    )
    assert inexistente.status_code == 404


def test_listado_por_historia_sin_bytes(api_client, session_factory) -> None:
    """Expected: metadata only, newest first, scoped to the history."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    primero = _subir(api_client, odontologo, historia["id"]).json()
    segundo = _subir(
        api_client,
        odontologo,
        historia["id"],
        nombre="informe.pdf",
        contenido=PDF,
        mime="application/pdf",
    ).json()

    listado = api_client.get(
        f"/historia-clinica/{historia['id']}/adjuntos",
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert listado.status_code == 200, listado.text
    bodies = listado.json()
    assert {fila["id"] for fila in bodies} == {primero["id"], segundo["id"]}
    assert all("contenido" not in fila for fila in bodies)


def test_rbac_de_adjuntos(api_client, session_factory) -> None:
    """RBAC: only the owning dentist writes; readers read their scope."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    for rol in ("administrador", "recepcionista", "auditor", "asistente"):
        assert _subir(
            api_client, data["actores"][rol], historia["id"]
        ).status_code == 403, rol

    assert _subir(
        api_client, data["odontologo_ajeno"], historia["id"]
    ).status_code == 403

    listado = api_client.get(
        f"/historia-clinica/{historia['id']}/adjuntos",
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert listado.status_code == 200

    sin_token = api_client.get(
        f"/historia-clinica/{historia['id']}/adjuntos"
    )
    assert sin_token.status_code == 401

    historia_sala = _abrir(
        api_client, odontologo, data["paciente_en_sala"].id
    )
    assert api_client.get(
        f"/historia-clinica/{historia_sala['id']}/adjuntos",
        headers=bearer(data["actores"]["asistente"]),
    ).status_code == 200
    assert api_client.get(
        f"/historia-clinica/{historia['id']}/adjuntos",
        headers=bearer(data["actores"]["asistente"]),
    ).status_code == 403
