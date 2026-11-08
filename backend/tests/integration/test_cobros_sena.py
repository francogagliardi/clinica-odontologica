"""C-13 deposits: only the required service, exact amount, one live deposit."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models.caja import Cobro
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.cobros_helpers import (
    cobro_payload,
    leer_turno,
    setup_cobros,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer
from tests.integration.turnos_helpers import insertar_turno_db

_UA = "pytest-ua-c13-sena"


def _setup(session_factory) -> dict[str, object]:
    return run(setup_cobros(session_factory))


def _post(api_client, data, *, actor: str = "recepcionista", **overrides):
    return api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers={**bearer(data["actores"][actor]), "User-Agent": _UA},
    )


def _sena(api_client, data, **overrides):
    valores = {
        "tipo": "sena",
        "medio": "efectivo",
        "monto": "10000.00",
        "turno_id": data["turnos_cobro"]["sena"],
    }
    valores.update(overrides)
    return _post(api_client, data, **valores)


def _contar(session_factory) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count()).select_from(Cobro)
            )

    return run(contar())


def _sena_estado(session_factory, turno_id: uuid.UUID) -> str | None:
    async def leer() -> str | None:
        turno = await leer_turno(session_factory, turno_id)
        return turno.sena_estado if turno else None

    return run(leer())


def test_sena_valida_marca_el_turno_pagado(api_client, session_factory) -> None:
    """Expected: 201 approved and `Turno.sena_estado='pagada'` in the same tx."""
    data = _setup(session_factory)
    respuesta = _sena(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["tipo"] == "sena"
    assert body["monto"] == "10000.00"
    assert body["estado"] == "aprobado"
    assert body["turno_id"] == str(data["turnos_cobro"]["sena"])
    assert _sena_estado(session_factory, data["turnos_cobro"]["sena"]) == (
        "pagada"
    )


def test_prestacion_sin_sena_devuelve_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    respuesta = _post(
        api_client,
        data,
        tipo="sena",
        medio="efectivo",
        monto="10000.00",
        turno_id=data["turnos_cobro"]["sin_sena"],
    )
    assert respuesta.status_code == 422, respuesta.text
    assert _contar(session_factory) == 0


def test_turno_sin_prestacion_devuelve_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = _post(
        api_client,
        data,
        tipo="sena",
        medio="efectivo",
        monto="10000.00",
        turno_id=data["turnos_cobro"]["sin_prestacion"],
    )
    assert respuesta.status_code == 422, respuesta.text
    assert _contar(session_factory) == 0


def test_monto_distinto_del_monto_sena_devuelve_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    for monto in ("9999.99", "10000.01", "1.00"):
        respuesta = _sena(api_client, data, monto=monto)
        assert respuesta.status_code == 422, respuesta.text
    assert _contar(session_factory) == 0
    assert _sena_estado(session_factory, data["turnos_cobro"]["sena"]) == (
        "pendiente"
    )


@pytest.mark.parametrize("turno", ["cancelado", "ausente"])
def test_turno_no_activo_devuelve_422(
    api_client, session_factory, turno: str
) -> None:
    data = _setup(session_factory)
    respuesta = _post(
        api_client,
        data,
        tipo="sena",
        medio="efectivo",
        monto="10000.00",
        turno_id=data["turnos_cobro"][turno],
    )
    assert respuesta.status_code == 422, respuesta.text
    assert _contar(session_factory) == 0


def test_segunda_sena_viva_devuelve_409(api_client, session_factory) -> None:
    """Business error: one live deposit per appointment, enforced by the DB."""
    data = _setup(session_factory)
    primera = _sena(api_client, data)
    assert primera.status_code == 201, primera.text
    segunda = _sena(api_client, data)
    assert segunda.status_code == 409, segunda.text
    assert _contar(session_factory) == 1


def test_reintento_tras_rechazo_es_201(api_client, session_factory) -> None:
    """Edge: a rejected deposit no longer blocks a new attempt."""
    data = _setup(session_factory)
    run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="sena",
            medio="mercadopago",
            estado="rechazado",
            monto="10000.00",
            turno_id=data["turnos_cobro"]["sena"],
        )
    )
    respuesta = _sena(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    assert _contar(session_factory) == 2


def test_sena_perdida_no_se_reemplaza(api_client, session_factory) -> None:
    """Business error: a lost deposit is already resolved, so it is 409."""
    data = _setup(session_factory)
    run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="sena",
            medio="mercadopago",
            estado="perdido",
            monto="10000.00",
            turno_id=data["turnos_cobro"]["sena"],
        )
    )
    respuesta = _sena(api_client, data)
    assert respuesta.status_code == 409, respuesta.text
    assert _contar(session_factory) == 1


def test_dos_altas_concurrentes_de_sena(api_client, session_factory) -> None:
    """Edge: exactly one 201 and one 409; PostgreSQL resolves the race."""
    data = _setup(session_factory)
    headers = {**bearer(data["actores"]["recepcionista"]), "User-Agent": _UA}
    payload = cobro_payload(
        data,
        tipo="sena",
        medio="efectivo",
        monto="10000.00",
        turno_id=data["turnos_cobro"]["sena"],
    )

    def crear(_: int) -> int:
        return api_client.post(
            "/cobros", json=payload, headers=headers
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(pool.map(crear, range(2)))
    assert sorted(estados) == [201, 409], estados
    assert _contar(session_factory) == 1


def test_turno_inexistente_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    """Business error: an unknown/foreign turn cannot be charged."""
    data = _setup(session_factory)
    assert _sena(api_client, data, turno_id=uuid.uuid4()).status_code == 404

    async def crear_ajeno() -> uuid.UUID:
        from tests.integration.clinica_helpers import otro_consultorio

        ajeno = await otro_consultorio(session_factory)
        return await insertar_turno_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            profesional_id=data["profesional"].id,
            sillon_id=data["sillon"].id,
            prestacion_id=data["endo"].id,
            inicio=data["ahora"],
            fin=data["ahora"] + timedelta(minutes=90),
            sena_estado="pendiente",
        )

    turno_ajeno = run(crear_ajeno())
    respuesta = _sena(api_client, data, turno_id=turno_ajeno)
    assert respuesta.status_code == 404, respuesta.text
    assert _contar(session_factory) == 0
