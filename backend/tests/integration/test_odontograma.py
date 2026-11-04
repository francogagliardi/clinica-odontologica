"""FDI odontogram: versioned snapshots, immutability and audit (C-11 slice 3)."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.integration.clinica_helpers import (
    auditorias,
    insertar_historia_db,
    otro_consultorio,
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


def _hallazgo(
    api_client,
    actor,
    historia_id,
    *,
    pieza: int = 16,
    cara: str = "mesial",
    estado: str = "caries",
    cie10: str | None = "K02.1",
    diagnostico: str | None = "Lesión inicial",
    fecha: str | None = None,
):
    payload: dict[str, object] = {
        "pieza": pieza,
        "cara": cara,
        "estado": estado,
        "cie10": cie10,
        "diagnostico": diagnostico,
    }
    if fecha is not None:
        payload["fecha"] = fecha
    return api_client.post(
        f"/historia-clinica/{historia_id}/odontograma/hallazgos",
        json=payload,
        headers=bearer(actor),
    )


def _vigente(api_client, actor, historia_id):
    return api_client.get(
        f"/historia-clinica/{historia_id}/odontograma",
        headers=bearer(actor),
    )


def _version(api_client, actor, historia_id, version: int):
    return api_client.get(
        f"/historia-clinica/{historia_id}/odontograma/versiones/{version}",
        headers=bearer(actor),
    )


def _audit_count(session_factory, accion: str) -> int:
    return len(run(auditorias(session_factory, accion)))


async def _sqlstate_async(session_factory, statement, params):
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_historia_sin_odontograma_devuelve_version_nula(
    api_client, session_factory
) -> None:
    """Edge: no snapshots is a valid empty state, not a 404."""
    data = _setup(session_factory)
    historia = _abrir(
        api_client, data["actores"]["odontologo"], data["paciente_propio"].id
    )

    response = _vigente(
        api_client, data["actores"]["recepcionista"], historia["id"]
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"version": None, "hallazgos": []}


def test_primera_version_con_pieza_permanente(
    api_client, session_factory
) -> None:
    """Expected: first finding creates version 1 with the exact data."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    created = _hallazgo(api_client, odontologo, historia["id"])
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["version"] == 1
    assert len(body["hallazgos"]) == 1
    hallazgo = body["hallazgos"][0]
    assert hallazgo["pieza"] == 16
    assert hallazgo["cara"] == "mesial"
    assert hallazgo["estado"] == "caries"
    assert hallazgo["cie10"] == "K02.1"
    assert hallazgo["diagnostico"] == "Lesión inicial"
    assert hallazgo["fecha"] == "2026-11-04"

    vigente = _vigente(api_client, odontologo, historia["id"])
    assert vigente.json() == body


def test_pieza_temporaria_valida(api_client, session_factory) -> None:
    """Expected: 75 is a valid temporary tooth."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    created = _hallazgo(
        api_client,
        odontologo,
        historia["id"],
        pieza=75,
        cara="oclusal",
        estado="obturacion",
        cie10=None,
        diagnostico=None,
    )
    assert created.status_code == 201, created.text
    assert created.json()["hallazgos"][0]["pieza"] == 75


@pytest.mark.parametrize("pieza", [19, 20, 29, 49, 56, 86, 99])
def test_piezas_fuera_de_fdi_422(
    api_client, session_factory, pieza: int
) -> None:
    """Business error: invalid FDI pieces never create a version."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    rejected = _hallazgo(api_client, odontologo, historia["id"], pieza=pieza)
    assert rejected.status_code == 422, (pieza, rejected.text)
    assert _vigente(api_client, odontologo, historia["id"]).json() == {
        "version": None,
        "hallazgos": [],
    }
    assert _audit_count(session_factory, "odontograma.versionar") == 0


@pytest.mark.parametrize(
    "cambios",
    [
        {"cara": "lateral"},
        {"cara": "superior"},
        {"estado": "desconocido"},
        {"cie10": "caries"},
        {"cie10": "k021"},
    ],
)
def test_cara_estado_o_cie10_invalidos_422(
    api_client, session_factory, cambios: dict[str, object]
) -> None:
    """Business error: the clinical catalogue is validated at the edge."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    rejected = _hallazgo(
        api_client, odontologo, historia["id"], **cambios
    )
    assert rejected.status_code == 422, (cambios, rejected.text)
    assert _vigente(api_client, odontologo, historia["id"]).json() == {
        "version": None,
        "hallazgos": [],
    }


def test_historia_inexistente_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    """Business error: findings only hang from an own active history."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]

    assert _hallazgo(
        api_client, odontologo, uuid.uuid4()
    ).status_code == 404

    ajeno = run(otro_consultorio(session_factory))
    historia_ajena = run(
        insertar_historia_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente_id"],
            abierta_por=data["actores"]["administrador"].id,
        )
    )
    assert _hallazgo(
        api_client, odontologo, historia_ajena
    ).status_code == 404
    assert _vigente(
        api_client, data["actores"]["administrador"], historia_ajena
    ).status_code == 404


def test_versionado_snapshots_y_correccion(api_client, session_factory) -> None:
    """Business rule: N+1 copies N except the changed tooth/face."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    v1 = _hallazgo(api_client, odontologo, historia["id"])
    assert v1.status_code == 201, v1.text
    assert v1.json()["version"] == 1

    v2 = _hallazgo(
        api_client,
        odontologo,
        historia["id"],
        pieza=21,
        cara="oclusal",
        estado="sano",
        cie10=None,
    )
    assert v2.status_code == 201, v2.text
    assert v2.json()["version"] == 2
    assert len(v2.json()["hallazgos"]) == 2

    v3 = _hallazgo(
        api_client,
        odontologo,
        historia["id"],
        pieza=16,
        cara="mesial",
        estado="obturacion",
    )
    assert v3.status_code == 201, v3.text
    assert v3.json()["version"] == 3
    assert len(v3.json()["hallazgos"]) == 2
    corregido = {
        (fila["pieza"], fila["cara"]): fila["estado"]
        for fila in v3.json()["hallazgos"]
    }
    assert corregido[(16, "mesial")] == "obturacion"

    original = _version(api_client, odontologo, historia["id"], 1).json()
    assert len(original["hallazgos"]) == 1
    assert original["hallazgos"][0]["estado"] == "caries"

    anterior = _version(api_client, odontologo, historia["id"], 2).json()
    estados_v2 = {
        (fila["pieza"], fila["cara"]): fila["estado"]
        for fila in anterior["hallazgos"]
    }
    assert estados_v2[(16, "mesial")] == "caries"
    assert len(anterior["hallazgos"]) == 2

    vigente = _vigente(api_client, odontologo, historia["id"]).json()
    assert vigente["version"] == 3
    assert vigente == v3.json()


def test_version_inexistente_404(api_client, session_factory) -> None:
    """Business error: an unknown version never returns another snapshot."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    assert _hallazgo(
        api_client, odontologo, historia["id"]
    ).status_code == 201

    response = _version(api_client, odontologo, historia["id"], 99)
    assert response.status_code == 404, response.text


def test_hallazgo_no_admite_put_ni_delete_405(
    api_client, session_factory
) -> None:
    """Business rule: findings are append-only; the path exists only for GET."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    hallazgo = _hallazgo(
        api_client, odontologo, historia["id"]
    ).json()["hallazgos"][0]

    assert api_client.put(
        f"/odontograma/hallazgos/{hallazgo['id']}",
        json={"estado": "sano"},
        headers=bearer(odontologo),
    ).status_code == 405
    assert api_client.delete(
        f"/odontograma/hallazgos/{hallazgo['id']}",
        headers=bearer(odontologo),
    ).status_code == 405


def test_triggers_directos_p0001(api_client, session_factory) -> None:
    """Business error: PostgreSQL protects snapshots and findings too."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    body = _hallazgo(api_client, odontologo, historia["id"]).json()
    hallazgo_id = uuid.UUID(body["hallazgos"][0]["id"])

    async def odontograma_id() -> uuid.UUID:
        async with session_factory() as session:
            return await session.scalar(
                text(
                    "SELECT odontograma_id FROM hallazgos_dentales "
                    "WHERE id = :id"
                ),
                {"id": hallazgo_id},
            )

    version_id = run(odontograma_id())
    assert run(
        _sqlstate_async(
            session_factory,
            "UPDATE odontogramas SET version = 99 WHERE id = :id",
            {"id": version_id},
        )
    ) == "P0001"
    assert run(
        _sqlstate_async(
            session_factory,
            "UPDATE hallazgos_dentales SET estado = 'sano' WHERE id = :id",
            {"id": hallazgo_id},
        )
    ) == "P0001"
    assert run(
        _sqlstate_async(
            session_factory,
            "DELETE FROM hallazgos_dentales WHERE id = :id",
            {"id": hallazgo_id},
        )
    ) == "P0001"


def test_concurrencia_no_repite_version(api_client, session_factory) -> None:
    """Business rule: FOR UPDATE serializes concurrent snapshot writes."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    headers = bearer(odontologo)
    url = f"/historia-clinica/{historia['id']}/odontograma/hallazgos"

    def enviar(pieza: int):
        return api_client.post(
            url,
            json={"pieza": pieza, "cara": "mesial", "estado": "caries"},
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(enviar, [11, 21]))

    assert [r.status_code for r in responses] == [201, 201], [
        r.text for r in responses
    ]
    versiones = sorted(r.json()["version"] for r in responses)
    assert versiones == [1, 2]

    vigente = _vigente(api_client, odontologo, historia["id"]).json()
    assert vigente["version"] == 2
    assert {fila["pieza"] for fila in vigente["hallazgos"]} == {11, 21}


def test_auditoria_por_version_y_sin_rastro_si_falla(
    api_client, session_factory
) -> None:
    """Expected: one audit row per version; invalid input leaves none."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)

    for pieza in (11, 21, 31):
        assert _hallazgo(
            api_client, odontologo, historia["id"], pieza=pieza
        ).status_code == 201

    filas = run(auditorias(session_factory, "odontograma.versionar"))
    assert len(filas) == 3
    assert {fila.usuario_id for fila in filas} == {odontologo.id}
    assert all(fila.entidad == "odontograma" for fila in filas)
    assert len({fila.entidad_id for fila in filas}) == 3

    rechazado = _hallazgo(
        api_client, odontologo, historia["id"], pieza=19
    )
    assert rechazado.status_code == 422
    assert _audit_count(session_factory, "odontograma.versionar") == 3
    assert _vigente(api_client, odontologo, historia["id"]).json()["version"] == 3


def test_rbac_de_odontograma(api_client, session_factory) -> None:
    """RBAC: readers read their scope; only the owning dentist writes."""
    data = _setup(session_factory)
    odontologo = data["actores"]["odontologo"]
    historia = _abrir(api_client, odontologo, data["paciente_propio"].id)
    assert _hallazgo(
        api_client, odontologo, historia["id"]
    ).status_code == 201

    for rol in ("administrador", "recepcionista", "auditor"):
        leida = _vigente(api_client, data["actores"][rol], historia["id"])
        assert leida.status_code == 200, (rol, leida.text)
        assert _hallazgo(
            api_client, data["actores"][rol], historia["id"], pieza=22
        ).status_code == 403

    asistente = data["actores"]["asistente"]
    assert _vigente(
        api_client, asistente, historia["id"]
    ).status_code == 403
    assert _hallazgo(
        api_client, asistente, historia["id"], pieza=22
    ).status_code == 403

    historia_sala = _abrir(
        api_client, odontologo, data["paciente_en_sala"].id
    )
    assert _hallazgo(
        api_client, odontologo, historia_sala["id"], pieza=23
    ).status_code == 201
    assert _vigente(
        api_client, asistente, historia_sala["id"]
    ).status_code == 200
    assert _hallazgo(
        api_client, asistente, historia_sala["id"], pieza=24
    ).status_code == 403

    assert _vigente(
        api_client, data["odontologo_ajeno"], historia["id"]
    ).status_code == 403
    assert _hallazgo(
        api_client, data["odontologo_ajeno"], historia["id"], pieza=25
    ).status_code == 403
    assert _vigente(
        api_client, data["odontologo_sin_profesional"], historia["id"]
    ).status_code == 403

    assert api_client.get(
        f"/historia-clinica/{historia['id']}/odontograma"
    ).status_code == 401
