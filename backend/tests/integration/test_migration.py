"""Migrations under a real PostgreSQL: DDL, parity and reversibility (C-02/C-03)."""

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Base
from tests.integration.clinica_helpers import (
    insertar_consentimiento_db,
    insertar_evolucion_db,
    insertar_hallazgo_db,
    insertar_historia_db,
    insertar_odontograma_db,
    setup_clinica,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.presupuestos_helpers import (
    insertar_item_db,
    insertar_presupuesto_db,
    setup_presupuestos,
)

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
    """Expected: `upgrade head` creates every table declared in the ORM."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
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
            "uq_profesionales_matricula_activo",
            "uq_sillones_nombre_activo",
            "uq_prestaciones_codigo_activo",
            "uq_pacientes_dni_activo",
            "uq_obras_sociales_nombre_activo",
        ):
            assert "WHERE (deleted_at IS NULL)" in indexes[name], name

    run(scenario())


def test_turnos_declara_exclusion_y_token_publico(engine) -> None:
    """Business rule: anti-overlap lives in PostgreSQL, token unique when set."""

    async def scenario() -> None:
        assert {"ex_turnos_profesional", "ex_turnos_sillon"} <= set(
            await _exclude_constraints(engine)
        )
        snapshot = await _snapshot(engine)
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert "WHERE (token_publico IS NOT NULL)" in indexes[
            "uq_turnos_token_publico"
        ]

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


def test_c05_downgrade_y_upgrade_restaura_solo_sus_tablas(
    migrated_database: str, engine
) -> None:
    """Edge: 0005 ⇄ 0004 is reversible without touching C-04 tables."""

    _alembic("downgrade", "0004_recursos_agendables", database_url=migrated_database)

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0004_recursos_agendables"
        assert snapshot["tables"] == (
            set(Base.metadata.tables)
            - {
                "pacientes",
                "obras_sociales",
                "turnos",
                "recordatorios",
                "mensajes_whatsapp",
                "entradas_lista_espera",
                "historias_clinicas",
                "evoluciones",
                "odontogramas",
                "hallazgos_dentales",
                "adjuntos",
                "consentimientos",
                "presupuestos",
                "items_presupuesto",
            }
            | {"alembic_version"}
        )
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        return await _snapshot(engine)

    restored = run(after_upgrade())
    assert restored["version"] == "0011_presupuestos"
    assert {"pacientes", "obras_sociales", "turnos"} <= restored["tables"]


def test_c06_downgrade_y_upgrade_restaura_turnos(
    migrated_database: str, engine
) -> None:
    """Edge: 0006 ⇄ 0005 is reversible including the exclusion constraints."""

    _alembic("downgrade", "0005_pacientes_cobertura_base", database_url=migrated_database)

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0005_pacientes_cobertura_base"
        assert "turnos" not in snapshot["tables"]
        assert await _exclude_constraints(engine) == []
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        excludes = set(
            await _exclude_constraints(engine)
        )
        assert snapshot["version"] == "0011_presupuestos"
        assert "turnos" in snapshot["tables"]
        assert {"ex_turnos_profesional", "ex_turnos_sillon"} <= excludes
        return snapshot

    run(after_upgrade())


def test_c07_downgrade_y_upgrade_restaura_la_sena(
    migrated_database: str, engine
) -> None:
    """Edge: 0007 only adds the deposit state; 0006 ⇄ 0007 is reversible."""

    _alembic("downgrade", "0006_turnos_anti_solapamiento", database_url=migrated_database)

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0006_turnos_anti_solapamiento"
        columns = snapshot["columns"]
        assert ("turnos", "sena_estado") not in columns
        assert "turnos" in snapshot["tables"]
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert ("turnos", "sena_estado") in snapshot["columns"]
        return snapshot

    run(after_upgrade())


def test_c08_downgrade_y_upgrade_restaura_mensajeria(
    migrated_database: str, engine
) -> None:
    """Edge: 0008 ⇄ 0007 is reversible and only owns the messaging tables."""

    _alembic("downgrade", "0007_reserva_publica", database_url=migrated_database)

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0007_reserva_publica"
        assert "recordatorios" not in snapshot["tables"]
        assert "mensajes_whatsapp" not in snapshot["tables"]
        assert "turnos" in snapshot["tables"]
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert {"recordatorios", "mensajes_whatsapp"} <= snapshot["tables"]
        return snapshot

    run(after_upgrade())


def test_c10_downgrade_y_upgrade_restaura_la_lista_de_espera(
    migrated_database: str, engine
) -> None:
    """Edge: 0009 ⇄ 0008 is reversible and only owns the waiting list."""

    _alembic(
        "downgrade", "0008_whatsapp_recordatorios", database_url=migrated_database
    )

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0008_whatsapp_recordatorios"
        assert "entradas_lista_espera" not in snapshot["tables"]
        assert (
            "mensajes_whatsapp",
            "lista_espera_id",
        ) not in snapshot["columns"]
        assert not {
            "ex_lista_espera_profesional",
            "ex_lista_espera_sillon",
        } & set(await _exclude_constraints(engine))
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert "entradas_lista_espera" in snapshot["tables"]
        assert ("mensajes_whatsapp", "lista_espera_id") in snapshot["columns"]
        assert {
            "ex_lista_espera_profesional",
            "ex_lista_espera_sillon",
        } <= set(await _exclude_constraints(engine))
        assert ("mensajes_whatsapp", "turno_id") in await _columnas_nullable(
            engine
        )
        return snapshot

    run(after_upgrade())


async def _columnas_nullable(engine) -> set[tuple[str, str]]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT table_name, column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND is_nullable = 'YES'"
            )
        )
        return {(table, column) for table, column in rows.all()}


async def _exclude_constraints(engine) -> list[str]:
    async with engine.connect() as connection:
        return list(
            await connection.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE contype = 'x' "
                    "AND connamespace = 'public'::regnamespace"
                )
            )
        )

# --- C-11 `0010_historia_clinica` -----------------------------------------

_TABLAS_CLINICA = {
    "historias_clinicas",
    "evoluciones",
    "odontogramas",
    "hallazgos_dentales",
    "adjuntos",
    "consentimientos",
}
_TRIGGERS_CLINICA = {
    "trg_evoluciones_inmutabilidad",
    "trg_odontogramas_append_only",
    "trg_hallazgos_dentales_append_only",
    "trg_consentimientos_append_only",
}
_CHECKS_CLINICA = {
    "ck_historias_clinicas_baja_logica_coherente",
    "ck_evoluciones_baja_logica_coherente",
    "ck_evoluciones_firma_coherente",
    "ck_evoluciones_texto_no_vacio",
    "ck_odontogramas_version_positiva",
    "ck_hallazgos_dentales_pieza_fdi_valida",
    "ck_hallazgos_dentales_cara_valida",
    "ck_hallazgos_dentales_estado_valido",
    "ck_hallazgos_dentales_cie10_formato",
    "ck_adjuntos_baja_logica_coherente",
    "ck_adjuntos_mime_permitido",
    "ck_adjuntos_tamano_valido",
    "ck_adjuntos_tamano_coherente",
    "ck_adjuntos_nombre_saneado",
    "ck_consentimientos_tipo_valido",
    "ck_consentimientos_texto_hash_formato",
    "ck_consentimientos_firma_ref_formato",
}


def test_c11_upgrade_crea_las_seis_tablas(engine) -> None:
    """Expected: head is 0010 and the clinical tables exist."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert _TABLAS_CLINICA <= snapshot["tables"]

    run(scenario())


def test_c11_indices_unicos_de_clinica(engine) -> None:
    """Business rule: one active history, one active rectification, no dup version."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        historia = indexes["uq_historias_clinicas_paciente_activa"]
        assert "UNIQUE INDEX" in historia
        assert "paciente_id" in historia
        assert "deleted_at IS NULL" in historia

        rectificacion = indexes["uq_evoluciones_rectificacion_activa"]
        assert "UNIQUE INDEX" in rectificacion
        assert "rectifica_a" in rectificacion
        assert "rectifica_a IS NOT NULL" in rectificacion
        assert "deleted_at IS NULL" in rectificacion

        version = indexes["uq_odontogramas_historia_version"]
        assert "UNIQUE INDEX" in version
        assert "historia_id" in version and "version" in version

        hallazgo = indexes["uq_hallazgos_dentales_odontograma_pieza_cara"]
        assert "UNIQUE INDEX" in hallazgo

    run(scenario())


def test_c11_checks_y_triggers_declarados(engine) -> None:
    """Expected: every CHECK and immutability trigger ships in the migration."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        triggers: set[str] = snapshot["triggers"]  # type: ignore[assignment]
        assert _CHECKS_CLINICA <= checks
        assert _TRIGGERS_CLINICA <= triggers
        functions = await _funciones_trigger(engine)
        assert {
            "evoluciones_inmutabilidad",
            "odontogramas_append_only",
            "hallazgos_dentales_append_only",
            "consentimientos_append_only",
        } <= functions

    run(scenario())


def test_c11_triggers_rechazan_append_only_con_p0001(session_factory) -> None:
    """Business error: signed evolutions and snapshots cannot be rewritten."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        consultorio_id = data["consultorio_id"]
        actores = data["actores"]
        profesional = data["profesional"]
        paciente = data["paciente_propio"]
        historia_id = await insertar_historia_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            abierta_por=actores["odontologo"].id,
        )
        evolucion_id = await insertar_evolucion_db(
            session_factory,
            historia_id=historia_id,
            profesional_id=profesional.id,
            creado_por=actores["odontologo"].id,
            firmada=True,
            firmada_por=actores["odontologo"].id,
            fecha_firma=datetime.now(timezone.utc),
        )
        odontograma_id = await insertar_odontograma_db(
            session_factory, historia_id=historia_id, version=1
        )
        hallazgo_id = await insertar_hallazgo_db(
            session_factory, odontograma_id=odontograma_id
        )
        consentimiento_id = await insertar_consentimiento_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            registrado_por=actores["odontologo"].id,
        )

        assert await _sqlstate_de(
            session_factory,
            "UPDATE evoluciones SET texto = 'adulterado' WHERE id = :id",
            {"id": evolucion_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "DELETE FROM evoluciones WHERE id = :id",
            {"id": evolucion_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "UPDATE odontogramas SET version = 99 WHERE id = :id",
            {"id": odontograma_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "DELETE FROM odontogramas WHERE id = :id",
            {"id": odontograma_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "UPDATE hallazgos_dentales SET estado = 'sano' WHERE id = :id",
            {"id": hallazgo_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "DELETE FROM hallazgos_dentales WHERE id = :id",
            {"id": hallazgo_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "UPDATE consentimientos SET tipo = 'otro' WHERE id = :id",
            {"id": consentimiento_id},
        ) == "P0001"
        assert await _sqlstate_de(
            session_factory,
            "DELETE FROM consentimientos WHERE id = :id",
            {"id": consentimiento_id},
        ) == "P0001"

    run(scenario())


def test_c11_borrador_de_evolucion_se_edita_y_firma(session_factory) -> None:
    """Edge: the trigger must not block the legal draft ? signature path."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        actores = data["actores"]
        historia_id = await insertar_historia_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_propio"].id,
            abierta_por=actores["odontologo"].id,
        )
        evolucion_id = await insertar_evolucion_db(
            session_factory,
            historia_id=historia_id,
            profesional_id=data["profesional"].id,
            creado_por=actores["odontologo"].id,
        )

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE evoluciones SET texto = 'Borrador corregido' "
                    "WHERE id = :id"
                ),
                {"id": evolucion_id},
            )
            await session.execute(
                text(
                    "UPDATE evoluciones SET firmada = true, "
                    "firmada_por = :usuario, fecha_firma = now() "
                    "WHERE id = :id"
                ),
                {"id": evolucion_id, "usuario": actores["odontologo"].id},
            )

        async with session_factory() as session:
            texto, firmada = (
                await session.execute(
                    text(
                        "SELECT texto, firmada FROM evoluciones WHERE id = :id"
                    ),
                    {"id": evolucion_id},
                )
            ).one()
        assert texto == "Borrador corregido"
        assert firmada is True

    run(scenario())


def test_c11_pieza_invalida_y_version_duplicada_fallan_en_la_base(
    session_factory,
) -> None:
    """Business error: FDI and version uniqueness are enforced by PostgreSQL."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        actores = data["actores"]
        historia_id = await insertar_historia_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_propio"].id,
            abierta_por=actores["odontologo"].id,
        )
        odontograma_id = await insertar_odontograma_db(
            session_factory, historia_id=historia_id, version=1
        )
        for pieza in (19, 20, 29, 49, 56, 86, 99):
            assert await _sqlstate_de(
                session_factory,
                "INSERT INTO hallazgos_dentales "
                "(id, odontograma_id, pieza, cara, estado) "
                "VALUES (:id, :odontograma_id, :pieza, 'mesial', 'caries')",
                {
                    "id": uuid.uuid4(),
                    "odontograma_id": odontograma_id,
                    "pieza": pieza,
                },
            ) == "23514"
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO odontogramas (id, historia_id, version) "
            "VALUES (:id, :historia_id, 1)",
            {"id": uuid.uuid4(), "historia_id": historia_id},
        ) == "23505"

    run(scenario())


def test_c11_downgrade_limpia_las_seis_tablas(
    migrated_database: str, engine
) -> None:
    """Edge: 0010 ? 0009 is reversible, triggers and functions included."""

    _alembic("downgrade", "0009_lista_espera", database_url=migrated_database)

    async def after_downgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0009_lista_espera"
        assert not _TABLAS_CLINICA & set(snapshot["tables"])
        assert not _TRIGGERS_CLINICA & set(snapshot["triggers"])
        assert not {
            "evoluciones_inmutabilidad",
            "odontogramas_append_only",
            "hallazgos_dentales_append_only",
            "consentimientos_append_only",
        } & await _funciones_trigger(engine)
        # C-01..C-10 tables are untouched by the rollback.
        assert {"pacientes", "turnos", "entradas_lista_espera"} <= set(
            snapshot["tables"]
        )

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert _TABLAS_CLINICA <= snapshot["tables"]
        assert _TRIGGERS_CLINICA <= snapshot["triggers"]

    run(after_upgrade())


async def _funciones_trigger(engine) -> set[str]:
    async with engine.connect() as connection:
        return set(
            await connection.scalars(
                text(
                    "SELECT proname FROM pg_proc "
                    "WHERE pronamespace = 'public'::regnamespace"
                )
            )
        )


async def _sqlstate_de(
    session_factory, statement: str, params: dict[str, object]
) -> str | None:
    """Run a statement expected to fail and return its SQLSTATE."""
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


# --- C-12 `0011_presupuestos` ----------------------------------------------

_TABLAS_PRESUPUESTOS = {"presupuestos", "items_presupuesto"}
_CHECKS_PRESUPUESTOS = {
    "ck_presupuestos_baja_logica_coherente",
    "ck_presupuestos_estado_valido",
    "ck_presupuestos_cobertura_estado_valido",
    "ck_presupuestos_importes_no_negativos",
    "ck_presupuestos_totales_coherentes",
    "ck_items_presupuesto_baja_logica_coherente",
    "ck_items_presupuesto_cantidad_positiva",
    "ck_items_presupuesto_importes_no_negativos",
    "ck_items_presupuesto_totales_item_coherentes",
    "ck_items_presupuesto_pieza_fdi_valida",
}


def test_c12_upgrade_crea_tablas_e_indices(engine) -> None:
    """Expected: head is 0011 and the two budget tables and indexes exist."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert _TABLAS_PRESUPUESTOS <= snapshot["tables"]
        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        paciente = indexes["ix_presupuestos_paciente_created"]
        assert "consultorio_id" in paciente
        assert "paciente_id" in paciente
        assert "created_at" in paciente
        profesional = indexes["ix_presupuestos_profesional_estado"]
        assert "profesional_id" in profesional
        assert "estado" in profesional
        assert "ix_items_presupuesto_presupuesto" in indexes

    run(scenario())


def test_c12_checks_declarados(engine) -> None:
    """Expected: every per-row invariant ships as a named CHECK."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_PRESUPUESTOS <= checks

    run(scenario())


def test_c12_sql_directo_rechaza_invariantes(session_factory) -> None:
    """Business error: PostgreSQL refuses incoherent rows with 23514."""
    data = run(setup_presupuestos(session_factory))
    consultorio_id = data["consultorio_id"]
    paciente = data["paciente_os_demo"]
    profesional = data["profesional"]
    creado_por = data["actores"]["odontologo"].id
    cons = data["prestaciones"]["CONS"]

    async def scenario() -> None:
        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            creado_por=creado_por,
        )

        # cantidad = 0 (the line has zero money, so only this CHECK trips).
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO items_presupuesto "
            "(id, presupuesto_id, prestacion_id, pieza, cantidad, "
            "precio_unitario, cobertura_item, copago_item) "
            "VALUES (:id, :presupuesto_id, :prestacion_id, NULL, 0, "
            "0, 0, 0)",
            {
                "id": uuid.uuid4(),
                "presupuesto_id": presupuesto_id,
                "prestacion_id": cons.id,
            },
        ) == "23514"

        # Invalid FDI teeth.
        for pieza in (19, 49, 86):
            assert await _sqlstate_de(
                session_factory,
                "INSERT INTO items_presupuesto "
                "(id, presupuesto_id, prestacion_id, pieza, cantidad, "
                "precio_unitario, cobertura_item, copago_item) "
                "VALUES (:id, :presupuesto_id, :prestacion_id, :pieza, 1, "
                "10000, 6000, 4000)",
                {
                    "id": uuid.uuid4(),
                    "presupuesto_id": presupuesto_id,
                    "prestacion_id": cons.id,
                    "pieza": pieza,
                },
            ) == "23514"

        # cobertura_item + copago_item != precio_unitario * cantidad.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO items_presupuesto "
            "(id, presupuesto_id, prestacion_id, pieza, cantidad, "
            "precio_unitario, cobertura_item, copago_item) "
            "VALUES (:id, :presupuesto_id, :prestacion_id, 16, 1, "
            "10000, 1, 4000)",
            {
                "id": uuid.uuid4(),
                "presupuesto_id": presupuesto_id,
                "prestacion_id": cons.id,
            },
        ) == "23514"

        # A valid line is accepted (the constraints are not over-strict).
        await insertar_item_db(
            session_factory,
            presupuesto_id=presupuesto_id,
            prestacion_id=cons.id,
            pieza=48,
        )

        # subtotal != cobertura_calculada + copago.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO presupuestos "
            "(id, consultorio_id, paciente_id, profesional_id, creado_por, "
            "estado, cobertura_estado, subtotal, cobertura_calculada, copago) "
            "VALUES (:id, :consultorio_id, :paciente_id, :profesional_id, "
            ":creado_por, 'borrador', 'calculada', 20000, 6000, 4000)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "paciente_id": paciente.id,
                "profesional_id": profesional.id,
                "creado_por": creado_por,
            },
        ) == "23514"

        # Incoherent soft delete: deleted_at set with is_active still true.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO presupuestos "
            "(id, consultorio_id, paciente_id, profesional_id, creado_por, "
            "estado, cobertura_estado, subtotal, cobertura_calculada, copago, "
            "is_active, deleted_at) "
            "VALUES (:id, :consultorio_id, :paciente_id, :profesional_id, "
            ":creado_por, 'borrador', 'calculada', 10000, 6000, 4000, "
            "true, now())",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "paciente_id": paciente.id,
                "profesional_id": profesional.id,
                "creado_por": creado_por,
            },
        ) == "23514"

    run(scenario())


def test_c12_downgrade_limpia_solo_sus_tablas(
    migrated_database: str, engine
) -> None:
    """Edge: 0011 ⇄ 0010 is reversible and leaves C-01–C-11 untouched."""

    _alembic("downgrade", "0010_historia_clinica", database_url=migrated_database)

    async def after_downgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0010_historia_clinica"
        assert not _TABLAS_PRESUPUESTOS & set(snapshot["tables"])
        assert {"pacientes", "turnos", "historias_clinicas"} <= set(
            snapshot["tables"]
        )
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert not _CHECKS_PRESUPUESTOS & checks

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert _TABLAS_PRESUPUESTOS <= snapshot["tables"]

    run(after_upgrade())

