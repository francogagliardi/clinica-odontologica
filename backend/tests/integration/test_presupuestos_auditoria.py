"""Budget audit trail: every action, no rows on rejection, append-only (C-12)."""

import uuid

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import RegistroAuditoria
from tests.integration.clinica_helpers import auditorias
from tests.integration.helpers import run, sqlstate
from tests.integration.presupuestos_helpers import setup_presupuestos
from tests.integration.recursos_helpers import bearer

_UA = "pytest-ua-c12"


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def _payload(data, paciente_id=None, profesional_id=None, codigo="CONS"):
    return {
        "paciente_id": str(paciente_id or data["paciente_os_demo"].id),
        "profesional_id": str(profesional_id or data["profesional"].id),
        "items": [
            {
                "prestacion_id": str(data["prestaciones"][codigo].id),
                "cantidad": 1,
            }
        ],
    }


def _headers(data, actor=None):
    return {
        **bearer(actor or data["actores"]["administrador"]),
        "User-Agent": _UA,
    }


def _alta(
    api_client,
    data,
    *,
    codigo="CONS",
    paciente_id=None,
    profesional_id=None,
    actor=None,
):
    return api_client.post(
        "/presupuestos",
        json=_payload(
            data,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            codigo=codigo,
        ),
        headers=_headers(data, actor),
    )


def _estado(api_client, data, presupuesto_id, estado: str):
    return api_client.patch(
        f"/presupuestos/{presupuesto_id}/estado",
        json={"estado": estado},
        headers=_headers(data),
    )


def _presupuesto_rows(session_factory) -> list[RegistroAuditoria]:
    return [
        registro
        for registro in run(auditorias(session_factory))
        if registro.accion.startswith("presupuesto.")
    ]


def test_todas_las_acciones_auditan_usuario_ip_y_agente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    admin = data["actores"]["administrador"]

    principal = _alta(api_client, data)
    assert principal.status_code == 201, principal.text
    presupuesto_id = principal.json()["id"]
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=_payload(data, codigo="OBT"),
            headers=_headers(data),
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            f"/presupuestos/{presupuesto_id}/recalcular",
            json={},
            headers=_headers(data),
        ).status_code
        == 200
    )
    assert _estado(api_client, data, presupuesto_id, "aceptado").status_code == 200
    assert _estado(api_client, data, presupuesto_id, "en_curso").status_code == 200
    assert _estado(api_client, data, presupuesto_id, "finalizado").status_code == 200

    rechazado = _alta(api_client, data).json()["id"]
    assert _estado(api_client, data, rechazado, "rechazado").status_code == 200

    eliminado = _alta(api_client, data).json()["id"]
    assert (
        api_client.delete(
            f"/presupuestos/{eliminado}", headers=_headers(data)
        ).status_code
        == 204
    )

    filas = _presupuesto_rows(session_factory)
    acciones = {fila.accion for fila in filas}
    assert {
        "presupuesto.crear",
        "presupuesto.editar",
        "presupuesto.recalcular",
        "presupuesto.aceptar",
        "presupuesto.en_curso",
        "presupuesto.finalizar",
        "presupuesto.rechazar",
        "presupuesto.eliminar",
    } <= acciones
    for fila in filas:
        assert fila.entidad == "presupuesto"
        assert fila.usuario_id == admin.id
        assert fila.ip == "testclient"
        assert fila.dispositivo == _UA

    entidades = {
        fila.entidad_id
        for fila in filas
        if fila.accion
        in {
            "presupuesto.aceptar",
            "presupuesto.en_curso",
            "presupuesto.finalizar",
        }
    }
    assert entidades == {str(presupuesto_id)}


def test_rechazos_no_dejan_fila_de_auditoria(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = _headers(data)

    aceptado = _alta(api_client, data).json()["id"]
    assert _estado(api_client, data, aceptado, "aceptado").status_code == 200
    borrador = _alta(api_client, data).json()["id"]
    ajeno = _alta(
        api_client,
        data,
        paciente_id=data["paciente_ajeno"].id,
        profesional_id=data["profesional_ajeno"].id,
    )
    assert ajeno.status_code == 201, ajeno.text

    antes = len(_presupuesto_rows(session_factory))

    # 422: invalid transition and invalid draft payload.
    assert _estado(api_client, data, borrador, "en_curso").status_code == 422
    assert (
        api_client.put(
            f"/presupuestos/{borrador}",
            json={
                **_payload(data),
                "items": [
                    {
                        "prestacion_id": str(
                            data["prestaciones"]["CONS"].id
                        ),
                        "cantidad": 1,
                        "precio_unitario": "1.00",
                    }
                ],
            },
            headers=headers,
        ).status_code
        == 422
    )
    # 409: non-draft write paths.
    assert (
        api_client.put(
            f"/presupuestos/{aceptado}",
            json=_payload(data),
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        api_client.delete(
            f"/presupuestos/{aceptado}", headers=headers
        ).status_code
        == 409
    )
    # 404: missing budget.
    assert (
        api_client.get(
            f"/presupuestos/{uuid.uuid4()}", headers=headers
        ).status_code
        == 404
    )
    # 403: another dentist's budget.
    ajeno_id = ajeno.json()["id"]
    odontologo = bearer(data["actores"]["odontologo"])
    assert (
        api_client.get(f"/presupuestos/{ajeno_id}", headers=odontologo).status_code
        == 403
    )
    assert (
        api_client.patch(
            f"/presupuestos/{ajeno_id}/estado",
            json={"estado": "aceptado"},
            headers=odontologo,
        ).status_code
        == 403
    )

    despues = len(_presupuesto_rows(session_factory))
    assert despues == antes
    assert run(auditorias(session_factory, "presupuesto.recalcular")) == []


def test_accion_idempotente_no_audita_de_nuevo(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    presupuesto_id = _alta(api_client, data).json()["id"]

    assert _estado(api_client, data, presupuesto_id, "aceptado").status_code == 200
    antes = len(run(auditorias(session_factory, "presupuesto.aceptar")))
    assert _estado(api_client, data, presupuesto_id, "aceptado").status_code == 200
    despues = len(run(auditorias(session_factory, "presupuesto.aceptar")))
    assert despues == antes == 1


async def _sqlstate_de(
    session_factory, statement: str, params: dict[str, object]
) -> str | None:
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_auditoria_de_presupuesto_es_append_only_p0001(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    assert creado.status_code == 201, creado.text

    filas = run(auditorias(session_factory, "presupuesto.crear"))
    assert len(filas) == 1
    audit_id = filas[0].id

    assert (
        run(
            _sqlstate_de(
                session_factory,
                "UPDATE registro_auditoria SET accion = 'alterado' "
                "WHERE id = :id",
                {"id": audit_id},
            )
        )
        == "P0001"
    )
    assert (
        run(
            _sqlstate_de(
                session_factory,
                "DELETE FROM registro_auditoria WHERE id = :id",
                {"id": audit_id},
            )
        )
        == "P0001"
    )

    # The row is still there and untouched.
    assert len(run(auditorias(session_factory, "presupuesto.crear"))) == 1
