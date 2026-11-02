"""Migration 0002 under a real PostgreSQL: DDL, parity and reversibility."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.models import Base
from tests.integration.helpers import run

BACKEND_DIR = Path(__file__).resolve().parents[2]


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
        columns = {
            (table, column)
            for table, column in (
                await connection.execute(
                    text(
                        "SELECT table_name, column_name "
                        "FROM information_schema.columns "
                        "WHERE table_schema = 'public'"
                    )
                )
            ).all()
        }
        checks = set(
            await connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
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
        version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    return {
        "tables": tables,
        "columns": columns,
        "checks": checks,
        "indexes": indexes,
        "triggers": triggers,
        "version": version,
    }


def test_upgrade_crea_tablas_columnas_e_indices(engine) -> None:
    """Expected: 0002 creates exactly the five tables with their columns."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0002_core_models_seguridad"
        assert snapshot["tables"] == set(Base.metadata.tables) | {
            "alembic_version"
        }
        metadata_columns = {
            (table.name, column.name)
            for table in Base.metadata.tables.values()
            for column in table.columns
        }
        assert metadata_columns <= snapshot["columns"]

    run(scenario())


def test_paridad_orm_esquema(engine) -> None:
    """Expected: every declared index, CHECK and trigger exists in the DB."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]

        for table in Base.metadata.tables.values():
            for index in table.indexes:
                assert index.name in indexes, f"falta el índice {index.name}"
                if index.unique:
                    assert "UNIQUE INDEX" in indexes[index.name]

        expected_checks = {
            constraint.name
            for table in Base.metadata.tables.values()
            for constraint in table.constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        }
        assert expected_checks <= snapshot["checks"]

        assert {
            "trg_registro_auditoria_sin_update_delete",
            "trg_registro_auditoria_sin_truncate",
        } <= snapshot["triggers"]

    run(scenario())


def test_indices_unicos_son_parciales(engine) -> None:
    """Business rule: uniqueness only applies to active rows."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        for name in (
            "uq_consultorios_slug_activo",
            "uq_roles_nombre_activo",
            "uq_usuarios_email_activo",
        ):
            assert "WHERE (deleted_at IS NULL)" in indexes[name], name

    run(scenario())


def test_upgrade_repetido_es_no_op(migrated_database: str, engine) -> None:
    """Edge: running upgrade head again changes nothing (idempotent deploy)."""

    async def before() -> dict[str, object]:
        return await _snapshot(engine)

    first = run(before())
    _alembic("upgrade", "head", database_url=migrated_database)
    second = run(before())
    assert first == second


def test_base_inalcanzable_falla_sin_esquema_parcial(
    migrated_database: str, engine
) -> None:
    """Business error: a wrong URL fails naming the connection, changing nothing."""

    async def snapshot() -> dict[str, object]:
        return await _snapshot(engine)

    before = run(snapshot())
    unreachable = "postgresql+asyncpg://clinica:secret@127.0.0.1:1/clinica"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": unreachable},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "connect" in (result.stdout + result.stderr).lower()
    assert run(snapshot()) == before


def test_downgrade_y_upgrade_restaura_el_esquema(
    migrated_database: str, engine
) -> None:
    """Edge: the migration is reversible, triggers included."""

    _alembic("downgrade", "base", database_url=migrated_database)

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["tables"] == {"alembic_version"}
        assert snapshot["triggers"] == set()
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        return await _snapshot(engine)

    restored = run(after_upgrade())
    assert restored["tables"] == set(Base.metadata.tables) | {"alembic_version"}
    assert "trg_registro_auditoria_sin_truncate" in restored["triggers"]
