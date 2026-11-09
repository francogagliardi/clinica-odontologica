"""Fixed role catalogue and assignment API (C-16, task 3.3).

`GET /roles` is read-only and administrator-only; `PUT /usuarios/{id}/roles`
replaces the set atomically, ignores duplicates and rejects unknown/empty lists
with 422. No role CRUD exists: other methods answer 405.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_uow
from app.infrastructure.uow import UnitOfWork
from app.main import app
from tests.integration.acceso_helpers import bearer_de, roles_db, setup_acceso

PASSWORD = "clave-larga-123"
ROLES = ("administrador", "odontologo", "recepcionista", "asistente", "auditor")


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


def _admin(acceso: dict) -> dict[str, str]:
    return bearer_de(acceso["admin"].id)


def _crear(client: TestClient, headers: dict[str, str], email: str) -> dict:
    response = client.post(
        "/usuarios",
        json={
            "nombre": "Roles Target",
            "email": email,
            "password": PASSWORD,
            "roles": ["odontologo"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_get_roles_devuelve_los_cinco_solo_al_admin(
    test_client: TestClient, acceso: dict
) -> None:
    response = test_client.get("/roles", headers=_admin(acceso))
    assert response.status_code == 200, response.text
    nombres = [rol["nombre"] for rol in response.json()]
    assert len(nombres) == 5
    assert set(nombres) == set(ROLES)
    assert nombres == sorted(nombres)
    assert all(rol["id"] for rol in response.json())

    for rol in ROLES[1:]:
        negado = test_client.get(
            "/roles", headers=bearer_de(acceso["actores"][rol].id)
        )
        assert negado.status_code == 403, rol
    assert test_client.get("/roles").status_code == 401
    assert (
        test_client.get("/roles?x=1", headers=_admin(acceso)).status_code
        == 422
    )


@pytest.mark.anyio
async def test_put_reemplaza_el_conjunto(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _admin(acceso)
    creado = _crear(test_client, headers, "reemplazo@clinica.test")

    primera = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": ["odontologo"]},
        headers=headers,
    )
    assert primera.status_code == 200, primera.text
    assert primera.json()["roles"] == ["odontologo"]

    segunda = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": ["odontologo", "asistente"]},
        headers=headers,
    )
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["roles"] == ["asistente", "odontologo"]
    assert await roles_db(session_factory, creado["id"]) == [
        "asistente",
        "odontologo",
    ]

    # Replacing again drops the roles that are no longer sent.
    tercera = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": ["auditor"]},
        headers=headers,
    )
    assert tercera.status_code == 200
    assert tercera.json()["roles"] == ["auditor"]


@pytest.mark.anyio
async def test_duplicados_son_idempotentes(
    test_client: TestClient, acceso: dict, session_factory
) -> None:
    headers = _admin(acceso)
    creado = _crear(test_client, headers, "duplicados@clinica.test")

    response = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": ["asistente", "asistente", "asistente"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["asistente"]
    assert await roles_db(session_factory, creado["id"]) == ["asistente"]

    # Repeating an already assigned role changes nothing and stays 200.
    repetida = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": ["asistente"]},
        headers=headers,
    )
    assert repetida.status_code == 200
    assert repetida.json()["roles"] == ["asistente"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "roles",
    [["superadmin"], ["Administrador"], ["ODONTOLOGO"], []],
)
async def test_roles_invalidos_422_conservan_los_anteriores(
    test_client: TestClient, acceso: dict, roles: list[str]
) -> None:
    headers = _admin(acceso)
    creado = _crear(test_client, headers, "invalidos@clinica.test")
    antes = test_client.get(
        f"/usuarios/{creado['id']}", headers=headers
    ).json()

    response = test_client.put(
        f"/usuarios/{creado['id']}/roles",
        json={"roles": roles},
        headers=headers,
    )
    assert response.status_code == 422, response.text

    despues = test_client.get(
        f"/usuarios/{creado['id']}", headers=headers
    ).json()
    assert despues["roles"] == antes["roles"] == ["odontologo"]


@pytest.mark.anyio
async def test_put_roles_cuerpo_invalido_422(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin(acceso)
    creado = _crear(test_client, headers, "cuerpo@clinica.test")
    assert (
        test_client.put(
            f"/usuarios/{creado['id']}/roles",
            json={"roles": ["odontologo"], "extra": True},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        test_client.put(
            f"/usuarios/{creado['id']}/roles",
            json={"roles": "odontologo"},
            headers=headers,
        ).status_code
        == 422
    )


@pytest.mark.anyio
async def test_put_roles_permisos_y_404(
    test_client: TestClient, acceso: dict
) -> None:
    inexistente = "00000000-0000-0000-0000-000000000000"
    assert (
        test_client.put(
            f"/usuarios/{inexistente}/roles",
            json={"roles": ["auditor"]},
            headers=_admin(acceso),
        ).status_code
        == 404
    )
    for rol in ROLES[1:]:
        assert (
            test_client.put(
                f"/usuarios/{acceso['admin'].id}/roles",
                json={"roles": ["auditor"]},
                headers=bearer_de(acceso["actores"][rol].id),
            ).status_code
            == 403
        )
    assert (
        test_client.put(
            f"/usuarios/{acceso['admin'].id}/roles",
            json={"roles": ["auditor"]},
        ).status_code
        == 401
    )


@pytest.mark.anyio
@pytest.mark.parametrize("metodo", ["post", "patch", "delete"])
async def test_roles_no_se_pueden_modificar_405(
    test_client: TestClient, acceso: dict, metodo: str
) -> None:
    headers = _admin(acceso)
    llamada = getattr(test_client, metodo)
    kwargs: dict[str, object] = {"headers": headers}
    if metodo != "delete":
        kwargs["json"] = {"nombre": "superadmin"}
    response = llamada("/roles", **kwargs)
    assert response.status_code == 405
    catalogo = test_client.get("/roles", headers=headers).json()
    assert len(catalogo) == 5
