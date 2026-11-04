"""Clinical history endpoints: aperture, reads, RBAC and audit (C-11 slice 1)."""

import uuid

import pytest
from sqlalchemy import func, select

from app.infrastructure.uow import UnitOfWork
from app.models import RegistroAuditoria
from tests.integration.clinica_helpers import (
    insertar_historia_db,
    otro_consultorio,
    setup_clinica,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_clinica(session_factory))


def _crear(api_client, actor, paciente_id: uuid.UUID):
    return api_client.post(
        "/historia-clinica",
        json={"paciente_id": str(paciente_id)},
        headers=bearer(actor),
    )


async def _auditorias(session_factory) -> list[RegistroAuditoria]:
    async with session_factory() as session:
        result = await session.scalars(
            select(RegistroAuditoria)
            .where(RegistroAuditoria.accion.like("historia_clinica.%"))
            .order_by(RegistroAuditoria.timestamp)
        )
        return list(result)


def _borrar_paciente(session_factory, paciente_id: uuid.UUID) -> None:
    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(paciente_id)
            assert paciente is not None
            await uow.pacientes.soft_delete(paciente)

    run(scenario())


def test_apertura_devuelve_201_y_las_lecturas_200(
    api_client, session_factory
) -> None:
    """Expected: create once, then read by id and by patient."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    created = _crear(api_client, odontologo, paciente.id)
    assert created.status_code == 201, created.text
    historia = created.json()
    assert historia["paciente_id"] == str(paciente.id)
    assert historia["consultorio_id"] == str(data["consultorio_id"])
    assert historia["abierta_por"] == str(odontologo.id)
    assert historia["fecha_apertura"]
    assert historia["is_active"] is True

    por_id = api_client.get(
        f"/historia-clinica/{historia['id']}",
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert por_id.status_code == 200, por_id.text
    assert por_id.json() == historia

    por_paciente = api_client.get(
        f"/pacientes/{paciente.id}/historia-clinica",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert por_paciente.status_code == 200, por_paciente.text
    assert por_paciente.json() == historia


def test_segunda_historia_activa_responde_409(
    api_client, session_factory
) -> None:
    """Business error: one active history per patient, no extra row/audit."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    assert _crear(api_client, odontologo, paciente.id).status_code == 201
    duplicated = _crear(api_client, odontologo, paciente.id)
    assert duplicated.status_code == 409, duplicated.text

    async def contar() -> tuple[int, int]:
        async with session_factory() as session:
            historias = await session.scalar(
                select(func.count())
                .select_from(RegistroAuditoria)
                .where(RegistroAuditoria.accion == "historia_clinica.crear")
            )
        auditorias = await _auditorias(session_factory)
        return historias or 0, len(auditorias)

    assert run(contar()) == (1, 1)


def test_paciente_inexistente_o_dado_de_baja_404(
    api_client, session_factory
) -> None:
    """Business error: unknown or soft-deleted patient is not a valid target."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    inexistente = _crear(api_client, odontologo, uuid.uuid4())
    assert inexistente.status_code == 404, inexistente.text
    assert inexistente.json()["detail"] == "Paciente no encontrado"

    _borrar_paciente(session_factory, data["paciente_propio"].id)
    dado_de_baja = _crear(
        api_client, odontologo, data["paciente_propio"].id
    )
    assert dado_de_baja.status_code == 404, dado_de_baja.text

    assert run(_auditorias(session_factory)) == []


def test_apertura_de_paciente_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    """Business error: a patient of another tenant is invisible, not forbidden."""
    data = _setup(session_factory)
    ajeno = run(otro_consultorio(session_factory))

    response = _crear(
        api_client, data["actores"]["odontologo"], ajeno["paciente_id"]
    )
    assert response.status_code == 404, response.text
    assert run(_auditorias(session_factory)) == []


def test_paciente_sin_historia_responde_404_con_detalle(
    api_client, session_factory
) -> None:
    """Edge: an active patient may still have no history yet."""
    data = _setup(session_factory)
    response = api_client.get(
        f"/pacientes/{data['paciente_propio'].id}/historia-clinica",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Historia clínica no encontrada"


def test_historia_de_otro_consultorio_404(api_client, session_factory) -> None:
    """Business error: cross-tenant identifiers never expose clinical data."""
    data = _setup(session_factory)
    ajeno = run(otro_consultorio(session_factory))
    historia_id = run(
        insertar_historia_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente_id"],
            abierta_por=data["actores"]["administrador"].id,
        )
    )

    por_id = api_client.get(
        f"/historia-clinica/{historia_id}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert por_id.status_code == 404, por_id.text

    por_paciente = api_client.get(
        f"/pacientes/{ajeno['paciente_id']}/historia-clinica",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert por_paciente.status_code == 404, por_paciente.text


def test_apertura_solo_odontologo_propio(api_client, session_factory) -> None:
    """RBAC: admin/reception/auditor/assistant cannot open; dentist owns."""
    data = _setup(session_factory)
    paciente = data["paciente_propio"]
    actores = data["actores"]

    for rol in ("administrador", "recepcionista", "asistente", "auditor"):
        forbidden = _crear(api_client, actores[rol], paciente.id)
        assert forbidden.status_code == 403, (rol, forbidden.text)

    ajeno = _crear(api_client, data["odontologo_ajeno"], paciente.id)
    assert ajeno.status_code == 403, ajeno.text

    sin_profesional = _crear(
        api_client, data["odontologo_sin_profesional"], paciente.id
    )
    assert sin_profesional.status_code == 403, sin_profesional.text

    sin_turno = _crear(
        api_client, actores["odontologo"], data["paciente_sin_turno"].id
    )
    assert sin_turno.status_code == 403, sin_turno.text

    anonimo = api_client.post(
        "/historia-clinica", json={"paciente_id": str(paciente.id)}
    )
    assert anonimo.status_code == 401, anonimo.text

    assert run(_auditorias(session_factory)) == []


def test_lectura_por_rol(api_client, session_factory) -> None:
    """RBAC read matrix: total readers, own dentist and in-room assistant."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]

    propia = _crear(api_client, odontologo, paciente.id)
    assert propia.status_code == 201, propia.text
    historia_id = propia.json()["id"]

    for rol in ("administrador", "recepcionista", "auditor"):
        leida = api_client.get(
            f"/historia-clinica/{historia_id}",
            headers=bearer(data["actores"][rol]),
        )
        assert leida.status_code == 200, (rol, leida.text)

    propia_odontologo = api_client.get(
        f"/historia-clinica/{historia_id}", headers=bearer(odontologo)
    )
    assert propia_odontologo.status_code == 200

    # Assistant: the patient is only `reservado`, not in the chair.
    asistente = api_client.get(
        f"/historia-clinica/{historia_id}",
        headers=bearer(data["actores"]["asistente"]),
    )
    assert asistente.status_code == 403, asistente.text

    en_sala = _crear(api_client, odontologo, data["paciente_en_sala"].id)
    assert en_sala.status_code == 201, en_sala.text
    asistente_sala = api_client.get(
        f"/historia-clinica/{en_sala.json()['id']}",
        headers=bearer(data["actores"]["asistente"]),
    )
    assert asistente_sala.status_code == 200, asistente_sala.text

    # Another dentist cannot read it; neither can one without a professional.
    ajeno = api_client.get(
        f"/historia-clinica/{historia_id}",
        headers=bearer(data["odontologo_ajeno"]),
    )
    assert ajeno.status_code == 403, ajeno.text
    sin_profesional = api_client.get(
        f"/historia-clinica/{historia_id}",
        headers=bearer(data["odontologo_sin_profesional"]),
    )
    assert sin_profesional.status_code == 403, sin_profesional.text


def test_lectura_sin_token_401(api_client, session_factory) -> None:
    """RBAC: no Bearer token means 401, never clinical data."""
    data = _setup(session_factory)
    response = api_client.get(
        f"/pacientes/{data['paciente_propio'].id}/historia-clinica"
    )
    assert response.status_code == 401, response.text


def test_auditoria_de_la_apertura(api_client, session_factory) -> None:
    """Expected: exactly one row with user, IP and truncated User-Agent."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    created = _crear(api_client, odontologo, data["paciente_propio"].id)
    assert created.status_code == 201, created.text

    filas = run(_auditorias(session_factory))
    assert len(filas) == 1
    fila = filas[0]
    assert fila.accion == "historia_clinica.crear"
    assert fila.entidad == "historia_clinica"
    assert fila.entidad_id == created.json()["id"]
    assert fila.usuario_id == odontologo.id
    assert fila.ip == "testclient"
    assert fila.dispositivo is not None
    assert len(fila.dispositivo) <= 120


def test_apertura_rechazada_no_deja_auditoria(
    api_client, session_factory
) -> None:
    """Business error: a failed write rolls back the audit row too."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    rechazada = _crear(api_client, odontologo, uuid.uuid4())
    assert rechazada.status_code == 404
    assert run(_auditorias(session_factory)) == []

    assert _crear(
        api_client, odontologo, data["paciente_propio"].id
    ).status_code == 201
    duplicada = _crear(api_client, odontologo, data["paciente_propio"].id)
    assert duplicada.status_code == 409

    filas = run(_auditorias(session_factory))
    assert len(filas) == 1


@pytest.mark.parametrize(
    "campo", ["historia_id", "paciente", "texto", "otro"]
)
def test_apertura_rechaza_campos_extra(
    api_client, session_factory, campo: str
) -> None:
    """Strict boundary: only `paciente_id` is accepted in the body."""
    data = _setup(session_factory)
    payload = {
        "paciente_id": str(data["paciente_propio"].id),
        campo: "sorpresa",
    }
    response = api_client.post(
        "/historia-clinica",
        json=payload,
        headers=bearer(data["actores"]["odontologo"]),
    )
    assert response.status_code == 422, response.text
