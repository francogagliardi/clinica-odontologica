"""Cross-cutting RBAC and audit matrix for the clinical record (C-11 slice 3).

This file is deliberately end-to-end: it walks every role over the real routes
and verifies that each clinical write appends exactly one audit row with the
authenticated user, while rejected writes append none.
"""

import uuid

from tests.integration.clinica_helpers import auditorias, setup_clinica
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
ACCIONES = (
    "historia_clinica.crear",
    "evolucion.crear",
    "evolucion.editar",
    "evolucion.descartar",
    "evolucion.firmar",
    "evolucion.rectificar",
    "odontograma.versionar",
    "adjunto.crear",
    "consentimiento.registrar",
)
ENTIDADES = {
    "historia_clinica.crear": "historia_clinica",
    "evolucion.crear": "evolucion",
    "evolucion.editar": "evolucion",
    "evolucion.descartar": "evolucion",
    "evolucion.firmar": "evolucion",
    "evolucion.rectificar": "evolucion",
    "odontograma.versionar": "odontograma",
    "adjunto.crear": "adjunto",
    "consentimiento.registrar": "consentimiento",
}


def _setup(session_factory) -> dict[str, object]:
    return run(setup_clinica(session_factory))


def _abrir(api_client, actor, paciente_id: uuid.UUID):
    return api_client.post(
        "/historia-clinica",
        json={"paciente_id": str(paciente_id)},
        headers=bearer(actor),
    )


def _evolucion(api_client, actor, historia_id, texto: str = "Borrador"):
    return api_client.post(
        f"/historia-clinica/{historia_id}/evoluciones",
        json={"texto": texto},
        headers=bearer(actor),
    )


def _editar(api_client, actor, historia_id, evolucion_id, texto: str):
    return api_client.put(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
        json={"texto": texto},
        headers=bearer(actor),
    )


def _firmar(api_client, actor, historia_id, evolucion_id):
    return api_client.post(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}/firmar",
        json={},
        headers=bearer(actor),
    )


def _descartar(api_client, actor, historia_id, evolucion_id):
    return api_client.delete(
        f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
        headers=bearer(actor),
    )


def _hallazgo(api_client, actor, historia_id, pieza: int = 16):
    return api_client.post(
        f"/historia-clinica/{historia_id}/odontograma/hallazgos",
        json={
            "pieza": pieza,
            "cara": "mesial",
            "estado": "caries",
            "cie10": "K02.1",
        },
        headers=bearer(actor),
    )


def _adjunto(api_client, actor, historia_id):
    return api_client.post(
        "/adjuntos",
        data={"historia_id": str(historia_id)},
        files={"archivo": ("foto.png", PNG, "image/png")},
        headers=bearer(actor),
    )


def _consentimiento(api_client, actor, paciente_id):
    return api_client.post(
        f"/pacientes/{paciente_id}/consentimientos",
        json={"tipo": "procedimiento_invasivo", "texto_version": "v1-2026-11"},
        headers=bearer(actor),
    )


def _expediente(api_client, data):
    """Create a complete clinical record as the owning dentist."""
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    assert historia.status_code == 201, historia.text
    historia_id = historia.json()["id"]
    evolucion = _evolucion(api_client, odontologo, historia_id)
    assert evolucion.status_code == 201, evolucion.text
    assert _hallazgo(api_client, odontologo, historia_id).status_code == 201
    assert _adjunto(api_client, odontologo, historia_id).status_code == 201
    assert _consentimiento(
        api_client, odontologo, data["paciente_propio"].id
    ).status_code == 201
    return historia_id, evolucion.json()["id"]


def _lecturas(api_client, actor, historia_id, paciente_id):
    headers = bearer(actor)
    return [
        api_client.get(f"/historia-clinica/{historia_id}", headers=headers),
        api_client.get(
            f"/historia-clinica/{historia_id}/evoluciones", headers=headers
        ),
        api_client.get(
            f"/historia-clinica/{historia_id}/odontograma", headers=headers
        ),
        api_client.get(
            f"/historia-clinica/{historia_id}/adjuntos", headers=headers
        ),
        api_client.get(
            f"/pacientes/{paciente_id}/consentimientos", headers=headers
        ),
    ]


def _escrituras(
    api_client, actor, historia_id, paciente_id, evolucion_id
):
    headers = bearer(actor)
    return [
        _abrir(api_client, actor, paciente_id),
        _evolucion(api_client, actor, historia_id),
        _hallazgo(api_client, actor, historia_id, pieza=22),
        _adjunto(api_client, actor, historia_id),
        _consentimiento(api_client, actor, paciente_id),
        api_client.put(
            f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
            json={"texto": "x"},
            headers=headers,
        ),
        api_client.delete(
            f"/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
            headers=headers,
        ),
        api_client.post(
            f"/historia-clinica/{historia_id}/evoluciones/"
            f"{evolucion_id}/firmar",
            json={},
            headers=headers,
        ),
    ]


def test_administrador_lee_todo_y_no_escribe(api_client, session_factory) -> None:
    """RBAC: administrator has read access to the whole file, never write."""
    data = _setup(session_factory)
    historia_id, evolucion_id = _expediente(api_client, data)
    admin = data["actores"]["administrador"]

    for response in _lecturas(
        api_client, admin, historia_id, data["paciente_propio"].id
    ):
        assert response.status_code == 200, response.text

    for response in _escrituras(
        api_client, admin, historia_id, data["paciente_en_sala"].id,
        evolucion_id,
    ):
        assert response.status_code == 403, response.text


def test_odontologo_propio_escribe_y_ajeno_403(
    api_client, session_factory
) -> None:
    """RBAC: the dentist operates only over patients with a live own turn."""
    data = _setup(session_factory)
    a = data["actores"]["odontologo"]
    ajeno = data["odontologo_ajeno"]

    propia = _abrir(api_client, a, data["paciente_propio"].id)
    assert propia.status_code == 201, propia.text
    historia_id = propia.json()["id"]
    assert _evolucion(api_client, a, historia_id).status_code == 201
    assert _hallazgo(api_client, a, historia_id).status_code == 201

    # The patient is attended by another professional: no access for A.
    assert _abrir(api_client, a, data["paciente_ajeno"].id).status_code == 403
    assert _hallazgo(api_client, a, historia_id, pieza=23).status_code == 201

    historia_ajena = _abrir(api_client, ajeno, data["paciente_ajeno"].id)
    assert historia_ajena.status_code == 201, historia_ajena.text
    historia_ajena_id = historia_ajena.json()["id"]
    assert _evolucion(api_client, a, historia_ajena_id).status_code == 403
    assert _hallazgo(api_client, a, historia_ajena_id).status_code == 403
    assert api_client.get(
        f"/historia-clinica/{historia_ajena_id}", headers=bearer(a)
    ).status_code == 403

    sin_profesional = data["odontologo_sin_profesional"]
    assert _abrir(
        api_client, sin_profesional, data["paciente_propio"].id
    ).status_code == 403
    assert api_client.get(
        f"/historia-clinica/{historia_id}", headers=bearer(sin_profesional)
    ).status_code == 403


def test_recepcionista_lee_y_no_escribe(api_client, session_factory) -> None:
    """RBAC: reception reads the file and cannot perform clinical writes."""
    data = _setup(session_factory)
    historia_id, evolucion_id = _expediente(api_client, data)
    recepcion = data["actores"]["recepcionista"]

    for response in _lecturas(
        api_client, recepcion, historia_id, data["paciente_propio"].id
    ):
        assert response.status_code == 200, response.text
    for response in _escrituras(
        api_client, recepcion, historia_id, data["paciente_en_sala"].id,
        evolucion_id,
    ):
        assert response.status_code == 403, response.text


def test_asistente_solo_paciente_en_sala(api_client, session_factory) -> None:
    """RBAC: assistant reads/edits only while the patient is in the chair."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    asistente = data["actores"]["asistente"]

    historia = _abrir(
        api_client, odontologo, data["paciente_en_sala"].id
    )
    assert historia.status_code == 201, historia.text
    historia_id = historia.json()["id"]
    borrador = _evolucion(api_client, odontologo, historia_id).json()
    assert _hallazgo(
        api_client, odontologo, historia_id
    ).status_code == 201
    assert _adjunto(api_client, odontologo, historia_id).status_code == 201
    assert _consentimiento(
        api_client, odontologo, data["paciente_en_sala"].id
    ).status_code == 201

    for response in _lecturas(
        api_client, asistente, historia_id, data["paciente_en_sala"].id
    ):
        assert response.status_code == 200, response.text
    editado = _editar(
        api_client, asistente, historia_id, borrador["id"], "Asistente"
    )
    assert editado.status_code == 200, editado.text

    assert _evolucion(api_client, asistente, historia_id).status_code == 403
    assert _firmar(
        api_client, asistente, historia_id, borrador["id"]
    ).status_code == 403
    assert _hallazgo(api_client, asistente, historia_id).status_code == 403
    assert _adjunto(api_client, asistente, historia_id).status_code == 403
    assert _consentimiento(
        api_client, asistente, data["paciente_en_sala"].id
    ).status_code == 403

    # Confirmed (not in the chair) patient: no read and no edit either.
    historia_ajena = _abrir(
        api_client, data["odontologo_ajeno"], data["paciente_ajeno"].id
    )
    assert historia_ajena.status_code == 201
    historia_ajena_id = historia_ajena.json()["id"]
    assert api_client.get(
        f"/historia-clinica/{historia_ajena_id}", headers=bearer(asistente)
    ).status_code == 403
    assert api_client.get(
        f"/historia-clinica/{historia_ajena_id}/evoluciones",
        headers=bearer(asistente),
    ).status_code == 403


def test_auditor_lee_y_no_escribe(api_client, session_factory) -> None:
    """RBAC: auditor is read-only across the clinical record."""
    data = _setup(session_factory)
    historia_id, evolucion_id = _expediente(api_client, data)
    auditor = data["actores"]["auditor"]

    for response in _lecturas(
        api_client, auditor, historia_id, data["paciente_propio"].id
    ):
        assert response.status_code == 200, response.text
    for response in _escrituras(
        api_client, auditor, historia_id, data["paciente_en_sala"].id,
        evolucion_id,
    ):
        assert response.status_code == 403, response.text


def test_sin_token_401(api_client, session_factory) -> None:
    """RBAC: no Bearer token means 401 on every clinical route."""
    data = _setup(session_factory)
    historia_id, _ = _expediente(api_client, data)

    endpoints = [
        ("get", f"/historia-clinica/{historia_id}"),
        ("get", f"/historia-clinica/{historia_id}/evoluciones"),
        ("get", f"/historia-clinica/{historia_id}/odontograma"),
        ("get", f"/historia-clinica/{historia_id}/adjuntos"),
        (
            "get",
            f"/pacientes/{data['paciente_propio'].id}/consentimientos",
        ),
        ("post", "/historia-clinica"),
        ("post", f"/historia-clinica/{historia_id}/evoluciones"),
        ("post", f"/historia-clinica/{historia_id}/odontograma/hallazgos"),
        ("post", "/adjuntos"),
        (
            "post",
            f"/pacientes/{data['paciente_propio'].id}/consentimientos",
        ),
    ]
    for method, url in endpoints:
        response = getattr(api_client, method)(url)
        assert response.status_code == 401, (method, url, response.text)


def _conteos(session_factory) -> dict[str, int]:
    filas = run(auditorias(session_factory))
    conteo = {accion: 0 for accion in ACCIONES}
    for fila in filas:
        conteo[fila.accion] = conteo.get(fila.accion, 0) + 1
    return conteo


def _delta(antes: dict[str, int], despues: dict[str, int], accion: str) -> int:
    return despues.get(accion, 0) - antes.get(accion, 0)


def test_auditoria_exactamente_una_por_accion(api_client, session_factory) -> None:
    """RN-SE-02: one row per clinical write, and none for rejected writes."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    # Apertura.
    antes = _conteos(session_factory)
    historia = _abrir(api_client, odontologo, paciente.id)
    assert historia.status_code == 201, historia.text
    historia_id = historia.json()["id"]
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "historia_clinica.crear") == 1

    # Alta de evolución.
    antes = despues
    evolucion = _evolucion(api_client, odontologo, historia_id)
    assert evolucion.status_code == 201
    evolucion_id = evolucion.json()["id"]
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "evolucion.crear") == 1

    # Edición.
    antes = despues
    assert _editar(
        api_client, odontologo, historia_id, evolucion_id, "Editado"
    ).status_code == 200
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "evolucion.editar") == 1

    # Firma.
    antes = despues
    assert _firmar(
        api_client, odontologo, historia_id, evolucion_id
    ).status_code == 200
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "evolucion.firmar") == 1

    # Descarte de un borrador nuevo.
    antes = despues
    borrador = _evolucion(api_client, odontologo, historia_id)
    assert borrador.status_code == 201
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "evolucion.crear") == 1
    antes = despues
    assert _descartar(
        api_client, odontologo, historia_id, borrador.json()["id"]
    ).status_code == 204
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "evolucion.descartar") == 1

    # Rectificación de la evolución firmada.
    antes = despues
    rectificatoria = api_client.post(
        f"/historia-clinica/{historia_id}/evoluciones",
        json={"texto": "Rectificada", "rectifica_a": evolucion_id},
        headers=bearer(odontologo),
    )
    assert rectificatoria.status_code == 201, rectificatoria.text
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "evolucion.rectificar") == 1

    # Versión de odontograma.
    antes = despues
    assert _hallazgo(
        api_client, odontologo, historia_id
    ).status_code == 201
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "odontograma.versionar") == 1

    # Adjunto.
    antes = despues
    assert _adjunto(api_client, odontologo, historia_id).status_code == 201
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "adjunto.crear") == 1

    # Consentimiento.
    antes = despues
    assert _consentimiento(
        api_client, odontologo, paciente.id
    ).status_code == 201
    despues = _conteos(session_factory)
    assert _delta(antes, despues, "consentimiento.registrar") == 1

    # Every clinical row belongs to the authenticated dentist and entity.
    filas = run(auditorias(session_factory))
    propias = [fila for fila in filas if fila.accion in ACCIONES]
    assert propias
    for fila in propias:
        assert fila.usuario_id == odontologo.id, fila.accion
        assert fila.entidad == ENTIDADES[fila.accion], fila.accion
        assert fila.entidad_id

    # Rejected writes leave exactly zero new rows.
    total_antes = len(filas)
    assert _hallazgo(
        api_client, odontologo, historia_id, pieza=19
    ).status_code == 422
    assert _consentimiento(
        api_client, odontologo, paciente.id
    ).status_code == 201  # a valid one, to keep the flow honest
    total_despues_consentimiento = len(run(auditorias(session_factory)))
    assert total_despues_consentimiento == total_antes + 1
    admin = data["actores"]["administrador"]
    assert _evolucion(api_client, admin, historia_id).status_code == 403
    assert _hallazgo(api_client, admin, historia_id, pieza=25).status_code == 403
    assert len(run(auditorias(session_factory))) == total_despues_consentimiento
