"""Integration tests for Bearer validation and RBAC on real endpoints (C-03, RN-SE-01)."""

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_settings, get_uow
from app.core.security import create_access_token, get_password_hash
from app.infrastructure.uow import UnitOfWork
from app.main import app
from app.models.security import Rol, Usuario, UsuarioRol


@pytest.fixture
def test_client(
    migrated_database: str, session_factory: async_sessionmaker[AsyncSession]
) -> TestClient:
    async def override_get_uow() -> AsyncIterator[UnitOfWork]:
        uow = UnitOfWork(session_factory)
        async with uow:
            yield uow

    app.dependency_overrides[get_uow] = override_get_uow
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_actors(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Usuario]:
    uow = UnitOfWork(session_factory)
    async with uow:
        session = uow.session
        r_admin = Rol(id=uuid.uuid4(), nombre="administrador")
        r_recep = Rol(id=uuid.uuid4(), nombre="recepcionista")
        r_odon = Rol(id=uuid.uuid4(), nombre="odontologo")
        r_asist = Rol(id=uuid.uuid4(), nombre="asistente")
        session.add_all([r_admin, r_recep, r_odon, r_asist])
        await session.flush()

        u_admin = Usuario(
            id=uuid.uuid4(),
            nombre="Admin Only",
            email="admin.rbac@clinica.local",
            hash_password=get_password_hash("pass"),
        )
        u_recep = Usuario(
            id=uuid.uuid4(),
            nombre="Recep Only",
            email="recep.rbac@clinica.local",
            hash_password=get_password_hash("pass"),
        )
        u_multi = Usuario(
            id=uuid.uuid4(),
            nombre="Multi Role",
            email="multi.rbac@clinica.local",
            hash_password=get_password_hash("pass"),
        )
        u_deleted = Usuario(
            id=uuid.uuid4(),
            nombre="Deleted Admin",
            email="deleted.rbac@clinica.local",
            hash_password=get_password_hash("pass"),
        )
        session.add_all([u_admin, u_recep, u_multi, u_deleted])
        await session.flush()

        session.add_all(
            [
                UsuarioRol(usuario_id=u_admin.id, rol_id=r_admin.id),
                UsuarioRol(usuario_id=u_recep.id, rol_id=r_recep.id),
                UsuarioRol(usuario_id=u_multi.id, rol_id=r_odon.id),
                UsuarioRol(usuario_id=u_multi.id, rol_id=r_asist.id),
                UsuarioRol(usuario_id=u_deleted.id, rol_id=r_admin.id),
            ]
        )
        await uow.usuarios.soft_delete(u_deleted)

    return {
        "admin": u_admin,
        "recep": u_recep,
        "multi": u_multi,
        "deleted": u_deleted,
    }


def _make_token(user: Usuario) -> str:
    settings = get_settings()
    return create_access_token(
        subject=str(user.id),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=30,
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_auth_header_missing_or_invalid_schema(
    test_client: TestClient,
) -> None:
    assert test_client.get("/usuarios/me").status_code == 401
    assert (
        test_client.get(
            "/usuarios/me", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        ).status_code
        == 401
    )


@pytest.mark.anyio
async def test_auth_expired_or_tampered_token(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    admin = seeded_actors["admin"]
    settings = get_settings()

    expired = create_access_token(
        subject=str(admin.id),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=-10,
    )
    assert (
        test_client.get("/usuarios/me", headers=_bearer(expired)).status_code
        == 401
    )

    valid = _make_token(admin)
    tampered = valid[:-4] + "fake"
    assert (
        test_client.get("/usuarios/me", headers=_bearer(tampered)).status_code
        == 401
    )


@pytest.mark.anyio
async def test_token_con_tipo_incorrecto_es_rechazado_en_http(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    admin = seeded_actors["admin"]
    settings = get_settings()
    now = int(datetime.now(timezone.utc).timestamp())

    wrong_type = jwt.encode(
        {
            "sub": str(admin.id),
            "typ": "refresh",
            "iat": now,
            "exp": now + 60,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = test_client.get("/usuarios/me", headers=_bearer(wrong_type))
    assert response.status_code == 401


@pytest.mark.anyio
async def test_usuario_autenticado_lee_su_identidad(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    admin = seeded_actors["admin"]
    response = test_client.get("/usuarios/me", headers=_bearer(_make_token(admin)))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(admin.id)
    assert body["email"] == admin.email
    assert body["roles"] == ["administrador"]


@pytest.mark.anyio
async def test_rbac_rol_insuficiente_devuelve_403(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    recep = seeded_actors["recep"]
    response = test_client.get("/usuarios", headers=_bearer(_make_token(recep)))
    assert response.status_code == 403
    assert response.json()["detail"] == "Permisos insuficientes"


@pytest.mark.anyio
async def test_rbac_admin_lista_solo_usuarios_activos(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    admin = seeded_actors["admin"]
    response = test_client.get("/usuarios", headers=_bearer(_make_token(admin)))
    assert response.status_code == 200, response.text
    emails = {user["email"] for user in response.json()}
    assert admin.email in emails
    assert seeded_actors["recep"].email in emails
    # Soft-deleted users are hidden by the repository.
    assert seeded_actors["deleted"].email not in emails


@pytest.mark.anyio
async def test_rbac_multi_rol_solo_me(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    multi = seeded_actors["multi"]
    token = _make_token(multi)

    assert test_client.get("/usuarios/me", headers=_bearer(token)).status_code == 200
    assert test_client.get("/usuarios", headers=_bearer(token)).status_code == 403


@pytest.mark.anyio
async def test_usuario_dado_de_baja_no_autentica(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    deleted = seeded_actors["deleted"]
    response = test_client.get(
        "/usuarios/me", headers=_bearer(_make_token(deleted))
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_rol_revocado_en_caliente_invalida_el_token(
    test_client: TestClient,
    seeded_actors: dict[str, Usuario],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = seeded_actors["admin"]
    token = _make_token(admin)
    assert test_client.get("/usuarios", headers=_bearer(token)).status_code == 200

    # Revoke the administrator role after the token was issued.
    async with session_factory() as session:
        rol_admin_id = await session.scalar(
            select(Rol.id).where(Rol.nombre == "administrador")
        )
        await session.execute(
            delete(UsuarioRol).where(
                UsuarioRol.usuario_id == admin.id,
                UsuarioRol.rol_id == rol_admin_id,
            )
        )
        await session.commit()

    # Same unexpired token, but authorization is resolved from PostgreSQL.
    assert test_client.get("/usuarios", headers=_bearer(token)).status_code == 403


@pytest.mark.anyio
async def test_roles_dentro_del_token_no_autorizan(
    test_client: TestClient, seeded_actors: dict[str, Usuario]
) -> None:
    recep = seeded_actors["recep"]
    settings = get_settings()
    now = int(datetime.now(timezone.utc).timestamp())

    # Forged token that claims "administrador" in its own roles claim.
    forged = jwt.encode(
        {
            "sub": str(recep.id),
            "typ": "access",
            "roles": ["administrador"],
            "iat": now,
            "exp": now + 60,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = test_client.get("/usuarios", headers=_bearer(forged))
    assert response.status_code == 403
