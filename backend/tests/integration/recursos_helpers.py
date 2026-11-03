"""Builders for agenda integration tests (fictional data only)."""

import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_settings
from app.core.security import create_access_token, get_password_hash
from app.models import (
    Consultorio,
    Profesional,
    Rol,
    Sillon,
    Usuario,
    UsuarioRol,
)
from app.seed import CONSULTORIO_DEMO_SLUG, run_seed

EMAIL_POR_ROL = {
    "administrador": "admin.agenda@clinica.test",
    "odontologo": "odonto.agenda@clinica.test",
    "recepcionista": "recep.agenda@clinica.test",
    "asistente": "asistente.agenda@clinica.test",
    "auditor": "auditor.agenda@clinica.test",
}


async def seed_demo(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session, session.begin():
        await run_seed(session, "demo-secret-123")


async def consultorio_demo_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    async with session_factory() as session:
        consultorio_id = await session.scalar(
            select(Consultorio.id).where(
                Consultorio.slug == CONSULTORIO_DEMO_SLUG,
                Consultorio.deleted_at.is_(None),
            )
        )
    assert consultorio_id is not None
    return consultorio_id


async def create_actor(
    session_factory: async_sessionmaker[AsyncSession],
    rol: str,
    email: str | None = None,
) -> Usuario:
    """Create (or reuse) a user with exactly one active role."""
    email = email or EMAIL_POR_ROL[rol]
    async with session_factory() as session, session.begin():
        rol_model = await session.scalar(select(Rol).where(Rol.nombre == rol))
        if rol_model is None:
            rol_model = Rol(id=uuid.uuid4(), nombre=rol)
            session.add(rol_model)
            await session.flush()

        usuario = await session.scalar(
            select(Usuario).where(Usuario.email == email)
        )
        if usuario is None:
            usuario = Usuario(
                id=uuid.uuid4(),
                nombre=f"Actor {rol}",
                email=email,
                hash_password=get_password_hash("demo-pass"),
            )
            session.add(usuario)
            await session.flush()
            session.add(
                UsuarioRol(usuario_id=usuario.id, rol_id=rol_model.id)
            )
    return usuario


async def create_profesional(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    matricula: str,
    usuario_id: uuid.UUID | None = None,
    duracion_base_min: int = 60,
    dias_atencion: tuple[int, ...] = (0, 1, 2, 3, 4),
    hora_desde: time = time(9, 0),
    hora_hasta: time = time(12, 0),
) -> Profesional:
    async with session_factory() as session, session.begin():
        profesional = Profesional(
            id=uuid.uuid4(),
            consultorio_id=consultorio_id,
            usuario_id=usuario_id,
            matricula=matricula,
            especialidades=["general"],
            duracion_base_min=duracion_base_min,
            dias_atencion=list(dias_atencion),
            hora_desde=hora_desde,
            hora_hasta=hora_hasta,
        )
        session.add(profesional)
    return profesional


async def create_sillon(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    nombre: str,
) -> Sillon:
    async with session_factory() as session, session.begin():
        sillon = Sillon(
            id=uuid.uuid4(), consultorio_id=consultorio_id, nombre=nombre
        )
        session.add(sillon)
    return sillon


def make_token(usuario: Usuario) -> str:
    settings = get_settings()
    return create_access_token(
        subject=str(usuario.id),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=30,
    )


def bearer(usuario: Usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(usuario)}"}
