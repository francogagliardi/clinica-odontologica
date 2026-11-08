"""C-13 deposit loss: backoffice/public parity, no reversal, idempotent."""

import uuid
from datetime import datetime, timedelta, timezone

import app.application.cobros as cobros_app
from sqlalchemy import text

from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.mercadopago import TestMercadoPagoClient
from tests.integration.clinica_helpers import auditorias
from tests.integration.cobros_helpers import (
    cobro_payload,
    leer_cobro,
    leer_turno,
    movimientos_de,
    mp_override,
    setup_cobros,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


def _setup(session_factory, *, con_caja: bool = True) -> dict[str, object]:
    return run(setup_cobros(session_factory, con_caja=con_caja))


async def _mover_turno(
    session_factory, turno_id: uuid.UUID, inicio: datetime
) -> None:
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE turnos SET inicio = :inicio, "
                "fin = :fin WHERE id = :id"
            ),
            {
                "id": turno_id,
                "inicio": inicio,
                "fin": inicio + timedelta(minutes=90),
            },
        )


def _cambiar(api_client, data, turno_id, estado: str):
    return api_client.patch(
        f"/turnos/{turno_id}/estado",
        json={"estado": estado},
        headers=bearer(data["actores"]["recepcionista"]),
    )


def _pagar_sena(api_client, data, **overrides):
    respuesta = api_client.post(
        "/cobros",
        json=cobro_payload(
            data,
            tipo="sena",
            medio="efectivo",
            monto="10000.00",
            turno_id=data["turnos_cobro"]["sena"],
            **overrides,
        ),
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert respuesta.status_code == 201, respuesta.text
    return uuid.UUID(respuesta.json()["id"])


def test_cancelacion_tardia_desde_backoffice_pierde_la_sena(
    api_client, session_factory
) -> None:
    """Expected: cancelled late, deposit lost, cash income preserved."""
    data = _setup(session_factory)
    cobro_id = _pagar_sena(api_client, data)
    turno_id = data["turnos_cobro"]["sena"]
    run(
        _mover_turno(
            session_factory,
            turno_id,
            datetime.now(timezone.utc) + timedelta(hours=2),
        )
    )

    respuesta = _cambiar(api_client, data, turno_id, "cancelado")
    assert respuesta.status_code == 200, respuesta.text
    turno = run(leer_turno(session_factory, turno_id))
    assert turno is not None
    assert turno.estado == "cancelado"
    assert turno.sena_estado == "perdida"

    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "perdido"
    # The clinic keeps the money: no reversing movement is created.
    assert len(run(movimientos_de(session_factory, cobro_id))) == 1
    assert len(run(auditorias(session_factory, "cobro.perder"))) == 1


def test_cancelacion_dentro_del_plazo_conserva_pagada(
    api_client, session_factory
) -> None:
    """Expected: cancelling 30 h ahead keeps the deposit paid."""
    data = _setup(session_factory)
    cobro_id = _pagar_sena(api_client, data)
    turno_id = data["turnos_cobro"]["sena"]
    run(
        _mover_turno(
            session_factory,
            turno_id,
            datetime.now(timezone.utc) + timedelta(hours=30),
        )
    )

    respuesta = _cambiar(api_client, data, turno_id, "cancelado")
    assert respuesta.status_code == 200, respuesta.text
    turno = run(leer_turno(session_factory, turno_id))
    assert turno is not None and turno.sena_estado == "pagada"
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "aprobado"
    assert run(auditorias(session_factory, "cobro.perder")) == []


def test_limite_exacto_no_pierde_la_sena(
    api_client, session_factory, monkeypatch
) -> None:
    """Edge: exactly `inicio - plazo` is not late (agenda/turnos scenario)."""
    data = _setup(session_factory)
    cobro_id = _pagar_sena(api_client, data)
    turno_id = data["turnos_cobro"]["sena"]
    fijo = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(cobros_app, "ahora_utc", lambda: fijo)
    run(
        _mover_turno(
            session_factory, turno_id, fijo + timedelta(hours=24)
        )
    )

    respuesta = _cambiar(api_client, data, turno_id, "cancelado")
    assert respuesta.status_code == 200, respuesta.text
    turno = run(leer_turno(session_factory, turno_id))
    assert turno is not None and turno.sena_estado == "pagada"
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "aprobado"


def test_ausentismo_pierde_la_sena(api_client, session_factory) -> None:
    """Expected: marking `ausente` loses the deposit regardless of the clock."""
    data = _setup(session_factory)
    cobro_id = _pagar_sena(api_client, data)
    turno_id = data["turnos_cobro"]["sena"]
    run(
        _mover_turno(
            session_factory,
            turno_id,
            datetime.now(timezone.utc) + timedelta(days=30),
        )
    )

    respuesta = _cambiar(api_client, data, turno_id, "ausente")
    assert respuesta.status_code == 200, respuesta.text
    turno = run(leer_turno(session_factory, turno_id))
    assert turno is not None
    assert turno.estado == "ausente" and turno.sena_estado == "perdida"
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "perdido"


def test_turno_sin_sena_no_cambia(api_client, session_factory) -> None:
    """Edge: `no_requiere` stays untouched on a late cancellation."""
    data = _setup(session_factory)
    turno_id = data["turnos_cobro"]["sin_sena"]
    run(
        _mover_turno(
            session_factory,
            turno_id,
            datetime.now(timezone.utc) + timedelta(hours=2),
        )
    )
    respuesta = _cambiar(api_client, data, turno_id, "cancelado")
    assert respuesta.status_code == 200, respuesta.text
    turno = run(leer_turno(session_factory, turno_id))
    assert turno is not None and turno.sena_estado == "no_requiere"
    assert run(auditorias(session_factory, "cobro.perder")) == []


def test_perdida_repetida_es_idempotente(
    api_client, session_factory
) -> None:
    """Edge: repeating `ausente` does not duplicate audit nor movements."""
    data = _setup(session_factory)
    cobro_id = _pagar_sena(api_client, data)
    turno_id = data["turnos_cobro"]["sena"]
    assert _cambiar(api_client, data, turno_id, "ausente").status_code == 200
    assert _cambiar(api_client, data, turno_id, "ausente").status_code == 200
    assert len(run(auditorias(session_factory, "cobro.perder"))) == 1
    assert len(run(movimientos_de(session_factory, cobro_id))) == 1


def test_sena_pendiente_se_pierde_sin_ingreso(
    api_client, session_factory
) -> None:
    """Expected: an unpaid MP deposit becomes lost with no cash movement."""
    data = _setup(session_factory, con_caja=False)
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        respuesta = api_client.post(
            "/cobros",
            json=cobro_payload(
                data,
                tipo="sena",
                medio="mercadopago",
                monto="10000.00",
                turno_id=data["turnos_cobro"]["sena"],
            ),
            headers=bearer(data["actores"]["recepcionista"]),
        )
    assert respuesta.status_code == 201, respuesta.text
    cobro_id = uuid.UUID(respuesta.json()["id"])
    turno_id = data["turnos_cobro"]["sena"]
    run(
        _mover_turno(
            session_factory,
            turno_id,
            datetime.now(timezone.utc) + timedelta(hours=2),
        )
    )

    assert _cambiar(api_client, data, turno_id, "cancelado").status_code == 200
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "perdido"
    assert run(movimientos_de(session_factory, cobro_id)) == []


def test_cancelacion_publica_mantiene_la_politica(
    api_client, session_factory
) -> None:
    """Edge: the public link loses the deposit exactly like the backoffice."""
    data = _setup(session_factory)
    inicio = datetime(2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET)
    reserva = api_client.post(
        "/reservar/demo/turnos",
        json={
            "nombre": "Sena",
            "apellido": "Publica",
            "dni": "43999001",
            "telefono": "11 7777-9901",
            "email": "sena.publica@example.test",
            "profesional_id": str(data["profesional"].id),
            "prestacion_id": str(data["endo"].id),
            "inicio": inicio.isoformat(),
        },
    )
    assert reserva.status_code == 201, reserva.text
    cuerpo = reserva.json()
    turno_id = uuid.UUID(cuerpo["turno_id"])
    token = cuerpo["gestion_url"].rsplit("/", 1)[-1]
    turno = run(leer_turno(session_factory, turno_id))
    assert turno is not None

    sena = api_client.post(
        "/cobros",
        json=cobro_payload(
            data,
            paciente_id=turno.paciente_id,
            tipo="sena",
            medio="efectivo",
            monto="10000.00",
            turno_id=turno_id,
        ),
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert sena.status_code == 201, sena.text
    cobro_id = uuid.UUID(sena.json()["id"])

    run(
        _mover_turno(
            session_factory,
            turno_id,
            datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    cancelada = api_client.post(f"/reservar/gestion/{token}/cancelar")
    assert cancelada.status_code == 200, cancelada.text
    assert cancelada.json() == {
        "estado": "cancelado",
        "sena_perdida": True,
    }
    perdido = run(leer_turno(session_factory, turno_id))
    assert perdido is not None and perdido.sena_estado == "perdida"
    cobro = run(leer_cobro(session_factory, cobro_id))
    assert cobro is not None and cobro.estado == "perdido"
