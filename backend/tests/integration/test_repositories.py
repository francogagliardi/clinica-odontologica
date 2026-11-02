"""Repository contract: no commits, no hard deletes, integrity surfaces."""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.repositories import (
    ConsultorioRepository,
    UsuarioRepository,
)
from app.models import Consultorio, Usuario
from tests.integration.helpers import run


def _usuario(email: str) -> Usuario:
    return Usuario(
        nombre="Ana Pérez",
        email=email,
        hash_password="$2b$12$fakeparahashparatest0000000000000000000000000000000000",
    )


def test_add_no_commitea_y_otra_sesion_no_lo_ve(session_factory) -> None:
    """Business rule: repositories never commit; the unit of work does."""

    async def scenario() -> None:
        async with session_factory() as writer:
            await UsuarioRepository(writer).add(_usuario("nocommit@clinica.test"))

            async with session_factory() as reader:
                visible = await reader.scalar(
                    select(func.count()).select_from(Usuario)
                )
                assert visible == 0

            await writer.commit()

        async with session_factory() as reader:
            visible = await reader.scalar(
                select(func.count()).select_from(Usuario)
            )
            assert visible == 1

    run(scenario())


def test_get_devuelve_entidad_y_none_si_no_existe(session_factory) -> None:
    """Expected: get returns the entity or None (404 decision is the API's)."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            usuario = _usuario("get@clinica.test")
            session.add(usuario)
            await session.flush()
            usuario_id = usuario.id

        async with session_factory() as session:
            repo = UsuarioRepository(session)
            encontrado = await repo.get(usuario_id)
            assert encontrado is not None
            assert encontrado.email == "get@clinica.test"
            assert await repo.get(uuid.uuid4()) is None

    run(scenario())


def test_list_oculta_bajas_y_include_inactive_las_muestra(
    session_factory,
) -> None:
    """Expected: listings exclude soft-deleted rows unless explicitly asked."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            viva = _usuario("viva@clinica.test")
            baja = _usuario("baja@clinica.test")
            session.add_all([viva, baja])
            await session.flush()
            baja.soft_delete()

        async with session_factory() as session:
            repo = UsuarioRepository(session)
            assert [u.email for u in await repo.list()] == ["viva@clinica.test"]
            todos = await repo.list(include_inactive=True)
            assert {u.email for u in todos} == {
                "viva@clinica.test",
                "baja@clinica.test",
            }

    run(scenario())


def test_alta_y_modificacion_actualizan_timestamps(session_factory) -> None:
    """Expected: timestamps carry timezone and updated_at advances on update."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            session.add(Consultorio(nombre="Uno", slug="timestamps"))

        async with session_factory() as session, session.begin():
            consultorio = await session.scalar(
                select(Consultorio).where(Consultorio.slug == "timestamps")
            )
            assert consultorio is not None
            assert consultorio.created_at.tzinfo is not None
            assert consultorio.updated_at.tzinfo is not None
            assert consultorio.deleted_at is None
            consultorio.nombre = "Dos"

        async with session_factory() as session:
            consultorio = await session.scalar(
                select(Consultorio).where(Consultorio.slug == "timestamps")
            )
            assert consultorio is not None
            assert consultorio.updated_at > consultorio.created_at
            assert consultorio.deleted_at is None

    run(scenario())


def test_soft_delete_es_idempotente(session_factory) -> None:
    """Edge: deleting twice keeps the original timestamp and one active row."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            usuario = _usuario("doble@clinica.test")
            session.add(usuario)
            await session.flush()
            repo = UsuarioRepository(session)

            await repo.soft_delete(usuario)
            primera_marca = usuario.deleted_at
            await repo.soft_delete(usuario)
            assert usuario.deleted_at == primera_marca

        async with session_factory() as session:
            activos = await session.scalar(
                select(func.count()).select_from(Usuario).where(
                    Usuario.deleted_at.is_(None)
                )
            )
            assert activos == 0

    run(scenario())


def test_repositorio_no_expone_borrado_fisico(session_factory) -> None:
    """Business rule: only soft delete exists; history is never destroyed."""

    async def scenario() -> None:
        async with session_factory() as session:
            repo = ConsultorioRepository(session)
            assert hasattr(repo, "soft_delete")
            assert not hasattr(repo, "delete")
            assert not hasattr(repo, "hard_delete")

    run(scenario())


def test_violacion_de_unicidad_se_propaga(session_factory) -> None:
    """Business error: the repository does not swallow constraint errors."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            session.add(Consultorio(nombre="Uno", slug="repetido"))

        async with session_factory() as session:
            repo = ConsultorioRepository(session)
            with pytest.raises(IntegrityError):
                await repo.add(Consultorio(nombre="Dos", slug="repetido"))
            await session.rollback()

        async with session_factory() as session:
            total = await session.scalar(
                select(func.count()).select_from(Consultorio)
            )
            assert total == 1

    run(scenario())
