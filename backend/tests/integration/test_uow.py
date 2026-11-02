"""Unit of work: one transaction per use case, no leaks."""

import pytest
from sqlalchemy import func, select, text

from app.infrastructure.uow import UnitOfWork
from app.models import Consultorio, Usuario
from tests.integration.helpers import run


def _usuario(email: str) -> Usuario:
    return Usuario(
        nombre="Ana Pérez",
        email=email,
        hash_password="$2b$12$fakeparahashparatest0000000000000000000000000000000000",
    )


def test_commit_conjunto_publica_todas_las_escrituras(session_factory) -> None:
    """Expected: consultorio + usuario are published together."""

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            await uow.consultorios.add(
                Consultorio(nombre="Demo", slug="demo")
            )
            await uow.usuarios.add(_usuario("juntos@clinica.test"))

        async with session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(Usuario))
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(Consultorio)
                )
                == 1
            )

    run(scenario())


def test_excepcion_revierte_todo(session_factory) -> None:
    """Business error: any failure inside the block leaves zero rows."""

    async def scenario() -> None:
        with pytest.raises(RuntimeError):
            async with UnitOfWork(session_factory) as uow:
                await uow.usuarios.add(_usuario("revierte@clinica.test"))
                raise RuntimeError("falla de negocio")

        async with session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(Usuario))
                == 0
            )

    run(scenario())


def test_sesion_utilizable_tras_rollback(session_factory) -> None:
    """Edge: a later unit of work is unaffected by a previous rollback."""

    async def scenario() -> None:
        with pytest.raises(RuntimeError):
            async with UnitOfWork(session_factory) as uow:
                await uow.usuarios.add(_usuario("falla@clinica.test"))
                raise RuntimeError("falla")

        async with UnitOfWork(session_factory) as uow:
            await uow.usuarios.add(_usuario("despues@clinica.test"))

        async with session_factory() as session:
            emails = list(
                await session.scalars(select(Usuario.email).order_by(Usuario.email))
            )
            assert emails == ["despues@clinica.test"]

    run(scenario())


def test_no_deja_transacciones_abiertas(session_factory) -> None:
    """Edge: closing the unit of work never leaves 'idle in transaction'."""

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            await uow.usuarios.add(_usuario("limpia@clinica.test"))

        async with session_factory() as session:
            abiertas = await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND state = 'idle in transaction'"
                )
            )
            assert abiertas == 0

    run(scenario())


def test_acceso_a_sesion_fuera_de_contexto_falla(session_factory) -> None:
    """Edge: using the unit of work without entering fails loudly."""

    uow = UnitOfWork(session_factory)
    with pytest.raises(RuntimeError):
        _ = uow.session
