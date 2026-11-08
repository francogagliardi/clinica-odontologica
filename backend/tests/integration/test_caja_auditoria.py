"""C-13 audit trail for payments: actions, actor, no rows on rejection."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.mercadopago import TestMercadoPagoClient
from tests.integration.clinica_helpers import auditorias
from tests.integration.cobros_helpers import (
    cobro_payload,
    firma_mp,
    mp_override,
    pago,
    setup_cobros,
    webhook_payload,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.recursos_helpers import bearer

_UA_CREAR = "pytest-ua-c13-audit"
_UA_PERDER = "pytest-ua-c13-loss"
_UA_WEBHOOK = "pytest-ua-c13-webhook"


def _setup(session_factory, *, con_caja: bool = True) -> dict[str, object]:
    return run(setup_cobros(session_factory, con_caja=con_caja))


def _cobros_audit(session_factory):
    return [
        fila
        for fila in run(auditorias(session_factory))
        if fila.accion.startswith("cobro.")
    ]


def _caja_audit(session_factory):
    return [
        fila
        for fila in run(auditorias(session_factory))
        if fila.accion.startswith("caja.")
    ]


def _crear_efectivo(api_client, data, **overrides):
    return api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers={
            **bearer(data["actores"]["recepcionista"]),
            "User-Agent": _UA_CREAR,
        },
    )


def _crear_mp(
    api_client,
    data,
    cliente,
    *,
    turno_key: str = "sena",
    paciente_id=None,
) -> dict[str, object]:
    respuesta = api_client.post(
        "/cobros",
        json=cobro_payload(
            data,
            paciente_id=paciente_id or data["paciente_os_demo"].id,
            tipo="sena",
            medio="mercadopago",
            monto="10000.00",
            turno_id=data["turnos_cobro"][turno_key],
        ),
        headers={
            **bearer(data["actores"]["recepcionista"]),
            "User-Agent": _UA_CREAR,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_cobro_crear_audita_usuario_ip_y_agente(
    api_client, session_factory
) -> None:
    """Expected: one `cobro.crear` with user, IP and truncated User-Agent."""
    data = _setup(session_factory)
    respuesta = _crear_efectivo(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    cobro_id = respuesta.json()["id"]

    filas = [
        fila
        for fila in _cobros_audit(session_factory)
        if fila.accion == "cobro.crear"
    ]
    assert len(filas) == 1
    fila = filas[0]
    assert fila.entidad == "cobro"
    assert fila.entidad_id == cobro_id
    assert fila.usuario_id == data["actores"]["recepcionista"].id
    assert fila.ip == "testclient"
    assert fila.dispositivo == _UA_CREAR


def test_cobro_conciliar_audita_actor_sistema(
    api_client, session_factory
) -> None:
    """Expected: webhook reconciliation uses a NULL user (system actor)."""
    data = _setup(session_factory, con_caja=True)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        body = _crear_mp(api_client, data, cliente)
        cobro_id = uuid.UUID(body["id"])
        cliente.simular_pago(
            pago(cobro_id=cobro_id, pago_id="mp-audit-1")
        )
        headers = firma_mp("mp-audit-1")
        headers["user-agent"] = _UA_WEBHOOK
        respuesta = api_client.post(
            "/webhooks/mercadopago",
            json=webhook_payload("mp-audit-1"),
            headers=headers,
        )
    assert respuesta.status_code == 200, respuesta.text

    filas = [
        fila
        for fila in _cobros_audit(session_factory)
        if fila.accion == "cobro.conciliar"
    ]
    assert len(filas) == 1
    fila = filas[0]
    assert fila.entidad == "cobro"
    assert fila.entidad_id == str(cobro_id)
    assert fila.usuario_id is None
    assert fila.ip == "testclient"
    assert fila.dispositivo == _UA_WEBHOOK


def test_cobro_perder_audita_usuario_y_turno(
    api_client, session_factory
) -> None:
    """Expected: losing a deposit records `cobro.perder` with the actor."""
    data = _setup(session_factory)
    creado = _crear_efectivo(
        api_client,
        data,
        tipo="sena",
        medio="efectivo",
        monto="10000.00",
        turno_id=data["turnos_cobro"]["sena"],
    )
    assert creado.status_code == 201, creado.text
    cobro_id = creado.json()["id"]

    async def mover() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE turnos SET inicio = :inicio, fin = :fin "
                    "WHERE id = :id"
                ),
                {
                    "id": data["turnos_cobro"]["sena"],
                    "inicio": datetime.now(timezone.utc)
                    + timedelta(hours=2),
                    "fin": datetime.now(timezone.utc) + timedelta(hours=3),
                },
            )

    run(mover())
    perdida = api_client.patch(
        f"/turnos/{data['turnos_cobro']['sena']}/estado",
        json={"estado": "cancelado"},
        headers={
            **bearer(data["actores"]["recepcionista"]),
            "User-Agent": _UA_PERDER,
        },
    )
    assert perdida.status_code == 200, perdida.text

    filas = [
        fila
        for fila in _cobros_audit(session_factory)
        if fila.accion == "cobro.perder"
    ]
    assert len(filas) == 1
    assert filas[0].entidad_id == cobro_id
    assert filas[0].usuario_id == data["actores"]["recepcionista"].id
    assert filas[0].ip == "testclient"
    assert filas[0].dispositivo == _UA_PERDER


def test_escrituras_rechazadas_no_dejan_auditoria(
    api_client, session_factory
) -> None:
    """Business error: every rejected path leaves the audit trail untouched."""
    data = _setup(session_factory)
    antes = len(_cobros_audit(session_factory))

    assert _crear_efectivo(api_client, data, monto="0").status_code == 422
    assert (
        _crear_efectivo(
            api_client,
            data,
            tipo="sena",
            monto="9999.00",
            turno_id=data["turnos_cobro"]["sena"],
        ).status_code
        == 422
    )
    assert (
        _crear_efectivo(
            api_client, data, paciente_id=uuid.uuid4()
        ).status_code
        == 404
    )
    assert len(_cobros_audit(session_factory)) == antes

    # A valid deposit audits once; a duplicate is rejected without a new row.
    valido = _crear_efectivo(
        api_client,
        data,
        tipo="sena",
        monto="10000.00",
        turno_id=data["turnos_cobro"]["sena"],
    )
    assert valido.status_code == 201, valido.text
    assert (
        _crear_efectivo(
            api_client,
            data,
            tipo="sena",
            monto="10000.00",
            turno_id=data["turnos_cobro"]["sena"],
        ).status_code
        == 409
    )
    assert len(_cobros_audit(session_factory)) == antes + 1

    # Webhooks with an invalid signature or a mismatching amount add nothing.
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        mp_body = _crear_mp(
            api_client,
            data,
            cliente,
            turno_key="ajeno",
            paciente_id=data["paciente_ajeno"].id,
        )
        cobro_id = uuid.UUID(mp_body["id"])
        cliente.simular_pago(
            pago(
                cobro_id=cobro_id,
                monto="9999.00",
                pago_id="mp-audit-bad",
            )
        )
        assert (
            api_client.post(
                "/webhooks/mercadopago",
                json=webhook_payload("mp-audit-bad"),
                headers={
                    "x-signature": "ts=1,v1=" + ("0" * 64),
                    "x-request-id": "req-bad",
                },
            ).status_code
            == 401
        )
        assert (
            api_client.post(
                "/webhooks/mercadopago",
                json=webhook_payload("mp-audit-bad"),
                headers=firma_mp("mp-audit-bad"),
            ).status_code
            == 409
        )
    conciliaciones = [
        fila
        for fila in _cobros_audit(session_factory)
        if fila.accion == "cobro.conciliar"
    ]
    assert conciliaciones == []


async def _sqlstate_de(session_factory, statement: str, params) -> str | None:
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_auditoria_de_cobros_es_append_only_p0001(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creado = _crear_efectivo(api_client, data)
    assert creado.status_code == 201, creado.text
    fila = _cobros_audit(session_factory)[0]

    assert (
        run(
            _sqlstate_de(
                session_factory,
                "UPDATE registro_auditoria SET accion = 'alterado' "
                "WHERE id = :id",
                {"id": fila.id},
            )
        )
        == "P0001"
    )
    assert (
        run(
            _sqlstate_de(
                session_factory,
                "DELETE FROM registro_auditoria WHERE id = :id",
                {"id": fila.id},
            )
        )
        == "P0001"
    )
    assert len(_cobros_audit(session_factory)) == 1


def test_caja_abrir_movimiento_cerrar_auditan(
    api_client, session_factory
) -> None:
    """Expected: the three register actions carry user, IP and device."""
    data = _setup(session_factory, con_caja=False)
    headers = {
        **bearer(data["actores"]["recepcionista"]),
        "User-Agent": _UA_PERDER,
    }
    apertura = api_client.post(
        "/caja/abrir",
        json={"monto_apertura": "10000.00"},
        headers=headers,
    )
    assert apertura.status_code == 201, apertura.text
    caja_id = apertura.json()["id"]

    movimiento = api_client.post(
        "/caja/movimientos",
        json={
            "tipo": "gasto",
            "concepto": "Insumos",
            "monto": "1000.00",
        },
        headers=headers,
    )
    assert movimiento.status_code == 201, movimiento.text

    cierre = api_client.post(
        "/caja/cerrar",
        json={"monto_contado": "9000.00"},
        headers=headers,
    )
    assert cierre.status_code == 200, cierre.text

    filas = {fila.accion: fila for fila in _caja_audit(session_factory)}
    assert set(filas) == {
        "caja.abrir",
        "caja.movimiento",
        "caja.cerrar",
    }
    for fila in filas.values():
        assert fila.entidad == "caja"
        assert fila.entidad_id == caja_id
        assert fila.usuario_id == data["actores"]["recepcionista"].id
        assert fila.ip == "testclient"
        assert fila.dispositivo == _UA_PERDER


def test_cobro_reembolsar_audita(api_client, session_factory) -> None:
    data = _setup(session_factory)
    creado = _crear_efectivo(api_client, data)
    assert creado.status_code == 201, creado.text
    respuesta = api_client.post(
        f"/cobros/{creado.json()['id']}/reembolsar",
        headers={
            **bearer(data["actores"]["administrador"]),
            "User-Agent": _UA_PERDER,
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    filas = run(auditorias(session_factory, "cobro.reembolsar"))
    assert len(filas) == 1
    assert filas[0].entidad_id == creado.json()["id"]
    assert filas[0].usuario_id == data["actores"]["administrador"].id
    assert filas[0].ip == "testclient"
    assert filas[0].dispositivo == _UA_PERDER


def test_caja_rechazos_no_dejan_auditoria(
    api_client, session_factory
) -> None:
    """Business error: rejected register writes add no caja.* rows."""
    data = _setup(session_factory, con_caja=False)
    headers = {
        **bearer(data["actores"]["recepcionista"]),
        "User-Agent": _UA_PERDER,
    }
    antes = len(_caja_audit(session_factory))
    assert (
        api_client.post(
            "/caja/abrir",
            json={"monto_apertura": "-1.00"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        api_client.post(
            "/caja/movimientos",
            json={
                "tipo": "gasto",
                "concepto": "Insumos",
                "monto": "10.00",
            },
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        api_client.post(
            "/caja/cerrar",
            json={"monto_contado": "0.00"},
            headers=headers,
        ).status_code
        == 404
    )
    assert len(_caja_audit(session_factory)) == antes
