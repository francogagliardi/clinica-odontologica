"""C-15 `0014_reportes`: exportation DDL, CHECKs, indexes and SQL rejects.

Two families of tests live here (tasks 1.3/1.6):

- the migrated schema exposes the `exportaciones` table, its named CHECKs, the
  unique partial index that keeps one job per combination and the head
  `0014_reportes`;
- a direct SQL write that breaks an invariant is rejected by PostgreSQL with
  the exact SQLSTATE the design promises (`23514`/`23505`).
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Base
from tests.integration.helpers import run, sqlstate
from tests.integration.reportes_helpers import (
    insertar_exportacion_db,
    setup_exportaciones,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]

_CHECKS_EXPORTACIONES = {
    "ck_exportaciones_alcance_valido",
    "ck_exportaciones_estado_valido",
    "ck_exportaciones_alcance_paciente_coherente",
    "ck_exportaciones_estado_coherente",
    "ck_exportaciones_fallida_con_error",
    "ck_exportaciones_intentos_no_negativos",
    "ck_exportaciones_tamano_positivo",
}
_INDICES_EXPORTACIONES = {
    "ix_exportaciones_estado_proximo",
    "ix_exportaciones_consultorio_fecha",
    "ix_exportaciones_paciente",
    "uq_exportaciones_en_curso",
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
        checks = set(
            await connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE contype = 'c' "
                    "AND connamespace = 'public'::regnamespace"
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
        columns = {
            name: (data_type, is_nullable, column_default)
            for name, data_type, is_nullable, column_default in (
                await connection.execute(
                    text(
                        "SELECT column_name, data_type, is_nullable, "
                        "column_default FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'exportaciones'"
                    )
                )
            ).all()
        }
        version = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
    return {
        "tables": tables,
        "checks": checks,
        "indexes": indexes,
        "columns": columns,
        "version": version,
    }


async def _sqlstate_exportacion(
    session_factory, **kwargs: object
) -> str | None:
    try:
        await insertar_exportacion_db(session_factory, **kwargs)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_c15_upgrade_crea_exportaciones_con_checks_e_indices(engine) -> None:
    """Expected: head is 0014 and `exportaciones` carries every D12 object."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0015_admin_auditoria"
        assert "exportaciones" in snapshot["tables"]
        assert snapshot["tables"] == set(Base.metadata.tables) | {
            "alembic_version"
        }

        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_EXPORTACIONES <= checks

        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert _INDICES_EXPORTACIONES <= set(indexes)

        assert [
            column
            for column in ("estado", "proximo_intento")
            if column in indexes["ix_exportaciones_estado_proximo"]
        ] == ["estado", "proximo_intento"]
        assert "consultorio_id" in indexes[
            "ix_exportaciones_consultorio_fecha"
        ]
        assert "created_at" in indexes[
            "ix_exportaciones_consultorio_fecha"
        ]
        assert "paciente_id" in indexes["ix_exportaciones_paciente"]

        en_curso = indexes["uq_exportaciones_en_curso"]
        assert "UNIQUE INDEX" in en_curso
        assert "consultorio_id" in en_curso
        assert "solicitado_por" in en_curso
        assert "alcance" in en_curso
        assert "COALESCE" in en_curso
        assert "pendiente" in en_curso and "generando" in en_curso

        columns: dict[str, tuple] = snapshot["columns"]  # type: ignore[assignment]
        assert not columns["intentos"][1] == "YES"
        assert columns["intentos"][2] == "0"
        assert columns["estado"][2] == "'pendiente'::character varying"
        assert columns["alcance"][1] == "NO"
        assert columns["paciente_id"][1] == "YES"
        assert columns["contenido"][1] == "YES"
        assert columns["generada_at"][1] == "YES"
        assert "deleted_at" not in columns
        assert "is_active" not in columns
        assert {"created_at", "updated_at"} <= set(columns)

    run(scenario())


def test_c15_sql_directo_rechaza_alcance_incoherente(session_factory) -> None:
    """Business error: the scope and its patient must agree (23514)."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        solicitado_por = data["actores"]["administrador"].id
        paciente_id = data["paciente"].id

        # 1) Patient scope without a patient.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="paciente",
            paciente_id=None,
        ) == "23514"

        # 2) Consultorio scope carrying a patient.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="consultorio",
            paciente_id=paciente_id,
        ) == "23514"

        # 3) An unknown scope value.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="historias",
        ) == "23514"

        # The coherent patient scope is accepted.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="paciente",
            paciente_id=paciente_id,
        ) is None

    run(scenario())


def test_c15_sql_directo_rechaza_estado_incoherente(session_factory) -> None:
    """Business error: `lista` needs its artifact and `fallida` its reason."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        solicitado_por = data["actores"]["administrador"].id

        # 1) `lista` without content, size or generation timestamp.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            estado="lista",
            completar=False,
        ) == "23514"

        # 2) `fallida` without the error that explains the failure.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            estado="fallida",
            ultimo_error=None,
            completar=False,
        ) == "23514"

        # 3) Negative retries are rejected.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            intentos=-1,
        ) == "23514"

        # 4) A non-positive artifact size never happens.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            estado="lista",
            contenido=b"x",
            tamano_bytes=0,
            generada_at=datetime.now(timezone.utc),
        ) == "23514"

        # A coherent `lista` row and a coherent `fallida` row are accepted.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            estado="lista",
        ) is None
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            estado="fallida",
        ) is None

    run(scenario())


def test_c15_sql_directo_rechaza_dos_jobs_en_curso_identicos(
    session_factory,
) -> None:
    """Business error: D7 keeps one identical exportation in progress."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        solicitado_por = data["actores"]["administrador"].id
        paciente_id = data["paciente"].id

        await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="paciente",
            paciente_id=paciente_id,
        )
        # The same combination while still pending must fail.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="paciente",
            paciente_id=paciente_id,
        ) == "23505"

        # A different scope of the same requester is a different job.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="consultorio",
        ) is None

        # Two consultorio jobs of the same requester are identical too.
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="consultorio",
        ) == "23505"

        # Once the pending patient job fails, a new one is allowed.
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE exportaciones SET estado = 'fallida', "
                    "ultimo_error = 'cancelada para el test' "
                    "WHERE alcance = 'paciente' AND estado = 'pendiente'"
                )
            )
        assert await _sqlstate_exportacion(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="paciente",
            paciente_id=paciente_id,
        ) is None

    run(scenario())


def test_c15_downgrade_y_upgrade_restaura_solo_su_tabla(
    migrated_database: str, engine
) -> None:
    """Edge: 0014 ⇄ 0013 is reversible and leaves C-01..C-14 untouched."""

    _alembic(
        "downgrade", "0013_facturacion_arca", database_url=migrated_database
    )

    async def after_downgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0013_facturacion_arca"
        assert "exportaciones" not in snapshot["tables"]
        assert {"comprobantes", "cobros", "turnos"} <= set(
            snapshot["tables"]
        )
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert not _CHECKS_EXPORTACIONES & checks
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert not _INDICES_EXPORTACIONES & set(indexes)

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0015_admin_auditoria"
        assert "exportaciones" in snapshot["tables"]
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_EXPORTACIONES <= checks
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert _INDICES_EXPORTACIONES <= set(indexes)

    run(after_upgrade())
