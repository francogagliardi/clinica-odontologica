"""Builders for the C-16 access-management tests (fictional data only).

`seed_demo` already creates the demo consultorio, the five roles and the only
administrator used by the last-admin invariant. The rest of the cast is added
on demand so a test can start with exactly one active administrator.
"""

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import load_settings
from app.core.security import create_access_token
from app.infrastructure.uow import UnitOfWork
from app.models import RegistroAuditoria, Usuario, UsuarioRol
from tests.integration.recursos_helpers import (
    EMAIL_POR_ROL,
    create_actor,
    seed_demo,
)

ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
ADMIN_EMAIL = "admin@clinica.test"
ADMIN_PASSWORD = "demo-secret-123"


async def setup_acceso(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Demo tenant, the seeded administrator and one actor per other role."""
    await seed_demo(session_factory)
    async with session_factory() as session:
        admin = await session.scalar(
            select(Usuario).where(Usuario.email == ADMIN_EMAIL)
        )
    assert admin is not None
    actores: dict[str, Usuario] = {"administrador": admin}
    for rol in ROLES[1:]:
        actores[rol] = await create_actor(session_factory, rol)
    return {"admin": admin, "actores": actores}


async def add_second_admin(
    session_factory: async_sessionmaker[AsyncSession],
    email: str = "admin.dos@clinica.test",
) -> Usuario:
    """Create another active administrator (two-admin scenarios)."""
    return await create_actor(session_factory, "administrador", email=email)


def token_de(usuario_id: uuid.UUID) -> str:
    settings = load_settings()
    return create_access_token(
        subject=str(usuario_id),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=30,
    )


def bearer_de(usuario_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_de(usuario_id)}"}


async def filas_auditoria(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    solo_usuario: bool = False,
) -> list[RegistroAuditoria]:
    async with session_factory() as session:
        statement = select(RegistroAuditoria).order_by(
            RegistroAuditoria.timestamp, RegistroAuditoria.id
        )
        if solo_usuario:
            statement = statement.where(
                RegistroAuditoria.accion.like("usuario.%")
            )
        return list(await session.scalars(statement))


async def contar_vinculos(
    session_factory: async_sessionmaker[AsyncSession],
    usuario_id: uuid.UUID,
) -> int:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(UsuarioRol)
            .where(UsuarioRol.usuario_id == usuario_id)
        )
    return int(total or 0)


async def roles_db(
    session_factory: async_sessionmaker[AsyncSession],
    usuario_id: uuid.UUID,
) -> list[str]:
    """Role names linked to a user, read straight from the link table."""
    async with session_factory() as session:
        rows = await session.execute(
            text(
                "SELECT r.nombre FROM usuario_roles ur "
                "JOIN roles r ON r.id = ur.rol_id "
                "WHERE ur.usuario_id = :usuario_id ORDER BY r.nombre"
            ),
            {"usuario_id": usuario_id},
        )
    return [nombre for (nombre,) in rows.all()]


async def contar_admin_activos(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Administrator count read through the same repository the API uses."""
    async with UnitOfWork(session_factory) as uow:
        return await uow.usuarios.contar_administradores_activos()


async def desactivar_db(
    session_factory: async_sessionmaker[AsyncSession],
    usuario_id: uuid.UUID,
) -> None:
    """Logical deactivation: the C-02 CHECK ties `is_active=false` to `deleted_at`."""
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE usuarios SET is_active = false, deleted_at = now() "
                "WHERE id = :id"
            ),
            {"id": usuario_id},
        )
