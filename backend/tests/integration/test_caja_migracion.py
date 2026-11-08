"""C-13 `0012_caja_cobros`: DDL, partial unique indexes and SQL rejects."""

import os
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Base
from tests.integration.caja_helpers import (
    FECHA_CAJA,
    insertar_cobro_db,
    insertar_movimiento_db,
    setup_caja,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.presupuestos_helpers import insertar_presupuesto_db

BACKEND_DIR = Path(__file__).resolve().parents[2]

_TABLAS_CAJA = {"cobros", "cajas_diarias", "movimientos_caja"}
_CHECKS_CAJA = {
    "ck_cobros_baja_logica_coherente",
    "ck_cobros_tipo_valido",
    "ck_cobros_medio_valido",
    "ck_cobros_estado_valido",
    "ck_cobros_monto_positivo",
    "ck_cobros_referencias_coherentes",
    "ck_cobros_efectivo_no_pendiente",
    "ck_cobros_proveedor_pago_solo_mp",
    "ck_cajas_diarias_baja_logica_coherente",
    "ck_cajas_diarias_estado_valido",
    "ck_cajas_diarias_monto_apertura_no_negativo",
    "ck_cajas_diarias_cierre_coherente",
    "ck_movimientos_caja_baja_logica_coherente",
    "ck_movimientos_caja_tipo_valido",
    "ck_movimientos_caja_medio_valido",
    "ck_movimientos_caja_monto_positivo",
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
        version = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
    return {
        "tables": tables,
        "checks": checks,
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


def test_c13_upgrade_crea_tablas_checks_e_indices(engine) -> None:
    """Expected: the three C-13 tables with D7/D9 objects exist at head."""

    async def scenario() -> None:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0013_facturacion_arca"
        assert _TABLAS_CAJA <= set(snapshot["tables"])
        assert _TABLAS_CAJA <= set(Base.metadata.tables)
        assert snapshot["tables"] == set(Base.metadata.tables) | {
            "alembic_version"
        }

        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_CAJA <= checks

        indexes: dict[str, str] = snapshot["indexes"]  # type: ignore[assignment]
        assert {
            "ix_cobros_paciente_fecha",
            "ix_cobros_turno",
            "ix_cobros_presupuesto",
            "ix_cobros_estado",
            "ix_movimientos_caja_caja",
        } <= set(indexes)

        proveedor = indexes["uq_cobros_proveedor_pago"]
        assert "UNIQUE INDEX" in proveedor
        assert "proveedor_pago_id IS NOT NULL" in proveedor

        sena = indexes["uq_cobros_sena_turno"]
        assert "UNIQUE INDEX" in sena
        assert "turno_id" in sena
        assert "tipo" in sena and "'sena'" in sena
        assert "pendiente" in sena and "aprobado" in sena and "perdido" in sena

        movimiento = indexes["uq_movimientos_caja_cobro"]
        assert "UNIQUE INDEX" in movimiento
        assert "cobro_id IS NOT NULL" in movimiento

        caja = indexes["uq_cajas_diarias_consultorio_fecha"]
        assert "UNIQUE INDEX" in caja
        assert "consultorio_id" in caja and "fecha" in caja

    run(scenario())


def test_c13_sql_directo_rechaza_duplicados(session_factory) -> None:
    """Business error: PostgreSQL enforces the three partial unique indexes."""
    data = run(setup_caja(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_propio"].id
        turno_id = data["turnos"]["propio"]

        sena_id = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="sena",
            medio="mercadopago",
            estado="pendiente",
            monto="8000.00",
            turno_id=turno_id,
        )
        # 1) A second live deposit for the same appointment.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO cobros "
            "(id, consultorio_id, paciente_id, turno_id, tipo, medio, "
            "estado, monto, fecha_operacion) "
            "VALUES (:id, :consultorio_id, :paciente_id, :turno_id, 'sena', "
            "'mercadopago', 'pendiente', 8000.00, :fecha)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "turno_id": turno_id,
                "fecha": FECHA_CAJA,
            },
        ) == "23505"

        # A rejected deposit does not block a new attempt (index predicate).
        rechazada = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="sena",
            medio="mercadopago",
            estado="rechazado",
            monto="8000.00",
            turno_id=turno_id,
        )
        assert rechazada != sena_id

        # 2) The same provider payment id cannot be reconciled twice.
        proveedor_id = "mp-pago-0001"
        await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="otro",
            medio="mercadopago",
            estado="aprobado",
            monto="15000.00",
            proveedor_pago_id=proveedor_id,
        )
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO cobros "
            "(id, consultorio_id, paciente_id, tipo, medio, estado, monto, "
            "proveedor_pago_id, fecha_operacion) "
            "VALUES (:id, :consultorio_id, :paciente_id, 'otro', "
            "'mercadopago', 'aprobado', 15000.00, :proveedor_pago_id, "
            ":fecha)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "proveedor_pago_id": proveedor_id,
                "fecha": FECHA_CAJA,
            },
        ) == "23505"

        # 3) A payment can produce only one cash movement.
        cobro_id = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            tipo="otro",
            medio="efectivo",
            estado="aprobado",
            monto="12000.00",
        )
        await insertar_movimiento_db(
            session_factory,
            caja_id=data["caja_id"],
            monto="12000.00",
            cobro_id=cobro_id,
        )
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO movimientos_caja "
            "(id, caja_id, tipo, concepto, monto, medio, cobro_id) "
            "VALUES (:id, :caja_id, 'ingreso', 'duplicado', 12000.00, "
            "'efectivo', :cobro_id)",
            {
                "id": uuid.uuid4(),
                "caja_id": data["caja_id"],
                "cobro_id": cobro_id,
            },
        ) == "23505"

    run(scenario())


def test_c13_sql_directo_rechaza_montos_y_referencias(
    session_factory,
) -> None:
    """Business error: D9 CHECKs reject non-positive money and bad references."""
    data = run(setup_caja(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        paciente_id = data["paciente_propio"].id
        turno_id = data["turnos"]["propio"]
        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=data["profesional"].id,
            creado_por=data["actores"]["odontologo"].id,
            estado="aceptado",
        )

        # monto <= 0 (all other rules are coherent, so only this CHECK trips).
        for monto in ("0.00", "-1.00"):
            assert await _sqlstate_de(
                session_factory,
                "INSERT INTO cobros "
                "(id, consultorio_id, paciente_id, tipo, medio, estado, "
                "monto, fecha_operacion) "
                "VALUES (:id, :consultorio_id, :paciente_id, 'otro', "
                "'efectivo', 'aprobado', :monto, :fecha)",
                {
                    "id": uuid.uuid4(),
                    "consultorio_id": consultorio_id,
                    "paciente_id": paciente_id,
                    "monto": monto,
                    "fecha": FECHA_CAJA,
                },
            ) == "23514"

        # Invalid type/reference combinations.
        invalidas = (
            # sena with both references
            (
                "sena",
                turno_id,
                presupuesto_id,
            ),
            # tratamiento pointing to a turn instead of a budget
            (
                "tratamiento",
                turno_id,
                None,
            ),
            # otro with a turn
            (
                "otro",
                turno_id,
                None,
            ),
        )
        for tipo, turno, presupuesto in invalidas:
            assert await _sqlstate_de(
                session_factory,
                "INSERT INTO cobros "
                "(id, consultorio_id, paciente_id, turno_id, presupuesto_id, "
                "tipo, medio, estado, monto, fecha_operacion) "
                "VALUES (:id, :consultorio_id, :paciente_id, :turno_id, "
                ":presupuesto_id, :tipo, 'efectivo', 'aprobado', 1000.00, "
                ":fecha)",
                {
                    "id": uuid.uuid4(),
                    "consultorio_id": consultorio_id,
                    "paciente_id": paciente_id,
                    "turno_id": turno,
                    "presupuesto_id": presupuesto,
                    "tipo": tipo,
                    "fecha": FECHA_CAJA,
                },
            ) == "23514"

        # Cash can never be pending and a provider id requires Mercado Pago.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO cobros "
            "(id, consultorio_id, paciente_id, tipo, medio, estado, monto, "
            "fecha_operacion) "
            "VALUES (:id, :consultorio_id, :paciente_id, 'otro', "
            "'efectivo', 'pendiente', 1000.00, :fecha)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "fecha": FECHA_CAJA,
            },
        ) == "23514"
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO cobros "
            "(id, consultorio_id, paciente_id, tipo, medio, estado, monto, "
            "proveedor_pago_id, fecha_operacion) "
            "VALUES (:id, :consultorio_id, :paciente_id, 'otro', "
            "'efectivo', 'aprobado', 1000.00, 'mp-x', :fecha)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "fecha": FECHA_CAJA,
            },
        ) == "23514"

        # Register coherence: negative opening and a closed row without snapshot.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO cajas_diarias "
            "(id, consultorio_id, fecha, estado, monto_apertura) "
            "VALUES (:id, :consultorio_id, :fecha, 'abierta', -1.00)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "fecha": date(2026, 11, 5),
            },
        ) == "23514"
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO cajas_diarias "
            "(id, consultorio_id, fecha, estado, monto_apertura) "
            "VALUES (:id, :consultorio_id, :fecha, 'cerrada', 0.00)",
            {
                "id": uuid.uuid4(),
                "consultorio_id": consultorio_id,
                "fecha": date(2026, 11, 6),
            },
        ) == "23514"

        # Movement money is positive too.
        assert await _sqlstate_de(
            session_factory,
            "INSERT INTO movimientos_caja "
            "(id, caja_id, tipo, concepto, monto, medio) "
            "VALUES (:id, :caja_id, 'gasto', 'insumos', 0.00, 'efectivo')",
            {"id": uuid.uuid4(), "caja_id": data["caja_id"]},
        ) == "23514"

    run(scenario())


def test_c13_downgrade_y_upgrade_restaura_solo_sus_tablas(
    migrated_database: str, engine
) -> None:
    """Edge: 0012 ⇄ 0011 is reversible and leaves C-01..C-12 untouched."""

    _alembic(
        "downgrade", "0011_presupuestos", database_url=migrated_database
    )

    async def after_downgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0011_presupuestos"
        assert not _TABLAS_CAJA & set(snapshot["tables"])
        assert {"pacientes", "turnos", "presupuestos"} <= set(
            snapshot["tables"]
        )
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert not _CHECKS_CAJA & checks
        return snapshot

    run(after_downgrade())

    _alembic("upgrade", "head", database_url=migrated_database)

    async def after_upgrade() -> dict[str, object]:
        snapshot = await _snapshot(engine)
        assert snapshot["version"] == "0013_facturacion_arca"
        assert _TABLAS_CAJA <= set(snapshot["tables"])
        checks: set[str] = snapshot["checks"]  # type: ignore[assignment]
        assert _CHECKS_CAJA <= checks
        return snapshot

    run(after_upgrade())
