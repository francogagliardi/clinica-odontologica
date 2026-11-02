"""Idempotent demo seed for C-02.

Creates the five role names, one demo consultorio and one demo administrator.
`SEED_ADMIN_PASSWORD` is required and has no default (R-08); re-running never
rewrites an existing password hash and never duplicates rows.

Usage:
    SEED_ADMIN_PASSWORD=<password> python -m app.seed
"""

import asyncio
import os
import uuid

import bcrypt
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import load_settings
from app.infrastructure.db import create_engine, create_session_factory
from app.models import Consultorio, Rol, Usuario, UsuarioRol

ROLES: tuple[str, ...] = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
CONSULTORIO_DEMO_SLUG = "demo"
CONSULTORIO_DEMO_NOMBRE = "Consultorio Demo"
ADMIN_EMAIL = "admin@clinica.test"
ADMIN_NOMBRE = "Administrador Demo"

# Partial unique indexes only cover active rows; ON CONFLICT must be told so.
_ACTIVO = text("deleted_at IS NULL")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (never store plain text, R-03)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


async def run_seed(session: AsyncSession, admin_password: str) -> None:
    """Populate the minimum demo data; safe to run many times and in parallel."""
    if not admin_password.strip():
        raise ValueError(
            "SEED_ADMIN_PASSWORD no puede estar vacía: no se genera una "
            "contraseña por defecto (R-08)."
        )

    for nombre in ROLES:
        await session.execute(
            insert(Rol)
            .values(id=uuid.uuid4(), nombre=nombre)
            .on_conflict_do_nothing(
                index_elements=["nombre"], index_where=_ACTIVO
            )
        )

    await session.execute(
        insert(Consultorio)
        .values(
            id=uuid.uuid4(),
            slug=CONSULTORIO_DEMO_SLUG,
            nombre=CONSULTORIO_DEMO_NOMBRE,
        )
        .on_conflict_do_nothing(index_elements=["slug"], index_where=_ACTIVO)
    )

    # The hash is computed for the insert attempt only: if the row already
    # exists the conflict is ignored, so a re-run never changes credentials.
    await session.execute(
        insert(Usuario)
        .values(
            id=uuid.uuid4(),
            nombre=ADMIN_NOMBRE,
            email=ADMIN_EMAIL,
            hash_password=hash_password(admin_password),
        )
        .on_conflict_do_nothing(index_elements=["email"], index_where=_ACTIVO)
    )

    admin_id = await session.scalar(
        select(Usuario.id).where(
            Usuario.email == ADMIN_EMAIL, Usuario.deleted_at.is_(None)
        )
    )
    rol_admin_id = await session.scalar(
        select(Rol.id).where(
            Rol.nombre == "administrador", Rol.deleted_at.is_(None)
        )
    )
    if admin_id is None or rol_admin_id is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "El seed no pudo resolver el administrador o su rol; "
            "revisar las restricciones de unicidad."
        )

    await session.execute(
        insert(UsuarioRol)
        .values(usuario_id=admin_id, rol_id=rol_admin_id)
        .on_conflict_do_nothing(index_elements=["usuario_id", "rol_id"])
    )


async def main() -> None:
    """CLI entrypoint: fail before touching the DB if the secret is missing."""
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if not admin_password.strip():
        raise RuntimeError(
            "Missing required environment variable(s): SEED_ADMIN_PASSWORD. "
            "El seed abortó sin crear ningún registro."
        )

    settings = load_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            async with session.begin():
                await run_seed(session, admin_password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
