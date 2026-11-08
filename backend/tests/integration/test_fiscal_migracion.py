"""C-14 `0013_facturacion_arca`: DDL, CHECKs, indexes and SQL rejects.

Two families of tests live here (task 1.2/1.5):

- the migrated schema exposes the five new tables, their named CHECKs, the
  partial unique indexes of D5 and the period exclusion constraint of D9;
- a direct SQL write that breaks an invariant is rejected by PostgreSQL with
  the exact SQLSTATE the spec promises (`23505`, `23514`, `23P01`).
"""

import os
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Base
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.fiscal_helpers import (
    CAE_PRUEBA,
    FECHA_FISCAL,
    insertar_comprobante_db,
    insertar_liquidacion_db,
    setup_fiscal,
)
from tests.integration.helpers import run, sqlstate

BACKEND_DIR = Path(__file__).resolve().parents[2]

_TABLAS_FISCALES = {
    "comprobantes",
    "comprobantes_envios",
    "secuencias_comprobantes",
    "liquidaciones_obras_sociales",
    "items_liquidacion",
}
_CHECKS_FISCALES = {
    "ck_comprobantes_baja_logica_coherente",
    "ck_comprobantes_tipo_valido",
    "ck_comprobantes_ambiente_valido",
    "ck_comprobantes_estado_valido",
    "ck_comprobantes_numero_interno_positivo",
    "ck_comprobantes_punto_venta_positivo",
    "ck_comprobantes_numero_fiscal_positivo",
    "ck_comprobantes_importe_positivo",
    "ck_comprobantes_intentos_no_negativos",
    "ck_comprobantes_cae_formato",
    "ck_comprobantes_estado_fiscal_coherente",
    "ck_comprobantes_fallido_con_error",
    "ck_comprobantes_envios_baja_logica_coherente",
    "ck_comprobantes_envios_canal_valido",
    "ck_comprobantes_envios_estado_valido",
    "ck_comprobantes_envios_destino_no_vacio",
    "ck_secuencias_comprobantes_punto_venta_positivo",
    "ck_secuencias_comprobantes_contadores_no_negativos",
    "ck_liquidaciones_obras_sociales_baja_logica_coherente",
    "ck_liquidaciones_obras_sociales_estado_valido",
    "ck_liquidaciones_obras_sociales_periodo_valido",
    "ck_liquidaciones_obras_sociales_cierre_coherente",
    "ck_liquidaciones_obras_sociales_totales_no_negativos",
    "ck_items_liquidacion_baja_logica_coherente",
    "ck_items_liquidacion_cantidad_positiva",
    "ck_items_liquidacion_cobertura_no_negativa",
}
_INDICES_FISCALES = {
    "uq_comprobantes_cobro",
    "uq_comprobantes_numero_interno",
    "uq_comprobantes_cae",
    "uq_comprobantes_fiscal",
    "ix_comprobantes_estado_proximo",
    "ix_comprobantes_paciente",
    "ix_comprobantes_fecha",
    "uq_comprobantes_envios_comprobante_canal",
    "uq_items_liquidacion_item",
    "ix_liquidaciones_obras_social_periodo",
    "ix_liquidaciones_estado",
    "ix_items_liquidacion_liquidacion",
    "ix_items_liquidacion_presupuesto",
    "ix_items_liquidacion_cobro",
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
        excludes = {
            name: definition
            for name, definition in (
                await connection.execute(
                    text(
                        "SELECT conname, pg_get_constraintdef(oid) "
                        "FROM pg_constraint WHERE contype = 'x' "
                        "AND connamespace = 'public'::regnamespace"
                    )
                )
            ).all()
        }
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
        version = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
    return {
        "tables": tables,
        "checks": checks,
        "excludes": excludes,
        "indexes": indexes,
        "version": version,
    }


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


async def _sqlstate_comprobante(
    session_factory, **kwargs: object
) -> str | None:
    try:
        await insertar_comprobante_db(session_factory, **kwargs)
    except DBAPIError as error:
        return sqlstate(error)
    return None


async def _sqlstate_liquidacion(
    session_factory, **kwargs: object
) -> str | None:
    try:
        await insertar_liquidacion_db(session_factory, **kwargs)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_c14_upgrade_crea_tablas_checks_e_indices(engine) -> None:
    """Expected: head is 0013 with the five tables and every C-14 object."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0014_reportes"
        assert _TABLAS_FISCALES <= set(snapshot["tables"])
        assert _TABLAS_FISCALES <= set(Base.metadata.tables)
        assert snapshot["tables"] == set(Base.metadata.tables) | {
            "alembic_version"
        }

        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_FISCALES <= checks

        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert _INDICES_FISCALES <= set(indexes)

        assert "UNIQUE INDEX" in indexes["uq_comprobantes_cobro"]
        assert "cobro_id" in indexes["uq_comprobantes_cobro"]

        interno = indexes["uq_comprobantes_numero_interno"]
        assert "UNIQUE INDEX" in interno
        assert "consultorio_id" in interno and "punto_venta" in interno
        assert "numero_interno" in interno

        cae = indexes["uq_comprobantes_cae"]
        assert "UNIQUE INDEX" in cae
        assert "cae IS NOT NULL" in cae

        fiscal = indexes["uq_comprobantes_fiscal"]
        assert "UNIQUE INDEX" in fiscal
        assert "numero_fiscal IS NOT NULL" in fiscal

        item = indexes["uq_items_liquidacion_item"]
        assert "UNIQUE INDEX" in item
        assert "item_presupuesto_id" in item
        assert "deleted_at IS NULL" in item

        assert [
            column
            for column in ("estado", "proximo_intento")
            if column in indexes["ix_comprobantes_estado_proximo"]
        ] == ["estado", "proximo_intento"]

        excludes: dict[str, str] = snapshot["excludes"]  # type: ignore[assignment]
        assert "ex_liquidaciones_periodo" in excludes
        definicion = excludes["ex_liquidaciones_periodo"]
        assert "EXCLUDE USING gist" in definicion
        assert "obra_social_id WITH =" in definicion
        assert "daterange(desde, hasta" in definicion
        assert "WITH &&" in definicion
        assert "deleted_at IS NULL" in definicion

    run(scenario())


def test_c14_sql_directo_rechaza_duplicados(session_factory) -> None:
    """Business error: one receipt per payment, one CAE and one fiscal number."""
    data = run(setup_fiscal(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_os_demo"].id

        async def cobro() -> uuid.UUID:
            return await insertar_cobro_db(
                session_factory,
                consultorio_id=consultorio_id,
                paciente_id=paciente_id,
                tipo="otro",
                medio="efectivo",
                estado="aprobado",
                monto="10000.00",
            )

        cobro_uno = await cobro()
        await insertar_comprobante_db(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=cobro_uno,
            paciente_id=paciente_id,
            numero_interno=1,
        )
        # 1) A second receipt for the same payment.
        assert await _sqlstate_comprobante(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=cobro_uno,
            paciente_id=paciente_id,
            numero_interno=2,
        ) == "23505"

        # 2) The same CAE cannot be used twice in the same environment.
        await insertar_comprobante_db(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=await cobro(),
            paciente_id=paciente_id,
            estado="emitido",
            numero_interno=3,
            numero_fiscal=3,
            cae=CAE_PRUEBA,
        )
        assert await _sqlstate_comprobante(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=await cobro(),
            paciente_id=paciente_id,
            estado="emitido",
            numero_interno=4,
            numero_fiscal=4,
            cae=CAE_PRUEBA,
        ) == "23505"

        # 3) Fiscal numbering is unique per environment and point of sale.
        await insertar_comprobante_db(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=await cobro(),
            paciente_id=paciente_id,
            estado="emitido",
            numero_interno=5,
            numero_fiscal=10,
            cae="11111111111111",
        )
        assert await _sqlstate_comprobante(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=await cobro(),
            paciente_id=paciente_id,
            estado="emitido",
            numero_interno=6,
            numero_fiscal=10,
            cae="22222222222222",
        ) == "23505"

        # 4) Internal numbering is unique per consultorio and point of sale.
        assert await _sqlstate_comprobante(
            session_factory,
            consultorio_id=consultorio_id,
            cobro_id=await cobro(),
            paciente_id=paciente_id,
            numero_interno=1,
        ) == "23505"

    run(scenario())


def test_c14_sql_directo_rechaza_importes_y_estado_incoherente(
    session_factory,
) -> None:
    """Business error: D12 CHECKs reject bad money and fiscal incoherence."""
    data = run(setup_fiscal(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_os_demo"].id
        cobro_id = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="otro",
            medio="efectivo",
            estado="aprobado",
            monto="10000.00",
        )

        # Non-positive total.
        for importe in ("0.00", "-1.00"):
            assert await _sqlstate_comprobante(
                session_factory,
                consultorio_id=consultorio_id,
                cobro_id=cobro_id,
                paciente_id=paciente_id,
                importe_total=importe,
            ) == "23514"

        # `emitido` without CAE/number/QR/date is incoherent.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO comprobantes "
            "(id, consultorio_id, cobro_id, paciente_id, tipo, ambiente, "
            "estado, numero_interno, punto_venta, qr_interno, "
            "receptor_nombre, receptor_documento, receptor_tipo_documento, "
            "condicion_fiscal_receptor, condicion_fiscal_emisor, "
            "importe_total, fecha_emision) "
            "VALUES (:id, :consultorio_id, :cobro_id, :paciente_id, 'B', "
            "'homologacion', 'emitido', 20, 1, :qr, 'Demo, Paciente', "
            "'42112001', 'DNI', 'consumidor_final', "
            "'responsable_inscripto', 10000.00, :fecha)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "cobro_id": cobro_id,
                "paciente_id": paciente_id,
                "qr": "https://app.local/comprobantes/verificar?p=e30",
                "fecha": FECHA_FISCAL,
            },
        ) == "23514"

        # A pending receipt cannot carry fiscal fields.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO comprobantes "
            "(id, consultorio_id, cobro_id, paciente_id, tipo, ambiente, "
            "estado, numero_interno, punto_venta, numero_fiscal, cae, "
            "cae_vencimiento, qr_interno, qr_fiscal, receptor_nombre, "
            "receptor_documento, receptor_tipo_documento, "
            "condicion_fiscal_receptor, condicion_fiscal_emisor, "
            "importe_total, fecha_emision, fecha_emision_fiscal) "
            "VALUES (:id, :consultorio_id, :cobro_id, :paciente_id, 'B', "
            "'homologacion', 'pendiente', 21, 1, 21, :cae, :vencimiento, "
            ":qr, :qr, 'Demo, Paciente', '42112001', 'DNI', "
            "'consumidor_final', 'responsable_inscripto', 10000.00, "
            ":fecha, now())",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "cobro_id": cobro_id,
                "paciente_id": paciente_id,
                "cae": CAE_PRUEBA,
                "vencimiento": date(2026, 11, 14),
                "qr": "https://app.local/comprobantes/verificar?p=e30",
                "fecha": FECHA_FISCAL,
            },
        ) == "23514"

        # `fallido` must explain why it failed.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO comprobantes "
            "(id, consultorio_id, cobro_id, paciente_id, tipo, ambiente, "
            "estado, numero_interno, punto_venta, qr_interno, "
            "receptor_nombre, receptor_documento, receptor_tipo_documento, "
            "condicion_fiscal_receptor, condicion_fiscal_emisor, "
            "importe_total, fecha_emision) "
            "VALUES (:id, :consultorio_id, :cobro_id, :paciente_id, 'B', "
            "'homologacion', 'fallido', 22, 1, :qr, 'Demo, Paciente', "
            "'42112001', 'DNI', 'consumidor_final', "
            "'responsable_inscripto', 10000.00, :fecha)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "cobro_id": cobro_id,
                "paciente_id": paciente_id,
                "qr": "https://app.local/comprobantes/verificar?p=e30",
                "fecha": FECHA_FISCAL,
            },
        ) == "23514"

    run(scenario())


def test_c14_sql_directo_rechaza_periodo_solapado(session_factory) -> None:
    """Business error: the GiST exclusion constraint rejects an overlap."""
    data = run(setup_fiscal(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        obra_social_id = data["obra_social_demo_id"]
        creado_por = data["actores"]["administrador"].id

        await insertar_liquidacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            obra_social_id=obra_social_id,
            creado_por=creado_por,
            desde=date(2026, 11, 1),
            hasta=date(2026, 11, 30),
        )
        # An inclusive period that crosses the live one must fail.
        assert await _sqlstate_liquidacion(
            session_factory,
            consultorio_id=consultorio_id,
            obra_social_id=obra_social_id,
            creado_por=creado_por,
            desde=date(2026, 11, 15),
            hasta=date(2026, 12, 5),
        ) == "23P01"

        # Contiguous periods do not overlap: 1 December starts the next one.
        assert await _sqlstate_liquidacion(
            session_factory,
            consultorio_id=consultorio_id,
            obra_social_id=obra_social_id,
            creado_por=creado_por,
            desde=date(2026, 12, 1),
            hasta=date(2026, 12, 31),
        ) is None

    run(scenario())


def test_c14_downgrade_y_upgrade_restaura_solo_sus_tablas(
    migrated_database: str, engine
) -> None:
    """Edge: 0013 ⇄ 0012 is reversible and leaves C-01..C-13 untouched."""

    _alembic(
        "downgrade", "0012_caja_cobros", database_url=migrated_database
    )

    async def after_downgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0012_caja_cobros"
        assert not _TABLAS_FISCALES & set(snapshot["tables"])
        assert {"cobros", "presupuestos", "pacientes"} <= set(
            snapshot["tables"]
        )
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert not _CHECKS_FISCALES & checks
        excludes: dict[str, str] = snapshot["excludes"]  # type: ignore[assignment]
        assert "ex_liquidaciones_periodo" not in excludes

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0014_reportes"
        assert _TABLAS_FISCALES <= set(snapshot["tables"])
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_FISCALES <= checks
        excludes: dict[str, str] = snapshot["excludes"]  # type: ignore[assignment]
        assert "ex_liquidaciones_periodo" in excludes

    run(after_upgrade())
