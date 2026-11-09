"""Last-active-administrator invariant (C-16, task 3.5).

Sequential cases: removing the role from the last administrator, deactivating
the last one, two-admin operations, self-deactivation and self-removal.

Concurrency: two transactions deactivate the two last administrators at the
same time under `pg_advisory_xact_lock`; exactly one commits (200) and the
other rolls back (409), leaving one active administrator. A test-only barrier
gates the lock acquisition so both requests have already authenticated, which
makes the race deterministic instead of dependent on scheduler luck.
"""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_uow
from app.infrastructure.uow import UnitOfWork
from app.main import app
from tests.integration.acceso_helpers import (
    add_second_admin,
    bearer_de,
    contar_admin_activos,
    setup_acceso,
)

PASSWORD = "clave-larga-123"


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


def _crear(client: TestClient, headers: dict[str, str], email: str) -> dict:
    response = client.post(
        "/usuarios",
        json={
            "nombre": "Admin Dos",
            "email": email,
            "password": PASSWORD,
            "roles": ["administrador"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_quitar_el_rol_al_ultimo_admin_409(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    admin = acceso["admin"]
    headers = bearer_de(admin.id)
    assert await contar_admin_activos(session_factory) == 1

    response = test_client.put(
        f"/usuarios/{admin.id}/roles",
        json={"roles": ["odontologo"]},
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "administrador" in response.json()["detail"].lower()

    detalle = test_client.get(f"/usuarios/{admin.id}", headers=headers)
    assert detalle.json()["roles"] == ["administrador"]
    assert await contar_admin_activos(session_factory) == 1


@pytest.mark.anyio
async def test_desactivar_al_ultimo_admin_409(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    admin = acceso["admin"]
    headers = bearer_de(admin.id)

    response = test_client.patch(
        f"/usuarios/{admin.id}",
        json={"activo": False},
        headers=headers,
    )
    assert response.status_code == 409, response.text
    assert "administrador" in response.json()["detail"].lower()

    detalle = test_client.get(f"/usuarios/{admin.id}", headers=headers)
    assert detalle.json()["is_active"] is True
    assert detalle.json()["roles"] == ["administrador"]
    assert await contar_admin_activos(session_factory) == 1


@pytest.mark.anyio
async def test_con_dos_admins_se_puede_desactivar_uno(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    admin = acceso["admin"]
    headers = bearer_de(admin.id)
    segundo = _crear(test_client, headers, "admin.dos.desactivar@clinica.test")
    assert await contar_admin_activos(session_factory) == 2

    response = test_client.patch(
        f"/usuarios/{segundo['id']}",
        json={"activo": False},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False
    assert await contar_admin_activos(session_factory) == 1
    # The deactivated administrator can no longer authenticate.
    assert (
        test_client.get(
            "/usuarios", headers=bearer_de(segundo["id"])
        ).status_code
        == 401
    )


@pytest.mark.anyio
async def test_auto_desactivacion_es_409_aun_con_otro_admin(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    admin = acceso["admin"]
    headers = bearer_de(admin.id)
    _crear(test_client, headers, "admin.dos.auto@clinica.test")

    response = test_client.patch(
        f"/usuarios/{admin.id}",
        json={"activo": False},
        headers=headers,
    )
    assert response.status_code == 409
    assert "propia cuenta" in response.json()["detail"].lower()
    assert (
        test_client.get(f"/usuarios/{admin.id}", headers=headers)
        .json()["is_active"]
        is True
    )
    assert await contar_admin_activos(session_factory) == 2


@pytest.mark.anyio
async def test_auto_remocion_con_otro_admin_200_y_pierde_acceso(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    admin = acceso["admin"]
    headers = bearer_de(admin.id)
    _crear(test_client, headers, "admin.dos.remocion@clinica.test")

    response = test_client.put(
        f"/usuarios/{admin.id}/roles",
        json={"roles": ["odontologo"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["odontologo"]

    # The token is still valid, but authorization is re-read from PostgreSQL.
    assert test_client.get("/usuarios", headers=headers).status_code == 403
    assert await contar_admin_activos(session_factory) == 1


@pytest.mark.anyio
async def test_auto_remocion_como_ultimo_admin_409(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    admin = acceso["admin"]
    headers = bearer_de(admin.id)

    response = test_client.put(
        f"/usuarios/{admin.id}/roles",
        json={"roles": ["asistente", "odontologo"]},
        headers=headers,
    )
    assert response.status_code == 409
    assert (
        test_client.get(f"/usuarios/{admin.id}", headers=headers)
        .json()["roles"]
        == ["administrador"]
    )
    assert await contar_admin_activos(session_factory) == 1


@pytest.mark.anyio
async def test_desactivaciones_concurrentes_una_gana_y_otra_409(
    migrated_database: str,
    session_factory: async_sessionmaker[AsyncSession],
    acceso: dict,
) -> None:
    admin = acceso["admin"]
    segundo = await add_second_admin(session_factory)
    assert await contar_admin_activos(session_factory) == 2

    barrera = asyncio.Barrier(2)

    class BarrierUnitOfWork(UnitOfWork):
        """Gate lock acquisition so both requests have authenticated first."""

        async def __aenter__(self) -> UnitOfWork:
            uow = await super().__aenter__()
            original = uow.usuarios.lock_acceso

            async def lock_acceso() -> None:
                await asyncio.wait_for(barrera.wait(), timeout=10)
                await original()

            uow.usuarios.lock_acceso = lock_acceso  # type: ignore[method-assign]
            return uow

    async def override_get_uow() -> AsyncIterator[UnitOfWork]:
        uow = BarrierUnitOfWork(session_factory)
        async with uow:
            yield uow

    app.dependency_overrides[get_uow] = override_get_uow
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            respuestas = await asyncio.gather(
                client.patch(
                    f"/usuarios/{admin.id}",
                    json={"activo": False},
                    headers=bearer_de(segundo.id),
                ),
                client.patch(
                    f"/usuarios/{segundo.id}",
                    json={"activo": False},
                    headers=bearer_de(admin.id),
                ),
            )
    finally:
        app.dependency_overrides.clear()

    codigos = sorted(respuesta.status_code for respuesta in respuestas)
    assert codigos == [200, 409], [
        (respuesta.status_code, respuesta.text) for respuesta in respuestas
    ]
    assert await contar_admin_activos(session_factory) == 1
