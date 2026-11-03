"""Integration tests for POST /usuarios/login (C-03, R-02, R-03, DD-07b, RN-SE-02)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_login_limiter, get_settings, get_uow
from app.core.security import decode_access_token, get_password_hash
from app.core.throttling import LoginRateLimiter
from app.infrastructure.uow import UnitOfWork
from app.main import app
from app.models.security import RegistroAuditoria, Rol, Usuario, UsuarioRol


@pytest.fixture
def limiter() -> LoginRateLimiter:
    """Isolated limiter per test: no shared process state between cases."""
    return LoginRateLimiter(max_attempts=3, window_seconds=60)


@pytest.fixture
def test_client(
    migrated_database: str,
    session_factory: async_sessionmaker[AsyncSession],
    limiter: LoginRateLimiter,
) -> TestClient:
    async def override_get_uow() -> AsyncIterator[UnitOfWork]:
        uow = UnitOfWork(session_factory)
        async with uow:
            yield uow

    app.dependency_overrides[get_uow] = override_get_uow
    app.dependency_overrides[get_login_limiter] = lambda: limiter
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_users(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Active admin, active receptionist and a soft-deleted user."""
    password = "CorrectDemoPassword123!"
    hashed = get_password_hash(password)

    uow = UnitOfWork(session_factory)
    async with uow:
        session = uow.session
        rol_admin = Rol(id=uuid.uuid4(), nombre="administrador")
        rol_recep = Rol(id=uuid.uuid4(), nombre="recepcionista")
        session.add_all([rol_admin, rol_recep])
        await session.flush()

        user_admin = Usuario(
            id=uuid.uuid4(),
            nombre="Admin User",
            email="admin.login@clinica.local",
            hash_password=hashed,
        )
        user_recep = Usuario(
            id=uuid.uuid4(),
            nombre="Recep User",
            email="recep.login@clinica.local",
            hash_password=hashed,
        )
        user_inactive = Usuario(
            id=uuid.uuid4(),
            nombre="Inactive User",
            email="inactive.user@clinica.local",
            hash_password=hashed,
        )
        session.add_all([user_admin, user_recep, user_inactive])
        await session.flush()

        session.add_all(
            [
                UsuarioRol(usuario_id=user_admin.id, rol_id=rol_admin.id),
                UsuarioRol(usuario_id=user_recep.id, rol_id=rol_recep.id),
            ]
        )
        await uow.usuarios.soft_delete(user_inactive)

    return {
        "admin_id": user_admin.id,
        "admin_email": user_admin.email,
        "recep_email": user_recep.email,
        "inactive_id": user_inactive.id,
        "inactive_email": user_inactive.email,
        "password": password,
    }


async def _audit_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[RegistroAuditoria]:
    async with session_factory() as session:
        result = await session.scalars(
            select(RegistroAuditoria).order_by(RegistroAuditoria.timestamp)
        )
        return list(result)


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/usuarios/login", json={"email": email, "password": password}
    )


@pytest.mark.anyio
async def test_login_exitoso_emite_token_y_audita(
    test_client: TestClient,
    seeded_users: dict[str, object],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = _login(
        test_client,
        str(seeded_users["admin_email"]),
        str(seeded_users["password"]),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["expires_in"], int)
    assert data["usuario"]["email"] == seeded_users["admin_email"]
    assert data["usuario"]["roles"] == ["administrador"]

    payload = decode_access_token(
        token=data["access_token"],
        secret=get_settings().jwt_secret,
        algorithms=[get_settings().jwt_algorithm],
    )
    assert payload["sub"] == str(seeded_users["admin_id"])
    assert "roles" not in payload and "email" not in payload

    rows = await _audit_rows(session_factory)
    assert [row.accion for row in rows] == ["login_exitoso"]
    assert rows[0].usuario_id == seeded_users["admin_id"]


@pytest.mark.anyio
async def test_login_email_es_case_insensitive(
    test_client: TestClient, seeded_users: dict[str, object]
) -> None:
    response = _login(
        test_client,
        "  ADMIN.LOGIN@CLINICA.LOCAL ",
        str(seeded_users["password"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["usuario"]["email"] == seeded_users["admin_email"]


@pytest.mark.anyio
async def test_login_credenciales_invalidas_sin_enumeracion(
    test_client: TestClient,
    seeded_users: dict[str, object],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    wrong_password = _login(
        test_client,
        str(seeded_users["admin_email"]),
        "WrongPassword999!",
    )
    unknown_user = _login(
        test_client, "does.not.exist@clinica.local", "AnyPassword123!"
    )

    # Same status and same body: the response does not reveal whether the
    # email is registered.
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()

    rows = await _audit_rows(session_factory)
    assert [row.accion for row in rows] == ["login_fallido", "login_fallido"]
    assert rows[0].usuario_id == seeded_users["admin_id"]
    assert rows[1].usuario_id is None


@pytest.mark.anyio
async def test_login_usuario_dado_de_baja_rechazado_y_auditado(
    test_client: TestClient,
    seeded_users: dict[str, object],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = _login(
        test_client,
        str(seeded_users["inactive_email"]),
        str(seeded_users["password"]),
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas"

    rows = await _audit_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].accion == "login_fallido"
    assert rows[0].usuario_id == seeded_users["inactive_id"]


@pytest.mark.anyio
async def test_login_extra_fields_rejected_by_roro(
    test_client: TestClient,
) -> None:
    response = test_client.post(
        "/usuarios/login",
        json={
            "email": "admin@clinica.local",
            "password": "pass",
            "campo_no_declarado": "hack",
        },
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_login_password_vacio_rechazado_por_schema(
    test_client: TestClient,
) -> None:
    response = _login(test_client, "admin@clinica.local", "")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_login_throttling_activado_con_retry_after(
    test_client: TestClient,
    seeded_users: dict[str, object],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    for _ in range(3):
        failed = _login(
            test_client,
            str(seeded_users["admin_email"]),
            "BadPassword!",
        )
        assert failed.status_code == 401

    blocked = _login(
        test_client,
        str(seeded_users["admin_email"]),
        str(seeded_users["password"]),
    )
    assert blocked.status_code == 429
    retry_after = blocked.headers.get("Retry-After")
    assert retry_after is not None and int(retry_after) > 0
    assert "Demasiados intentos" in blocked.json()["detail"]

    # The throttled attempt is not audited (append-only table stays bounded).
    rows = await _audit_rows(session_factory)
    assert len(rows) == 3
    assert {row.accion for row in rows} == {"login_fallido"}


@pytest.mark.anyio
async def test_login_exitoso_limpia_el_throttling(
    test_client: TestClient, seeded_users: dict[str, object]
) -> None:
    _login(test_client, str(seeded_users["admin_email"]), "BadPassword!")
    _login(test_client, str(seeded_users["admin_email"]), "BadPassword!")

    ok = _login(
        test_client,
        str(seeded_users["admin_email"]),
        str(seeded_users["password"]),
    )
    assert ok.status_code == 200

    # Counter restarted: two more failures still do not block.
    for _ in range(2):
        failed = _login(
            test_client,
            str(seeded_users["admin_email"]),
            "BadPassword!",
        )
        assert failed.status_code == 401
