"""Demo seed: required secret, idempotency, concurrency, no credential rewrite."""

import asyncio

import bcrypt
import pytest
from sqlalchemy import func, select

from app.models import Consultorio, Rol, Usuario, UsuarioRol
from app.seed import ADMIN_EMAIL, ROLES, main, run_seed
from tests.integration.helpers import run


async def _seed(session_factory, password: str) -> None:
    async with session_factory() as session, session.begin():
        await run_seed(session, password)


async def _count(session_factory, model) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


def test_seed_crea_roles_consultorio_y_admin(session_factory) -> None:
    """Expected: the demo dataset exists and the admin password is hashed."""

    async def scenario() -> None:
        await _seed(session_factory, "demo-secret-123")

        async with session_factory() as session:
            roles = set(await session.scalars(select(Rol.nombre)))
            assert roles == set(ROLES)
            assert await session.scalar(
                select(func.count()).select_from(Consultorio)
            ) == 1

            admin = await session.scalar(
                select(Usuario).where(Usuario.email == ADMIN_EMAIL)
            )
            assert admin is not None
            assert admin.hash_password != "demo-secret-123"
            assert bcrypt.checkpw(
                b"demo-secret-123", admin.hash_password.encode()
            )

            links = await session.scalar(
                select(func.count())
                .select_from(UsuarioRol)
                .where(UsuarioRol.usuario_id == admin.id)
            )
            assert links == 1

    run(scenario())


def test_seed_sin_password_aborta_sin_escribir(session_factory) -> None:
    """Business error: no default password exists; nothing is written."""

    async def scenario() -> None:
        with pytest.raises(ValueError):
            await _seed(session_factory, "   ")
        assert await _count(session_factory, Rol) == 0
        assert await _count(session_factory, Usuario) == 0

    run(scenario())


def test_cli_sin_variable_de_entorno_aborta(monkeypatch) -> None:
    """Business error: the CLI names the missing variable before connecting."""

    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="SEED_ADMIN_PASSWORD"):
        asyncio.run(main())


def test_seed_es_idempotente(session_factory) -> None:
    """Edge: re-running duplicates neither roles, users nor links."""

    async def scenario() -> None:
        await _seed(session_factory, "demo-secret-123")
        await _seed(session_factory, "demo-secret-123")

        assert await _count(session_factory, Rol) == len(ROLES)
        assert await _count(session_factory, Consultorio) == 1
        assert await _count(session_factory, Usuario) == 1
        assert await _count(session_factory, UsuarioRol) == 1

    run(scenario())


def test_seed_no_reescribe_el_hash(session_factory) -> None:
    """Business rule: a new seed password never changes stored credentials."""

    async def scenario() -> None:
        await _seed(session_factory, "primera-clave")
        async with session_factory() as session:
            original = await session.scalar(
                select(Usuario.hash_password).where(
                    Usuario.email == ADMIN_EMAIL
                )
            )

        await _seed(session_factory, "segunda-clave")
        async with session_factory() as session:
            actual = await session.scalar(
                select(Usuario.hash_password).where(
                    Usuario.email == ADMIN_EMAIL
                )
            )

        assert actual == original
        assert bcrypt.checkpw(b"primera-clave", actual.encode())
        assert not bcrypt.checkpw(b"segunda-clave", actual.encode())

    run(scenario())


def test_seed_concurrente_no_falla(session_factory) -> None:
    """Edge: two simultaneous seeds do not violate unique indexes."""

    async def scenario() -> None:
        await asyncio.gather(
            _seed(session_factory, "demo-secret-123"),
            _seed(session_factory, "demo-secret-123"),
        )

        assert await _count(session_factory, Rol) == len(ROLES)
        assert await _count(session_factory, Consultorio) == 1
        assert await _count(session_factory, Usuario) == 1
        assert await _count(session_factory, UsuarioRol) == 1

    run(scenario())
