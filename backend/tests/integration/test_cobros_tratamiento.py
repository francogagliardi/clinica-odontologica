"""C-13 treatment payments: partial copay, balance and budget states."""

import uuid

from sqlalchemy import select

from app.models.comercial import Presupuesto
from tests.integration.cobros_helpers import (
    cobro_payload,
    setup_cobros,
)
from tests.integration.helpers import run
from tests.integration.presupuestos_helpers import insertar_presupuesto_db
from tests.integration.recursos_helpers import bearer

_UA = "pytest-ua-c13-tratamiento"


def _setup(session_factory) -> dict[str, object]:
    return run(setup_cobros(session_factory))


def _post(api_client, data, *, actor: str = "recepcionista", **overrides):
    return api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers={**bearer(data["actores"][actor]), "User-Agent": _UA},
    )


def _tratamiento(api_client, data, monto: str, **overrides):
    valores = {
        "tipo": "tratamiento",
        "medio": "efectivo",
        "monto": monto,
        "presupuesto_id": data["presupuesto_cobro"],
    }
    valores.update(overrides)
    return _post(api_client, data, **valores)


def _estado_presupuesto(session_factory, presupuesto_id) -> str:
    async def leer() -> str:
        async with session_factory() as session:
            presupuesto = await session.get(Presupuesto, presupuesto_id)
            assert presupuesto is not None
            return presupuesto.estado

    return run(leer())


def test_pago_parcial_informa_saldo_y_no_cambia_el_presupuesto(
    api_client, session_factory
) -> None:
    """Expected: 201 with the remaining balance; budget state is C-12's job."""
    data = _setup(session_factory)
    respuesta = _tratamiento(api_client, data, "20000.00")
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["tipo"] == "tratamiento"
    assert body["estado"] == "aprobado"
    assert body["saldo_pendiente"] == "30000.00"
    assert _estado_presupuesto(
        session_factory, data["presupuesto_cobro"]
    ) == "aceptado"


def test_presupuesto_no_cobrable_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: only accepted or in-progress budgets are chargeable."""
    data = _setup(session_factory)
    for estado in ("borrador", "rechazado", "finalizado"):
        presupuesto_id = run(
            insertar_presupuesto_db(
                session_factory,
                consultorio_id=data["consultorio_id"],
                paciente_id=data["paciente_os_demo"].id,
                profesional_id=data["profesional"].id,
                creado_por=data["actores"]["administrador"].id,
                estado=estado,
                subtotal="50000.00",
                cobertura_calculada="0.00",
                copago="50000.00",
            )
        )
        respuesta = _tratamiento(
            api_client,
            data,
            "1000.00",
            presupuesto_id=presupuesto_id,
        )
        assert respuesta.status_code == 409, respuesta.text


def test_cobro_que_excede_el_copago_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: approved payments cannot exceed the copayment."""
    data = _setup(session_factory)
    primero = _tratamiento(api_client, data, "40000.00")
    assert primero.status_code == 201, primero.text
    exceso = _tratamiento(api_client, data, "15000.00")
    assert exceso.status_code == 409, exceso.text


def test_pagos_parciales_suman_exactamente_el_copago(
    api_client, session_factory
) -> None:
    """Edge: two partial payments may add up to the copay, not one cent more."""
    data = _setup(session_factory)
    primero = _tratamiento(api_client, data, "20000.00")
    assert primero.status_code == 201, primero.text
    segundo = _tratamiento(api_client, data, "30000.00")
    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["saldo_pendiente"] == "0.00"

    tercero = _tratamiento(api_client, data, "0.01")
    assert tercero.status_code == 409, tercero.text


def test_presupuesto_de_otro_paciente_devuelve_422(
    api_client, session_factory
) -> None:
    """Business error: the budget must belong to the charged patient."""
    data = _setup(session_factory)
    respuesta = _tratamiento(
        api_client,
        data,
        "1000.00",
        presupuesto_id=data["presupuesto_ajeno_cobro"],
    )
    assert respuesta.status_code == 422, respuesta.text


def test_presupuesto_inexistente_o_de_otro_consultorio_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    inexistente = _tratamiento(
        api_client, data, "1000.00", presupuesto_id=uuid.uuid4()
    )
    assert inexistente.status_code == 404

    async def crear_ajeno() -> uuid.UUID:
        from tests.integration.clinica_helpers import otro_consultorio

        ajeno = await otro_consultorio(session_factory)
        return await insertar_presupuesto_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente_id"],
            profesional_id=data["profesional"].id,
            creado_por=data["actores"]["administrador"].id,
            estado="aceptado",
            subtotal="10000.00",
            cobertura_calculada="0.00",
            copago="10000.00",
        )

    presupuesto_ajeno = run(crear_ajeno())
    ajeno = _tratamiento(
        api_client, data, "1000.00", presupuesto_id=presupuesto_ajeno
    )
    assert ajeno.status_code == 404


def test_presupuesto_en_curso_es_cobrable(api_client, session_factory) -> None:
    """Edge: an in-progress treatment still accepts partial payments."""
    data = _setup(session_factory)
    presupuesto_id = run(
        insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            profesional_id=data["profesional"].id,
            creado_por=data["actores"]["administrador"].id,
            estado="en_curso",
            subtotal="10000.00",
            cobertura_calculada="0.00",
            copago="10000.00",
        )
    )
    respuesta = _tratamiento(
        api_client, data, "10000.00", presupuesto_id=presupuesto_id
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["saldo_pendiente"] == "0.00"
