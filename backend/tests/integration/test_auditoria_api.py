"""`GET /auditoria` viewer on real PostgreSQL (C-16, task 5.1).

Order `timestamp DESC, id DESC`, combined filters, total before pagination,
bounded limit/offset, inclusive UTC-3 borders, empty table, soft-deleted user,
strict 422 and 405 on write methods.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.agenda import ARGENTINA_OFFSET
from tests.integration.acceso_helpers import bearer_de, setup_acceso
from tests.integration.auditoria_helpers import (
    contar_auditoria,
    insertar_auditoria,
)
from tests.integration.helpers import run

URL = "/auditoria"


def _momento(hora: int = 12, dia: int = 5) -> datetime:
    return datetime(2026, 11, dia, hora, 0, tzinfo=ARGENTINA_OFFSET)


@pytest.fixture
async def acceso(session_factory: async_sessionmaker[AsyncSession]) -> dict:
    return await setup_acceso(session_factory)


def _admin_headers(acceso: dict) -> dict[str, str]:
    return bearer_de(acceso["admin"].id)


@pytest.mark.anyio
async def test_listado_orden_estable_y_campos(
    api_client, acceso, session_factory
) -> None:
    admin = acceso["admin"]
    primero = uuid.UUID("00000000-0000-0000-0000-000000000001")
    segundo = uuid.UUID("00000000-0000-0000-0000-000000000002")
    await insertar_auditoria(
        session_factory,
        [
            (
                primero,
                admin.id,
                "usuario.crear",
                "usuario",
                "u-1",
                _momento(),
            ),
            (
                segundo,
                admin.id,
                "usuario.editar",
                "usuario",
                "u-2",
                _momento(),
            ),
        ],
        ip="10.0.0.9",
        dispositivo="visor-test",
    )

    response = api_client.get(URL, headers=_admin_headers(acceso))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["limite"] == 100
    assert body["offset"] == 0
    # Same timestamp: the second id wins because ordering is id DESC.
    assert [fila["id"] for fila in body["filas"]] == [
        str(segundo),
        str(primero),
    ]
    fila = body["filas"][0]
    assert fila["usuario_id"] == str(admin.id)
    assert fila["usuario_email"] == admin.email
    assert fila["accion"] == "usuario.editar"
    assert fila["entidad"] == "usuario"
    assert fila["entidad_id"] == "u-2"
    assert fila["ip"] == "10.0.0.9"
    assert fila["dispositivo"] == "visor-test"
    assert fila["timestamp"] is not None


@pytest.mark.anyio
async def test_filtros_combinados_y_total_antes_de_paginar(
    api_client, acceso, session_factory
) -> None:
    admin = acceso["admin"]
    odontologo = acceso["actores"]["odontologo"]
    filas = [
        (uuid.uuid4(), admin.id, "usuario.crear", "usuario", "a", _momento(9)),
        (uuid.uuid4(), admin.id, "usuario.crear", "usuario", "b", _momento(10)),
        (uuid.uuid4(), admin.id, "usuario.crear", "usuario", "c", _momento(11)),
        (
            uuid.uuid4(),
            admin.id,
            "usuario.editar",
            "usuario",
            "d",
            _momento(12),
        ),
        (
            uuid.uuid4(),
            odontologo.id,
            "usuario.crear",
            "usuario",
            "e",
            _momento(13),
        ),
        (
            uuid.uuid4(),
            admin.id,
            "usuario.crear",
            "turno",
            "f",
            _momento(14),
        ),
    ]
    await insertar_auditoria(session_factory, filas)

    response = api_client.get(
        URL,
        params={
            "usuario_id": str(admin.id),
            "entidad": "usuario",
            "accion": "usuario.crear",
            "desde": "2026-11-05",
            "hasta": "2026-11-06",
            "limite": 1,
            "offset": 0,
        },
        headers=_admin_headers(acceso),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert len(body["filas"]) == 1
    assert body["filas"][0]["entidad_id"] == "c"


@pytest.mark.anyio
async def test_paginacion_de_120_filas(
    api_client, acceso, session_factory
) -> None:
    admin = acceso["admin"]
    base = _momento(0, 5)
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                admin.id,
                "usuario.crear",
                "usuario",
                str(indice),
                base + timedelta(minutes=indice),
            )
            for indice in range(120)
        ],
    )

    response = api_client.get(
        URL,
        params={"limite": 50, "offset": 100},
        headers=_admin_headers(acceso),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 120
    assert body["limite"] == 50
    assert body["offset"] == 100
    assert len(body["filas"]) == 20


@pytest.mark.anyio
async def test_tabla_vacia(api_client, acceso) -> None:
    response = api_client.get(URL, headers=_admin_headers(acceso))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total": 0,
        "limite": 100,
        "offset": 0,
        "filas": [],
    }


@pytest.mark.anyio
async def test_lectura_no_agrega_filas(
    api_client, acceso, session_factory
) -> None:
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                acceso["admin"].id,
                "usuario.crear",
                "usuario",
                "u-1",
                _momento(),
            )
        ],
    )
    antes = await contar_auditoria(session_factory)
    for _ in range(2):
        assert (
            api_client.get(URL, headers=_admin_headers(acceso)).status_code
            == 200
        )
    assert await contar_auditoria(session_factory) == antes


@pytest.mark.anyio
async def test_usuario_dado_de_baja_sigue_trazado(
    api_client, acceso, session_factory
) -> None:
    odontologo = acceso["actores"]["odontologo"]
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                odontologo.id,
                "usuario.roles",
                "usuario",
                "u-9",
                _momento(),
            )
        ],
    )
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE usuarios SET is_active = false, deleted_at = now() "
                "WHERE id = :id"
            ),
            {"id": odontologo.id},
        )

    response = api_client.get(URL, headers=_admin_headers(acceso))
    assert response.status_code == 200, response.text
    filas = response.json()["filas"]
    assert len(filas) == 1
    assert filas[0]["usuario_id"] == str(odontologo.id)
    assert filas[0]["usuario_email"] == odontologo.email


@pytest.mark.anyio
async def test_bordes_de_fecha_inclusivos(
    api_client, acceso, session_factory
) -> None:
    inicio_dia = datetime(2026, 11, 5, 0, 0, 0, tzinfo=ARGENTINA_OFFSET)
    fin_dia = datetime(
        2026, 11, 5, 23, 59, 59, 999999, tzinfo=ARGENTINA_OFFSET
    )
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                acceso["admin"].id,
                "usuario.crear",
                "usuario",
                "inicio",
                inicio_dia,
            ),
            (
                uuid.uuid4(),
                acceso["admin"].id,
                "usuario.editar",
                "usuario",
                "fin",
                fin_dia,
            ),
        ],
    )

    response = api_client.get(
        URL,
        params={"desde": "2026-11-05", "hasta": "2026-11-05"},
        headers=_admin_headers(acceso),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert {fila["entidad_id"] for fila in body["filas"]} == {
        "inicio",
        "fin",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "params",
    [
        {"limite": 0},
        {"limite": 501},
        {"offset": -1},
        {"desde": "2026-11-06", "hasta": "2026-11-05"},
        {"filtro_no_declarado": "x"},
        {"usuario_id": "no-es-un-uuid"},
        {"desde": "06-11-2026"},
    ],
)
async def test_parametros_invalidos_422(
    api_client, acceso, params: dict
) -> None:
    response = api_client.get(
        URL, params=params, headers=_admin_headers(acceso)
    )
    assert response.status_code == 422, (params, response.text)


@pytest.mark.anyio
@pytest.mark.parametrize("metodo", ["post", "put", "patch", "delete"])
async def test_metodos_de_escritura_405(
    api_client, acceso, session_factory, metodo: str
) -> None:
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                acceso["admin"].id,
                "usuario.crear",
                "usuario",
                "u-1",
                _momento(),
            )
        ],
    )
    llamada = getattr(api_client, metodo)
    kwargs: dict[str, object] = {"headers": _admin_headers(acceso)}
    if metodo != "delete":
        kwargs["json"] = {"accion": "alterada"}
    response = llamada(URL, **kwargs)
    assert response.status_code == 405, response.text
    assert await contar_auditoria(session_factory) == 1
