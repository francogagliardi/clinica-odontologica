"""Core model behaviour against real PostgreSQL (C-02 specs)."""

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError

from app.infrastructure.audit import registrar
from app.models import (
    Consultorio,
    RegistroAuditoria,
    Rol,
    Usuario,
    UsuarioRol,
)
from tests.integration.helpers import run, sqlstate


def _consultorio(slug: str = "demo") -> Consultorio:
    return Consultorio(nombre="Consultorio Demo", slug=slug)


def _usuario(email: str = "ana@clinica.test") -> Usuario:
    return Usuario(
        nombre="Ana Pérez",
        email=email,
        hash_password="$2b$12$fakeparahashparatest0000000000000000000000000000000000",
    )


def test_alta_de_identidad_y_roles(session_factory) -> None:
    """Expected: usuario with roles persists and reads back with UUID v4 id."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            consultorio = _consultorio()
            usuario = _usuario()
            rol = Rol(nombre="odontologo")
            session.add_all([consultorio, usuario, rol])
            await session.flush()
            session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id))

        async with session_factory() as session:
            cargado = await session.scalar(
                select(Usuario).where(Usuario.email == "ana@clinica.test")
            )
            assert cargado is not None
            assert isinstance(cargado.id, uuid.UUID)
            assert cargado.id.version == 4
            assert [r.nombre for r in cargado.roles] == ["odontologo"]
            assert cargado.is_active is True
            assert cargado.deleted_at is None

            saved_consultorio = await session.scalar(
                select(Consultorio).where(Consultorio.slug == "demo")
            )
            assert saved_consultorio is not None
            assert saved_consultorio.id.version == 4

    run(scenario())


def test_email_duplicado_activo_rechazado_23505(session_factory) -> None:
    """Business error: two active users cannot share an email."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            session.add(_usuario("dup@clinica.test"))

        with pytest.raises(DBAPIError) as excinfo:
            async with session_factory() as session, session.begin():
                session.add(_usuario("dup@clinica.test"))
        assert sqlstate(excinfo.value) == "23505"

    run(scenario())


def test_slug_duplicado_activo_rechazado_23505(session_factory) -> None:
    """Business error: two active consultorios cannot share a slug."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            session.add(_consultorio("centro"))

        with pytest.raises(DBAPIError) as excinfo:
            async with session_factory() as session, session.begin():
                session.add(_consultorio("centro"))
        assert sqlstate(excinfo.value) == "23505"

    run(scenario())


def test_rol_duplicado_activo_rechazado_23505(session_factory) -> None:
    """Business error: role names are unique among active roles."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            session.add(Rol(nombre="asistente"))

        with pytest.raises(DBAPIError) as excinfo:
            async with session_factory() as session, session.begin():
                session.add(Rol(nombre="asistente"))
        assert sqlstate(excinfo.value) == "23505"

    run(scenario())


def test_email_reutilizable_tras_baja_logica(session_factory) -> None:
    """Edge: a soft-deleted email can be reused without deleting history."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            original = _usuario("reuso@clinica.test")
            session.add(original)
            await session.flush()
            original.soft_delete()

        async with session_factory() as session, session.begin():
            session.add(_usuario("reuso@clinica.test"))

        async with session_factory() as session:
            total = await session.scalar(
                select(func.count())
                .select_from(Usuario)
                .where(Usuario.email == "reuso@clinica.test")
            )
            activos = await session.scalar(
                select(func.count())
                .select_from(Usuario)
                .where(
                    Usuario.email == "reuso@clinica.test",
                    Usuario.deleted_at.is_(None),
                )
            )
            assert total == 2
            assert activos == 1

    run(scenario())


def test_slug_y_rol_reutilizables_tras_baja(session_factory) -> None:
    """Edge: soft-deleted slug/role names do not block their reuse."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            consultorio = _consultorio("norte")
            rol = Rol(nombre="recepcionista")
            session.add_all([consultorio, rol])
            await session.flush()
            consultorio.soft_delete()
            rol.soft_delete()

        async with session_factory() as session, session.begin():
            session.add_all(
                [_consultorio("norte"), Rol(nombre="recepcionista")]
            )

        async with session_factory() as session:
            activos = await session.scalar(
                select(func.count()).select_from(Consultorio).where(
                    Consultorio.slug == "norte",
                    Consultorio.deleted_at.is_(None),
                )
            )
            roles = await session.scalar(
                select(func.count()).select_from(Rol).where(
                    Rol.nombre == "recepcionista",
                    Rol.deleted_at.is_(None),
                )
            )
            assert activos == 1
            assert roles == 1

    run(scenario())


def test_asignacion_repetida_de_rol_no_duplica(session_factory) -> None:
    """Edge: replaying the same role assignment leaves exactly one link."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            usuario = _usuario("replay@clinica.test")
            rol = Rol(nombre="auditor")
            session.add_all([usuario, rol])
            await session.flush()
            usuario_id, rol_id = usuario.id, rol.id

        for _ in range(2):
            async with session_factory() as session, session.begin():
                await session.execute(
                    insert(UsuarioRol)
                    .values(usuario_id=usuario_id, rol_id=rol_id)
                    .on_conflict_do_nothing(
                        index_elements=["usuario_id", "rol_id"]
                    )
                )

        async with session_factory() as session:
            links = await session.scalar(
                select(func.count())
                .select_from(UsuarioRol)
                .where(UsuarioRol.usuario_id == usuario_id)
            )
            assert links == 1

    run(scenario())


def test_baja_logica_incoherente_rechazada_por_check(session_factory) -> None:
    """Edge: the database refuses a half-deleted row (is_active without date)."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            usuario = _usuario("check@clinica.test")
            session.add(usuario)
            await session.flush()
            usuario_id = usuario.id

        with pytest.raises(DBAPIError) as excinfo:
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE usuarios SET is_active = false WHERE id = :id"
                    ),
                    {"id": usuario_id},
                )
        assert sqlstate(excinfo.value) == "23514"

    run(scenario())


def test_auditoria_registra_usuario_y_sistema(session_factory) -> None:
    """Expected: actions are appended for a person and for a system actor."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            usuario = _usuario("auditor@clinica.test")
            session.add(usuario)
            await session.flush()
            usuario_id = usuario.id

        async with session_factory() as session, session.begin():
            await registrar(
                session,
                accion="usuario.login",
                entidad="usuario",
                entidad_id=usuario_id,
                usuario_id=usuario_id,
                ip="203.0.113.10",
                dispositivo="pytest",
            )
            await registrar(
                session,
                accion="recordatorio.enviado",
                entidad="turno",
                entidad_id="00000000-0000-4000-8000-000000000000",
            )

        async with session_factory() as session:
            registros = list(
                await session.scalars(
                    select(RegistroAuditoria).order_by(
                        RegistroAuditoria.timestamp
                    )
                )
            )
            assert [r.accion for r in registros] == [
                "usuario.login",
                "recordatorio.enviado",
            ]
            assert registros[0].usuario_id == usuario_id
            assert registros[0].ip == "203.0.113.10"
            assert registros[1].usuario_id is None
            assert registros[0].timestamp.tzinfo is not None

    run(scenario())


def test_auditoria_rechaza_update_y_delete(session_factory) -> None:
    """Business error: the audit trail is append-only (RN-SE-02)."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            await registrar(
                session, accion="alta", entidad="usuario", entidad_id="1"
            )
            registro_id = await session.scalar(
                select(RegistroAuditoria.id)
            )

        for statement in (
            "UPDATE registro_auditoria SET accion = 'alterado' WHERE id = :id",
            "DELETE FROM registro_auditoria WHERE id = :id",
        ):
            with pytest.raises(DBAPIError) as excinfo:
                async with session_factory() as session, session.begin():
                    await session.execute(
                        text(statement), {"id": registro_id}
                    )
            assert sqlstate(excinfo.value) == "P0001"
            assert "append-only" in str(excinfo.value)

        async with session_factory() as session:
            registro = await session.get(RegistroAuditoria, registro_id)
            assert registro is not None
            assert registro.accion == "alta"

    run(scenario())


def test_auditoria_rechaza_truncate(session_factory) -> None:
    """Edge: TRUNCATE would bypass row triggers, so a statement trigger blocks it."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            await registrar(
                session, accion="alta", entidad="usuario", entidad_id="1"
            )

        with pytest.raises(DBAPIError) as excinfo:
            async with session_factory() as session, session.begin():
                await session.execute(text("TRUNCATE registro_auditoria"))
        assert sqlstate(excinfo.value) == "P0001"

        async with session_factory() as session:
            total = await session.scalar(
                select(func.count()).select_from(RegistroAuditoria)
            )
            assert total == 1

    run(scenario())


def test_baja_de_usuario_conserva_auditoria(session_factory) -> None:
    """Edge: soft-deleting a user keeps the audit row and its reference."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            usuario = _usuario("baja@clinica.test")
            session.add(usuario)
            await session.flush()
            usuario_id = usuario.id
            await registrar(
                session,
                accion="usuario.alta",
                entidad="usuario",
                entidad_id=usuario_id,
                usuario_id=usuario_id,
            )

        async with session_factory() as session, session.begin():
            usuario = await session.get(Usuario, usuario_id)
            assert usuario is not None
            usuario.soft_delete()

        async with session_factory() as session:
            usuario = await session.get(Usuario, usuario_id)
            assert usuario is not None
            assert usuario.deleted_at is not None
            assert usuario.is_active is False
            registro = await session.scalar(
                select(RegistroAuditoria).where(
                    RegistroAuditoria.usuario_id == usuario_id
                )
            )
            assert registro is not None
            assert registro.entidad_id == str(usuario_id)

    run(scenario())
