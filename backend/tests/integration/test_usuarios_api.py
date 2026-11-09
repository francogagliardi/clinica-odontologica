"""`/usuarios` access-management API on real PostgreSQL (C-16, task 3.1).

Covers alta (201, normalized email, no hash), list with active/inactive
accounts, detail, partial PATCH, duplicate email 409, 422 validation, 404,
403 by role, 401 without token, password rotation, deactivation/reactivation
and the fact that `GET /usuarios/me` keeps its own route.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_uow
from app.infrastructure.uow import UnitOfWork
from app.main import app
from tests.integration.acceso_helpers import bearer_de, setup_acceso

PASSWORD = "clave-larga-123"
OTRA_PASSWORD = "otra-clave-456"


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


def _admin_headers(acceso: dict) -> dict[str, str]:
    return bearer_de(acceso["admin"].id)


def _crear(
    client: TestClient,
    headers: dict[str, str],
    *,
    email: str = "nueva.persona@clinica.test",
    nombre: str = "Nueva Persona",
    password: str = PASSWORD,
    roles: list[str] | None = None,
    extra: dict[str, object] | None = None,
):
    body: dict[str, object] = {
        "nombre": nombre,
        "email": email,
        "password": password,
        "roles": roles if roles is not None else ["odontologo"],
    }
    if extra is not None:
        body.update(extra)
    return client.post("/usuarios", json=body, headers=headers)


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/usuarios/login", json={"email": email, "password": password}
    )


@pytest.mark.anyio
async def test_alta_201_email_normalizado_sin_hash(
    test_client: TestClient, acceso: dict
) -> None:
    response = _crear(
        test_client,
        _admin_headers(acceso),
        email="  Nueva.Persona@Clinica.TEST ",
        roles=["odontologo", "asistente"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "nueva.persona@clinica.test"
    assert body["roles"] == ["asistente", "odontologo"]
    assert body["is_active"] is True
    assert "hash_password" not in response.text
    assert PASSWORD not in response.text

    login = _login(
        test_client, "nueva.persona@clinica.test", PASSWORD
    )
    assert login.status_code == 200, login.text
    assert login.json()["usuario"]["roles"] == ["asistente", "odontologo"]


@pytest.mark.anyio
async def test_listado_activos_e_inactivos_sin_hashes(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    creado = _crear(test_client, headers, email="activo@clinica.test").json()
    inactivo = _crear(
        test_client, headers, email="inactivo@clinica.test"
    ).json()

    desactivado = test_client.patch(
        f"/usuarios/{inactivo['id']}",
        json={"activo": False},
        headers=headers,
    )
    assert desactivado.status_code == 200, desactivado.text

    activos = test_client.get("/usuarios", headers=headers)
    assert activos.status_code == 200, activos.text
    emails = {usuario["email"] for usuario in activos.json()}
    assert creado["email"] in emails
    assert inactivo["email"] not in emails
    assert "hash_password" not in activos.text

    todos = test_client.get(
        "/usuarios?incluir_inactivos=true", headers=headers
    )
    assert todos.status_code == 200, todos.text
    por_email = {usuario["email"]: usuario for usuario in todos.json()}
    assert por_email[inactivo["email"]]["is_active"] is False
    assert por_email[creado["email"]]["is_active"] is True
    assert "hash_password" not in todos.text

    # Undeclared query parameters are rejected at the strict boundary.
    assert (
        test_client.get(
            "/usuarios?activo=false", headers=headers
        ).status_code
        == 422
    )


@pytest.mark.anyio
async def test_detalle_y_edicion_parcial(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    creado = _crear(
        test_client, headers, email="editar@clinica.test", nombre="Nombre Original"
    ).json()

    detalle = test_client.get(f"/usuarios/{creado['id']}", headers=headers)
    assert detalle.status_code == 200
    assert detalle.json()["email"] == "editar@clinica.test"

    solo_nombre = test_client.patch(
        f"/usuarios/{creado['id']}",
        json={"nombre": "Nombre Nuevo"},
        headers=headers,
    )
    assert solo_nombre.status_code == 200, solo_nombre.text
    body = solo_nombre.json()
    assert body["nombre"] == "Nombre Nuevo"
    assert body["email"] == "editar@clinica.test"
    assert body["roles"] == ["odontologo"]

    solo_email = test_client.patch(
        f"/usuarios/{creado['id']}",
        json={"email": "  Nuevo.Email@Clinica.TEST  "},
        headers=headers,
    )
    assert solo_email.status_code == 200
    assert solo_email.json()["email"] == "nuevo.email@clinica.test"

    # An empty PATCH is a no-op and keeps every field.
    vacio = test_client.patch(
        f"/usuarios/{creado['id']}", json={}, headers=headers
    )
    assert vacio.status_code == 200
    assert vacio.json()["nombre"] == "Nombre Nuevo"
    assert vacio.json()["email"] == "nuevo.email@clinica.test"


@pytest.mark.anyio
async def test_email_duplicado_409_sin_modificar(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    existente = _crear(
        test_client, headers, email="duplicado@clinica.test"
    ).json()
    otro = _crear(test_client, headers, email="otro@clinica.test").json()

    duplicado = _crear(
        test_client,
        headers,
        email="  DUPLICADO@CLINICA.TEST ",
        nombre="Choca",
    )
    assert duplicado.status_code == 409, duplicado.text

    colision = test_client.patch(
        f"/usuarios/{otro['id']}",
        json={"email": "Duplicado@Clinica.Test"},
        headers=headers,
    )
    assert colision.status_code == 409, colision.text
    actual = test_client.get(f"/usuarios/{otro['id']}", headers=headers)
    assert actual.json()["email"] == "otro@clinica.test"
    assert existente["email"] == "duplicado@clinica.test"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cambio",
    [
        {"roles": ["superadmin"]},
        {"roles": []},
        {"roles": ["Administrador"]},
        {"email": "sin-arroba"},
        {"password": "corta"},
        {"campo_no_declarado": "hack"},
        {"nombre": ""},
    ],
)
async def test_datos_invalidos_422_sin_crear(
    test_client: TestClient, acceso: dict, cambio: dict
) -> None:
    headers = _admin_headers(acceso)
    antes = test_client.get(
        "/usuarios?incluir_inactivos=true", headers=headers
    ).json()

    response = _crear(
        test_client,
        headers,
        email="invalido@clinica.test",
        extra=cambio,
    )
    assert response.status_code == 422, response.text

    despues = test_client.get(
        "/usuarios?incluir_inactivos=true", headers=headers
    ).json()
    assert len(despues) == len(antes)
    assert not any(
        usuario["email"] == "invalido@clinica.test" for usuario in despues
    )


@pytest.mark.anyio
async def test_usuario_inexistente_404(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    inexistente = "00000000-0000-0000-0000-000000000000"
    assert (
        test_client.get(f"/usuarios/{inexistente}", headers=headers).status_code
        == 404
    )
    assert (
        test_client.patch(
            f"/usuarios/{inexistente}", json={"nombre": "X"}, headers=headers
        ).status_code
        == 404
    )
    assert (
        test_client.post(
            f"/usuarios/{inexistente}/password",
            json={"password": PASSWORD},
            headers=headers,
        ).status_code
        == 404
    )


@pytest.mark.anyio
async def test_sin_borrado_fisico_delete_405(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    creado = _crear(test_client, headers, email="sin-borrar@clinica.test").json()
    response = test_client.delete(f"/usuarios/{creado['id']}", headers=headers)
    assert response.status_code == 405
    assert (
        test_client.get(f"/usuarios/{creado['id']}", headers=headers).status_code
        == 200
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "rol", ["odontologo", "recepcionista", "asistente", "auditor"]
)
async def test_gestion_solo_administrador_403(
    test_client: TestClient, acceso: dict, rol: str
) -> None:
    headers = bearer_de(acceso["actores"][rol].id)
    assert test_client.get("/usuarios", headers=headers).status_code == 403
    assert (
        test_client.post(
            "/usuarios",
            json={
                "nombre": "No",
                "email": "no@clinica.test",
                "password": PASSWORD,
                "roles": ["odontologo"],
            },
            headers=headers,
        ).status_code
        == 403
    )
    # `/me` remains available to every authenticated role.
    assert test_client.get("/usuarios/me", headers=headers).status_code == 200


@pytest.mark.anyio
async def test_sin_token_401(test_client: TestClient) -> None:
    assert test_client.get("/usuarios").status_code == 401
    assert (
        test_client.post(
            "/usuarios",
            json={
                "nombre": "No",
                "email": "no@clinica.test",
                "password": PASSWORD,
                "roles": ["odontologo"],
            },
        ).status_code
        == 401
    )


@pytest.mark.anyio
async def test_me_conserva_prioridad_sobre_el_detalle(
    test_client: TestClient, acceso: dict
) -> None:
    response = test_client.get(
        "/usuarios/me", headers=_admin_headers(acceso)
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == "admin@clinica.test"


@pytest.mark.anyio
async def test_cambio_de_password_sin_hash(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    creado = _crear(
        test_client, headers, email="password@clinica.test"
    ).json()
    assert _login(test_client, "password@clinica.test", PASSWORD).status_code == 200

    response = test_client.post(
        f"/usuarios/{creado['id']}/password",
        json={"password": OTRA_PASSWORD},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert "hash_password" not in response.text
    assert OTRA_PASSWORD not in response.text

    assert (
        _login(test_client, "password@clinica.test", PASSWORD).status_code
        == 401
    )
    assert (
        _login(
            test_client, "password@clinica.test", OTRA_PASSWORD
        ).status_code
        == 200
    )

    corta = test_client.post(
        f"/usuarios/{creado['id']}/password",
        json={"password": "corta"},
        headers=headers,
    )
    assert corta.status_code == 422


@pytest.mark.anyio
async def test_desactivacion_y_reactivacion_invalida_el_token(
    test_client: TestClient, acceso: dict
) -> None:
    headers = _admin_headers(acceso)
    creado = _crear(test_client, headers, email="toggle@clinica.test").json()
    login = _login(test_client, "toggle@clinica.test", PASSWORD)
    assert login.status_code == 200
    token_previo = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    desactivado = test_client.patch(
        f"/usuarios/{creado['id']}",
        json={"activo": False},
        headers=headers,
    )
    assert desactivado.status_code == 200, desactivado.text
    assert desactivado.json()["is_active"] is False

    # The unexpired token stops working immediately (roles/state from PostgreSQL).
    assert test_client.get("/usuarios/me", headers=token_previo).status_code == 401
    assert (
        _login(test_client, "toggle@clinica.test", PASSWORD).status_code == 401
    )
    activos = test_client.get("/usuarios", headers=headers).json()
    assert all(usuario["email"] != "toggle@clinica.test" for usuario in activos)

    reactivado = test_client.patch(
        f"/usuarios/{creado['id']}",
        json={"activo": True},
        headers=headers,
    )
    assert reactivado.status_code == 200, reactivado.text
    assert reactivado.json()["is_active"] is True
    assert (
        _login(test_client, "toggle@clinica.test", PASSWORD).status_code == 200
    )
