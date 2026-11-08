"""C-13 RBAC on /cobros: admin/reception write, dentist owns, others read."""

import uuid

from sqlalchemy import func, select

from app.models.caja import Cobro
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.cobros_helpers import cobro_payload, setup_cobros
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_cobros(session_factory))


def _post(api_client, data, actor: str, **overrides):
    return api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers=bearer(data["actores"][actor]),
    )


def _contar(session_factory) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count()).select_from(Cobro)
            )

    return run(contar())


def test_administrador_crea_lista_y_lee(api_client, session_factory) -> None:
    """Expected: admin creates any payment and reads the list/detail."""
    data = _setup(session_factory)
    creado = _post(api_client, data, "administrador")
    assert creado.status_code == 201, creado.text
    cobro_id = creado.json()["id"]

    listado = api_client.get(
        "/cobros", headers=bearer(data["actores"]["administrador"])
    )
    assert listado.status_code == 200, listado.text
    assert cobro_id in {cobro["id"] for cobro in listado.json()}

    ficha = api_client.get(
        f"/cobros/{cobro_id}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert ficha.status_code == 200, ficha.text
    assert ficha.json()["id"] == cobro_id


def test_recepcion_crea_y_lista_pero_no_borra(
    api_client, session_factory
) -> None:
    """Expected: reception creates/reads; there is no delete route."""
    data = _setup(session_factory)
    creado = _post(api_client, data, "recepcionista")
    assert creado.status_code == 201, creado.text
    assert (
        api_client.get(
            "/cobros", headers=bearer(data["actores"]["recepcionista"])
        ).status_code
        == 200
    )
    borrado = api_client.delete(
        f"/cobros/{creado.json()['id']}",
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert borrado.status_code in {403, 405}, borrado.text
    assert _contar(session_factory) == 1


def test_odontologo_solo_ve_y_lee_los_propios(
    api_client, session_factory
) -> None:
    """Business rule: own turn/budget only; a foreign detail is 403."""
    data = _setup(session_factory)
    propio = run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="sena",
            medio="mercadopago",
            estado="pendiente",
            monto="10000.00",
            turno_id=data["turnos_cobro"]["sena"],
        )
    )
    ajeno = run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_ajeno"].id,
            tipo="sena",
            medio="mercadopago",
            estado="pendiente",
            monto="10000.00",
            turno_id=data["turnos_cobro"]["ajeno"],
        )
    )
    sin_profesional = run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="otro",
            medio="efectivo",
            estado="aprobado",
            monto="1000.00",
        )
    )
    headers = bearer(data["actores"]["odontologo"])

    listado = api_client.get("/cobros", headers=headers)
    assert listado.status_code == 200, listado.text
    vistos = {cobro["id"] for cobro in listado.json()}
    assert vistos == {str(propio)}
    assert str(ajeno) not in vistos
    assert str(sin_profesional) not in vistos

    assert api_client.get(f"/cobros/{propio}", headers=headers).status_code == 200
    assert (
        api_client.get(f"/cobros/{ajeno}", headers=headers).status_code == 403
    )
    assert (
        api_client.get(f"/cobros/{sin_profesional}", headers=headers).status_code
        == 403
    )


def test_asistente_sin_acceso_y_odontologo_no_escribe(
    api_client, session_factory
) -> None:
    """Business rule: assistant 403 everywhere; dentist cannot create."""
    data = _setup(session_factory)
    asistente = bearer(data["actores"]["asistente"])
    assert api_client.get("/cobros", headers=asistente).status_code == 403
    assert _post(api_client, data, "asistente").status_code == 403

    odontologo = bearer(data["actores"]["odontologo"])
    assert _post(api_client, data, "odontologo").status_code == 403


def test_auditor_solo_lee(api_client, session_factory) -> None:
    """Expected: audit reads list/detail and cannot create."""
    data = _setup(session_factory)
    creado = _post(api_client, data, "administrador")
    assert creado.status_code == 201, creado.text
    headers = bearer(data["actores"]["auditor"])

    assert api_client.get("/cobros", headers=headers).status_code == 200
    assert (
        api_client.get(
            f"/cobros/{creado.json()['id']}", headers=headers
        ).status_code
        == 200
    )
    assert _post(api_client, data, "auditor").status_code == 403


def test_peticion_sin_token_es_401(api_client, session_factory) -> None:
    """Business rule: reads/writes require a Bearer, except the webhook."""
    data = _setup(session_factory)
    assert api_client.get("/cobros").status_code == 401
    assert api_client.post(
        "/cobros", json=cobro_payload(data)
    ).status_code == 401


def _headers(data, actor: str) -> dict[str, str]:
    return bearer(data["actores"][actor])


def test_recepcion_opera_caja_y_no_borra(api_client, session_factory) -> None:
    """Expected: reception opens/moves/closes; there is no DELETE route."""
    data = run(setup_cobros(session_factory, con_caja=False))
    headers = _headers(data, "recepcionista")
    apertura = api_client.post(
        "/caja/abrir",
        json={"monto_apertura": "0.00"},
        headers=headers,
    )
    assert apertura.status_code == 201, apertura.text
    movimiento = api_client.post(
        "/caja/movimientos",
        json={
            "tipo": "ingreso",
            "concepto": "Ingreso manual",
            "monto": "1000.00",
        },
        headers=headers,
    )
    assert movimiento.status_code == 201, movimiento.text
    cierre = api_client.post(
        "/caja/cerrar", json={"monto_contado": "1000.00"}, headers=headers
    )
    assert cierre.status_code == 200, cierre.text
    borrado = api_client.delete("/caja", headers=headers)
    assert borrado.status_code in {403, 405}, borrado.text


def test_odontologo_y_asistente_sin_acceso_a_caja(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    for actor in ("odontologo", "asistente"):
        headers = _headers(data, actor)
        assert api_client.get("/caja", headers=headers).status_code == 403
        assert (
            api_client.get("/caja/arqueo", headers=headers).status_code
            == 403
        )
        assert (
            api_client.post(
                "/caja/abrir",
                json={"monto_apertura": "0.00"},
                headers=headers,
            ).status_code
            == 403
        )


def test_auditor_lee_caja_pero_no_escribe(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = _headers(data, "auditor")
    assert api_client.get("/caja", headers=headers).status_code == 200
    assert (
        api_client.get("/caja/movimientos", headers=headers).status_code
        == 200
    )
    assert (
        api_client.get("/caja/arqueo", headers=headers).status_code == 200
    )
    assert (
        api_client.post(
            "/caja/abrir",
            json={"monto_apertura": "0.00"},
            headers=headers,
        ).status_code
        == 403
    )


def test_caja_sin_token_es_401(api_client, session_factory) -> None:
    data = _setup(session_factory)
    assert api_client.get("/caja").status_code == 401
    assert api_client.get("/caja/arqueo").status_code == 401
    assert api_client.post(
        "/caja/abrir", json={"monto_apertura": "0.00"}
    ).status_code == 401
