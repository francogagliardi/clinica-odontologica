"""C-16 `0015_admin_auditoria`: three viewer indexes, no tables, append-only.

Tasks 1.1–1.3:

- the head is `0015_admin_auditoria` and the three indexes that sustain the
  audit viewer order/filters exist;
- `upgrade head` → `downgrade 0014_reportes` → `upgrade head` is reversible and
  leaves the schema identical;
- a direct SQL `UPDATE`/`DELETE`/`TRUNCATE` on `registro_auditoria` is still
  rejected with `P0001`, and no privacy-acceptance index was added.
"""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Base
from tests.integration.helpers import run, sqlstate

BACKEND_DIR = Path(__file__).resolve().parents[2]

_INDICES_0015 = {
    "ix_registro_auditoria_timestamp",
    "ix_registro_auditoria_accion_timestamp",
    "ix_registro_auditoria_entidad_timestamp",
}
_INDICES_ANTERIORES = {
    "ix_registro_auditoria_usuario_timestamp",
    "ix_registro_auditoria_entidad",
}


def _alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
        capture_output=True,
        text=True,
    )


async def _snapshot(engine) -> dict[str, object]:
    async with engine.connect() as connection:
        tables = set(
            await connection.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        )
        indexes = {
            name: definition
            for name, definition in (
                await connection.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname = 'public'"
                    )
                )
            ).all()
        }
        triggers = set(
            await connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
                )
            )
        )
        version = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
    return {
        "tables": tables,
        "indexes": indexes,
        "triggers": triggers,
        "version": version,
    }


def test_c16_upgrade_crea_solo_los_tres_indices_del_visor(engine) -> None:
    """Expected: head 0015 with the three viewer indexes and no new table."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0015_admin_auditoria"
        assert snapshot["tables"] == set(Base.metadata.tables) | {
            "alembic_version"
        }

        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert _INDICES_0015 <= set(indexes)
        assert _INDICES_ANTERIORES <= set(indexes)

        timestamp = indexes["ix_registro_auditoria_timestamp"]
        assert "timestamp" in timestamp and "DESC" in timestamp
        assert "id DESC" in timestamp

        accion = indexes["ix_registro_auditoria_accion_timestamp"]
        assert "accion" in accion
        assert "timestamp" in accion and "DESC" in accion

        entidad = indexes["ix_registro_auditoria_entidad_timestamp"]
        assert "entidad" in entidad
        assert "timestamp" in entidad and "DESC" in entidad

        triggers: set[str] = snapshot["triggers"]  # type: ignore[assignment]
        assert {
            "trg_registro_auditoria_sin_update_delete",
            "trg_registro_auditoria_sin_truncate",
        } <= triggers

    run(scenario())


def test_c16_no_agrega_indices_de_aceptacion_de_privacidad(engine) -> None:
    """Business rule: privacy acceptance is out of scope for the migration."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert not [
            nombre
            for nombre in indexes
            if "privacidad" in nombre.lower()
            or "aceptacion" in nombre.lower()
            or "aceptada" in nombre.lower()
        ]
        tables: set[str] = snapshot["tables"]  # type: ignore[assignment]
        assert not [
            nombre
            for nombre in tables
            if "privacidad" in nombre.lower()
            or "aceptacion" in nombre.lower()
            or "aceptada" in nombre.lower()
        ]

    run(scenario())


def test_c16_downgrade_y_upgrade_restaura_los_indices(
    migrated_database: str, engine
) -> None:
    """Edge: 0015 ⇄ 0014 is reversible and leaves the rest untouched."""

    _alembic("downgrade", "0014_reportes", database_url=migrated_database)

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0014_reportes"
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert not _INDICES_0015 & set(indexes)
        assert _INDICES_ANTERIORES <= set(indexes)
        assert {"usuarios", "registro_auditoria"} <= set(
            snapshot["tables"]  # type: ignore[arg-type]
        )
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0015_admin_auditoria"
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert _INDICES_0015 <= set(indexes)
        return snapshot

    restored = run(after_upgrade())
    assert restored["tables"] == set(Base.metadata.tables) | {
        "alembic_version"
    }


def test_c16_sql_directo_auditoria_sigue_append_only(session_factory) -> None:
    """Business error: the viewer indexes do not weaken the append-only rule."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO registro_auditoria "
                    "(id, accion, entidad, entidad_id, ip, dispositivo) "
                    "VALUES (gen_random_uuid(), 'usuario.crear', 'usuario', "
                    "'00000000-0000-0000-0000-000000000001', "
                    "'127.0.0.1', 'pytest')"
                )
            )
            registro_id = await session.scalar(
                text("SELECT id FROM registro_auditoria LIMIT 1")
            )

        for statement in (
            "UPDATE registro_auditoria SET accion = 'alterado' WHERE id = :id",
            "DELETE FROM registro_auditoria WHERE id = :id",
        ):
            try:
                async with session_factory() as session, session.begin():
                    await session.execute(
                        text(statement), {"id": registro_id}
                    )
            except DBAPIError as error:
                assert sqlstate(error) == "P0001"
                assert "append-only" in str(error)
            else:  # pragma: no cover - the trigger must always fire
                raise AssertionError("la auditoría aceptó una escritura")

        try:
            async with session_factory() as session, session.begin():
                await session.execute(text("TRUNCATE registro_auditoria"))
        except DBAPIError as error:
            assert sqlstate(error) == "P0001"
        else:  # pragma: no cover - the statement trigger must always fire
            raise AssertionError("la auditoría aceptó TRUNCATE")

        async with session_factory() as session:
            total = await session.scalar(
                text("SELECT count(*) FROM registro_auditoria")
            )
            assert total == 1

    run(scenario())
