"""Audit trail of accepted access mutations (C-16, task 3.7).

Exactly one row per accepted create/edit/roles/password/activate/deactivate,
no row for a rejected (409/422) or no-op request, actor/entity/IP/device
columns filled, and never a password or hash. The table stays append-only.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_uow
from app.infrastructure.uow import UnitOfWork
from app.main import app
from tests.integration.acceso_helpers import (
    bearer_de,
    filas_auditoria,
    setup_acceso,
)
from tests.integration.helpers import sqlstate

PASSWORD = "clave-larga-123"
OTRA_PASSWORD = "otra-clave-456"
DISPOSITIVO = "pytest-device-c16"


@pytest.fixture
def test_client(
    migrated_database: str, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[TestClient]:
    async def override_get_uow() -> AsyncIterator[UnitOfWork]:
        uow = UnitOfWork(session_factory)
        async with uow:
            yield uow

    app.dependency_overrides[get_uow] = override_get_uow
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def acceso(session_factory: async_sessionmaker[AsyncSession]) -> dict:
    return await setup_acceso(session_factory)


def _headers(acceso: dict) -> dict[str, str]:
    return {
        **bearer_de(acceso["admin"].id),
        "User-Agent": DISPOSITIVO,
    }


def _crear(
    client: TestClient,
    headers: dict[str, str],
    email: str = "auditado@clinica.test",
) -> dict:
    response = client.post(
        "/usuarios",
        json={
            "nombre": "Auditado",
            "email": email,
            "password": PASSWORD,
            "roles": ["odontologo"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_una_fila_por_mutacion_aceptada(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _headers(acceso)
    creado = _crear(test_client, headers)

    assert (
        test_client.put(
            f"/usuarios/{creado['id']}/roles",
            json={"roles": ["odontologo", "asistente"]},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        test_client.post(
            f"/usuarios/{creado['id']}/password",
            json={"password": OTRA_PASSWORD},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        test_client.patch(
            f"/usuarios/{creado['id']}",
            json={"nombre": "Auditado Editado"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        test_client.patch(
            f"/usuarios/{creado['id']}",
            json={"activo": False},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        test_client.patch(
            f"/usuarios/{creado['id']}",
            json={"activo": True},
            headers=headers,
        ).status_code
        == 200
    )

    filas = await filas_auditoria(session_factory, solo_usuario=True)
    assert [fila.accion for fila in filas] == [
        "usuario.crear",
        "usuario.roles",
        "usuario.password",
        "usuario.editar",
        "usuario.desactivar",
        "usuario.activar",
    ]
    for fila in filas:
        assert fila.usuario_id == acceso["admin"].id
        assert fila.entidad == "usuario"
        assert fila.entidad_id == creado["id"]
        assert fila.ip == "testclient"
        assert fila.dispositivo == DISPOSITIVO
        assert fila.timestamp is not None


@pytest.mark.anyio
async def test_rechazos_y_validaciones_no_dejan_filas(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _headers(acceso)
    creado = _crear(test_client, headers, email="rechazos@clinica.test")
    antes = len(await filas_auditoria(session_factory, solo_usuario=True))

    duplicado = test_client.post(
        "/usuarios",
        json={
            "nombre": "Duplicado",
            "email": "RECHAZOS@CLINICA.TEST",
            "password": PASSWORD,
            "roles": ["odontologo"],
        },
        headers=headers,
    )
    assert duplicado.status_code == 409

    ultimo_admin = test_client.put(
        f"/usuarios/{acceso['admin'].id}/roles",
        json={"roles": ["odontologo"]},
        headers=headers,
    )
    assert ultimo_admin.status_code == 409

    assert (
        test_client.post(
            f"/usuarios/{creado['id']}/password",
            json={"password": "corta"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        test_client.put(
            f"/usuarios/{creado['id']}/roles",
            json={"roles": ["superadmin"]},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        test_client.patch(
            f"/usuarios/{creado['id']}",
            json={"email": "sin-arroba"},
            headers=headers,
        ).status_code
        == 422
    )

    despues = len(await filas_auditoria(session_factory, solo_usuario=True))
    assert despues == antes


@pytest.mark.anyio
async def test_sin_cambios_no_agrega_fila(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _headers(acceso)
    creado = _crear(test_client, headers, email="noop@clinica.test")
    antes = len(await filas_auditoria(session_factory, solo_usuario=True))

    mismo_nombre = test_client.patch(
        f"/usuarios/{creado['id']}",
        json={"nombre": "Auditado"},
        headers=headers,
    )
    assert mismo_nombre.status_code == 200

    mismos_roles = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": ["odontologo"]},
        headers=headers,
    )
    assert mismos_roles.status_code == 200

    despues = len(await filas_auditoria(session_factory, solo_usuario=True))
    assert despues == antes


@pytest.mark.anyio
async def test_la_auditoria_no_guarda_password_ni_hash(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _headers(acceso)
    creado = _crear(test_client, headers, email="secretos@clinica.test")
    assert (
        test_client.post(
            f"/usuarios/{creado['id']}/password",
            json={"password": OTRA_PASSWORD},
            headers=headers,
        ).status_code
        == 200
    )

    async with session_factory() as session:
        hash_guardado = await session.scalar(
            text("SELECT hash_password FROM usuarios WHERE id = :id"),
            {"id": creado["id"]},
        )
        filas = (
            await session.execute(
                text(
                    "SELECT accion, entidad, entidad_id, ip, dispositivo "
                    "FROM registro_auditoria WHERE accion LIKE 'usuario.%'"
                )
            )
        ).all()
    assert hash_guardado is not None
    texto = " ".join(" ".join(str(valor) for valor in fila) for fila in filas)
    assert PASSWORD not in texto
    assert OTRA_PASSWORD not in texto
    assert hash_guardado not in texto
    assert "$2b$" not in texto

    async with session_factory() as session:
        columnas = set(
            await session.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'registro_auditoria'"
                )
            )
        )
    assert "password" not in columnas
    assert "hash_password" not in columnas


@pytest.mark.anyio
async def test_auditoria_sigue_append_only(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _headers(acceso)
    _crear(test_client, headers, email="append@clinica.test")
    filas = await filas_auditoria(session_factory, solo_usuario=True)
    assert len(filas) == 1
    registro_id = filas[0].id

    for statement in (
        "UPDATE registro_auditoria SET accion = 'alterado' WHERE id = :id",
        "DELETE FROM registro_auditoria WHERE id = :id",
    ):
        with pytest.raises(DBAPIError) as excinfo:
            async with session_factory() as session, session.begin():
                await session.execute(text(statement), {"id": registro_id})
        assert sqlstate(excinfo.value) == "P0001"

    assert (
        len(await filas_auditoria(session_factory, solo_usuario=True)) == 1
    )
