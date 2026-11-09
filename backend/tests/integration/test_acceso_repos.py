"""Access-management repositories on real PostgreSQL (C-16, task 2.3).

Covers `UsuarioRepository.list_all` with deactivated accounts, the atomic role
replacement, the active-administrator count, the filtered audit query with its
total before pagination, and the `EXPLAIN` proof that `0015_admin_auditoria`
indexes the viewer order/filters.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.uow import UnitOfWork
from app.models import RegistroAuditoria, Rol
from tests.integration.acceso_helpers import (
    add_second_admin,
    contar_vinculos,
    desactivar_db,
    roles_db,
    setup_acceso,
)
from tests.integration.helpers import run


async def _rol_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, uuid.UUID]:
    async with session_factory() as session:
        rows = await session.execute(
            text("SELECT id, nombre FROM roles WHERE deleted_at IS NULL")
        )
    return {nombre: rol_id for rol_id, nombre in rows.all()}


def test_list_all_incluye_inactivos_sin_dados_de_baja(session_factory) -> None:
    """Expected: default active only; `incluir_inactivos` adds deactivated."""

    async def scenario() -> None:
        data = await setup_acceso(session_factory)
        actores = data["actores"]
        admin = data["admin"]
        recep = actores["recepcionista"]

        await desactivar_db(session_factory, recep.id)

        async with UnitOfWork(session_factory) as uow:
            activos = await uow.usuarios.list_all()
            todos = await uow.usuarios.list_all(incluir_inactivos=True)

        emails_activos = {usuario.email for usuario in activos}
        emails_todos = {usuario.email for usuario in todos}
        assert admin.email in emails_activos
        assert recep.email not in emails_activos
        assert recep.email in emails_todos
        por_email = {usuario.email: usuario for usuario in todos}
        assert por_email[recep.email].is_active is False
        # The logical deactivation is reversible and keeps the row (no DELETE).
        assert por_email[recep.email].deleted_at is not None
        assert all(usuario.deleted_at is None for usuario in activos)

    run(scenario())


def test_reemplazo_de_roles_es_atomico_y_deduplica(session_factory) -> None:
    """Expected: replace the set atomically; duplicates make one link."""

    async def scenario() -> None:
        data = await setup_acceso(session_factory)
        odontologo = data["actores"]["odontologo"]
        roles = await _rol_ids(session_factory)

        async with UnitOfWork(session_factory) as uow:
            await uow.usuarios.reemplazar_roles(
                odontologo.id, [roles["odontologo"]]
            )
        assert await roles_db(session_factory, odontologo.id) == [
            "odontologo"
        ]

        async with UnitOfWork(session_factory) as uow:
            await uow.usuarios.reemplazar_roles(
                odontologo.id,
                [roles["recepcionista"], roles["recepcionista"], roles["asistente"]],
            )
        assert await roles_db(session_factory, odontologo.id) == [
            "asistente",
            "recepcionista",
        ]
        assert await contar_vinculos(session_factory, odontologo.id) == 2

        # A failure after the replacement rolls back to the previous set.
        with pytest.raises(RuntimeError):
            async with UnitOfWork(session_factory) as uow:
                await uow.usuarios.reemplazar_roles(
                    odontologo.id, [roles["odontologo"]]
                )
                raise RuntimeError("falla simulada después del reemplazo")
        assert await roles_db(session_factory, odontologo.id) == [
            "asistente",
            "recepcionista",
        ]

    run(scenario())


def test_conteo_de_administradores_activos(session_factory) -> None:
    """Expected: only active users with the active administrator role count."""

    async def scenario() -> None:
        data = await setup_acceso(session_factory)
        admin = data["admin"]
        roles = await _rol_ids(session_factory)

        async with UnitOfWork(session_factory) as uow:
            assert await uow.usuarios.contar_administradores_activos() == 1

        segundo = await add_second_admin(session_factory)
        async with UnitOfWork(session_factory) as uow:
            assert await uow.usuarios.contar_administradores_activos() == 2

        await desactivar_db(session_factory, segundo.id)
        async with UnitOfWork(session_factory) as uow:
            assert await uow.usuarios.contar_administradores_activos() == 1

        # A user linked to the administrator role but deactivated never counts.
        odontologo = data["actores"]["odontologo"]
        async with UnitOfWork(session_factory) as uow:
            await uow.usuarios.reemplazar_roles(
                odontologo.id, [roles["administrador"]]
            )
        assert await roles_db(session_factory, odontologo.id) == [
            "administrador"
        ]
        async with UnitOfWork(session_factory) as uow:
            assert await uow.usuarios.contar_administradores_activos() == 2
        await desactivar_db(session_factory, odontologo.id)
        async with UnitOfWork(session_factory) as uow:
            assert await uow.usuarios.contar_administradores_activos() == 1

        # A soft-deleted administrator is not an active administrator either.
        async with UnitOfWork(session_factory) as uow:
            segundo = await uow.usuarios.get(segundo.id)
            assert segundo is not None
            await uow.usuarios.soft_delete(segundo)
        async with UnitOfWork(session_factory) as uow:
            assert await uow.usuarios.contar_administradores_activos() == 1

        # The seeded administrator is still the one keeping the invariant.
        assert admin.email == "admin@clinica.test"

    run(scenario())


async def _insertar_auditoria(
    session_factory: async_sessionmaker[AsyncSession],
    filas: list[tuple[uuid.UUID, uuid.UUID | None, str, str, str, datetime]],
) -> None:
    async with session_factory() as session, session.begin():
        for fila_id, usuario_id, accion, entidad, entidad_id, momento in filas:
            await session.execute(
                text(
                    "INSERT INTO registro_auditoria "
                    "(id, usuario_id, accion, entidad, entidad_id, ip, "
                    "dispositivo, timestamp) "
                    "VALUES (:id, :usuario_id, :accion, :entidad, :entidad_id, "
                    "'127.0.0.1', 'pytest', :momento)"
                ),
                {
                    "id": fila_id,
                    "usuario_id": usuario_id,
                    "accion": accion,
                    "entidad": entidad,
                    "entidad_id": entidad_id,
                    "momento": momento,
                },
            )


def test_consulta_de_auditoria_con_filtros_orden_y_total(session_factory) -> None:
    """Expected: DESC order, combined filters, inclusive bounds and total."""

    async def scenario() -> None:
        data = await setup_acceso(session_factory)
        admin = data["admin"]
        odontologo = data["actores"]["odontologo"]
        base = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        filas = [
            (
                uuid.uuid4(),
                admin.id,
                "usuario.crear",
                "usuario",
                "u-1",
                base,
            ),
            (
                uuid.uuid4(),
                admin.id,
                "usuario.editar",
                "usuario",
                "u-2",
                base + timedelta(minutes=1),
            ),
            (
                uuid.uuid4(),
                odontologo.id,
                "usuario.roles",
                "usuario",
                "u-1",
                base + timedelta(minutes=2),
            ),
            (
                uuid.uuid4(),
                admin.id,
                "usuario.desactivar",
                "usuario",
                "u-2",
                base + timedelta(minutes=3),
            ),
        ]
        await _insertar_auditoria(session_factory, filas)

        async with UnitOfWork(session_factory) as uow:
            todas, total = await uow.auditoria.list_filtrado(limite=10)
            por_usuario, total_usuario = await uow.auditoria.list_filtrado(
                usuario_id=admin.id, limite=10
            )
            por_accion, total_accion = await uow.auditoria.list_filtrado(
                accion="usuario.roles", limite=10
            )
            por_rango, total_rango = await uow.auditoria.list_filtrado(
                desde=base + timedelta(minutes=1),
                hasta=base + timedelta(minutes=2),
                limite=10,
            )
            combinado, total_combinado = await uow.auditoria.list_filtrado(
                usuario_id=admin.id,
                entidad="usuario",
                desde=base + timedelta(minutes=1),
                hasta=base + timedelta(minutes=3),
                limite=10,
            )
            pagina_uno, total_pagina = await uow.auditoria.list_filtrado(
                limite=2, offset=0
            )
            pagina_dos, _ = await uow.auditoria.list_filtrado(
                limite=2, offset=2
            )
            vacia, total_vacia = await uow.auditoria.list_filtrado(
                accion="inexistente", limite=10
            )

        assert total == 4
        assert [fila.accion for fila in todas] == [
            "usuario.desactivar",
            "usuario.roles",
            "usuario.editar",
            "usuario.crear",
        ]
        assert total_usuario == 3
        assert {fila.usuario_id for fila in por_usuario} == {admin.id}
        assert total_accion == 1
        assert [fila.entidad_id for fila in por_accion] == ["u-1"]
        # `desde` and `hasta` are inclusive.
        assert total_rango == 2
        assert {fila.accion for fila in por_rango} == {
            "usuario.editar",
            "usuario.roles",
        }
        assert total_combinado == 2
        assert {fila.accion for fila in combinado} == {
            "usuario.editar",
            "usuario.desactivar",
        }
        assert total_pagina == 4
        assert len(pagina_uno) == 2
        assert [fila.accion for fila in pagina_uno] == [
            "usuario.desactivar",
            "usuario.roles",
        ]
        assert [fila.accion for fila in pagina_dos] == [
            "usuario.editar",
            "usuario.crear",
        ]
        assert vacia == [] and total_vacia == 0

    run(scenario())


@pytest.mark.anyio
async def test_explain_usa_los_indices_de_0015(session_factory) -> None:
    """Evidence: with sequential scans disabled the viewer plans use 0015."""

    async def plan(statement: str) -> str:
        async with session_factory() as session, session.begin():
            await session.execute(text("SET LOCAL enable_seqscan = off"))
            filas = await session.scalars(text(f"EXPLAIN {statement}"))
            return "\n".join(filas)

    orden = await plan(
        "SELECT * FROM registro_auditoria "
        "ORDER BY timestamp DESC, id DESC LIMIT 10"
    )
    assert "ix_registro_auditoria_timestamp" in orden

    accion = await plan(
        "SELECT * FROM registro_auditoria WHERE accion = 'usuario.crear' "
        "ORDER BY timestamp DESC LIMIT 10"
    )
    assert "ix_registro_auditoria_accion_timestamp" in accion

    entidad = await plan(
        "SELECT * FROM registro_auditoria WHERE entidad = 'usuario' "
        "ORDER BY timestamp DESC LIMIT 10"
    )
    assert "ix_registro_auditoria_entidad_timestamp" in entidad


def test_auditoria_expone_solo_lectura_y_append(session_factory) -> None:
    """Business rule: the repository has no update/delete surface."""

    async def scenario() -> None:
        await setup_acceso(session_factory)
        async with UnitOfWork(session_factory) as uow:
            assert not hasattr(uow.auditoria, "update")
            assert not hasattr(uow.auditoria, "delete")
            assert not hasattr(uow.auditoria, "soft_delete")
            filas = await uow.auditoria.list()
            assert filas == []
            assert isinstance(RegistroAuditoria, type)
            assert isinstance(Rol, type)

    run(scenario())
