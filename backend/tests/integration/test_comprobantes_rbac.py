"""C-14 group 10.1: receipt RBAC matrix (D11)."""

import uuid

from app.models import Comprobante
from tests.integration.comprobantes_helpers import (
    crear_cobro_db,
    setup_comprobantes,
)
from tests.integration.fiscal_helpers import insertar_comprobante_db
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    data = run(setup_comprobantes(session_factory))
    cobro_id = run(crear_cobro_db(session_factory, data))
    comprobante_id = run(
        insertar_comprobante_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            cobro_id=cobro_id,
            paciente_id=data["paciente_os_demo"].id,
            estado="emitido",
            numero_interno=1,
        )
    )
    return {**data, "comprobante_id": comprobante_id}


def test_lectura_para_los_cuatro_roles(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    for actor in (
        "administrador",
        "recepcionista",
        "odontologo",
        "auditor",
    ):
        headers = bearer(data["actores"][actor])
        assert (
            api_client.get("/comprobantes", headers=headers).status_code
            == 200
        ), actor
        assert (
            api_client.get(
                f"/comprobantes/{data['comprobante_id']}",
                headers=headers,
            ).status_code
            == 200
        ), actor


def test_reintento_para_administrador_y_recepcion(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    for actor in ("administrador", "recepcionista"):
        respuesta = api_client.post(
            f"/comprobantes/{data['comprobante_id']}/reintentar",
            headers=bearer(data["actores"][actor]),
        )
        assert respuesta.status_code == 200, (actor, respuesta.text)


def test_envio_para_administrador_y_recepcion(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    primero = api_client.post(
        f"/comprobantes/{data['comprobante_id']}/enviar",
        json={"canal": "whatsapp"},
        headers=bearer(data["actores"]["administrador"]),
    )
    assert primero.status_code == 201, primero.text
    segundo = api_client.post(
        f"/comprobantes/{data['comprobante_id']}/enviar",
        json={"canal": "whatsapp"},
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert segundo.status_code == 200, segundo.text


def test_asistente_sin_acceso(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["asistente"])
    assert api_client.get("/comprobantes", headers=headers).status_code == 403
    assert (
        api_client.get(
            f"/comprobantes/{data['comprobante_id']}", headers=headers
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            f"/comprobantes/{data['comprobante_id']}/reintentar",
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            f"/comprobantes/{data['comprobante_id']}/enviar",
            json={"canal": "whatsapp"},
            headers=headers,
        ).status_code
        == 403
    )


def test_odontologo_no_escribe(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["odontologo"])
    assert (
        api_client.post(
            f"/comprobantes/{data['comprobante_id']}/reintentar",
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            f"/comprobantes/{data['comprobante_id']}/enviar",
            json={"canal": "whatsapp"},
            headers=headers,
        ).status_code
        == 403
    )
    comprobante = run(
        _leer(session_factory, data["comprobante_id"])
    )
    assert comprobante is not None and comprobante.cae is not None


def test_sin_token_devuelve_401(api_client, session_factory) -> None:
    data = _setup(session_factory)
    assert api_client.get("/comprobantes").status_code == 401
    assert (
        api_client.get(
            f"/comprobantes/{data['comprobante_id']}"
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            f"/comprobantes/{data['comprobante_id']}/reintentar"
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            f"/comprobantes/{data['comprobante_id']}/enviar",
            json={"canal": "whatsapp"},
        ).status_code
        == 401
    )


async def _leer(session_factory, comprobante_id) -> Comprobante | None:
    async with session_factory() as session:
        return await session.get(Comprobante, comprobante_id)
