"""Builders for cash-register and payment integration tests (fictional data)."""

import uuid
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.clinica_helpers import setup_clinica

FECHA_CAJA = date(2026, 11, 4)


async def setup_caja(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Clinical fixtures plus the demo register used by the repository tests."""
    data = await setup_clinica(session_factory)
    caja_id = await insertar_caja_db(
        session_factory,
        consultorio_id=data["consultorio_id"],
        fecha=FECHA_CAJA,
        monto_apertura="10000.00",
    )
    return {**data, "caja_id": caja_id, "fecha": FECHA_CAJA}


async def insertar_caja_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    fecha: date = FECHA_CAJA,
    estado: str = "abierta",
    monto_apertura: str = "10000.00",
    monto_sistema_efectivo: str | None = None,
    monto_contado: str | None = None,
    diferencia: str | None = None,
    cerrada_por: uuid.UUID | None = None,
    cerrada_at: datetime | None = None,
    observaciones: str | None = None,
    caja_id: uuid.UUID | None = None,
) -> uuid.UUID:
    caja_id = caja_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO cajas_diarias "
                "(id, consultorio_id, fecha, estado, monto_apertura, "
                "monto_sistema_efectivo, monto_contado, diferencia, "
                "cerrada_por, cerrada_at, observaciones) "
                "VALUES (:id, :consultorio_id, :fecha, :estado, "
                ":monto_apertura, :monto_sistema_efectivo, :monto_contado, "
                ":diferencia, :cerrada_por, :cerrada_at, :observaciones)"
            ),
            {
                "id": caja_id,
                "consultorio_id": consultorio_id,
                "fecha": fecha,
                "estado": estado,
                "monto_apertura": monto_apertura,
                "monto_sistema_efectivo": monto_sistema_efectivo,
                "monto_contado": monto_contado,
                "diferencia": diferencia,
                "cerrada_por": cerrada_por,
                "cerrada_at": cerrada_at,
                "observaciones": observaciones,
            },
        )
    return caja_id


async def insertar_cobro_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    tipo: str,
    medio: str = "efectivo",
    estado: str = "aprobado",
    monto: str = "15000.00",
    turno_id: uuid.UUID | None = None,
    presupuesto_id: uuid.UUID | None = None,
    creado_por: uuid.UUID | None = None,
    proveedor_pago_id: str | None = None,
    proveedor_preferencia_id: str | None = None,
    link_pago: str | None = None,
    fecha_operacion: date = FECHA_CAJA,
    fecha_conciliacion: datetime | None = None,
    cobro_id: uuid.UUID | None = None,
) -> uuid.UUID:
    cobro_id = cobro_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO cobros "
                "(id, consultorio_id, paciente_id, turno_id, presupuesto_id, "
                "creado_por, tipo, medio, estado, monto, proveedor_pago_id, "
                "proveedor_preferencia_id, link_pago, fecha_operacion, "
                "fecha_conciliacion) "
                "VALUES (:id, :consultorio_id, :paciente_id, :turno_id, "
                ":presupuesto_id, :creado_por, :tipo, :medio, :estado, "
                ":monto, :proveedor_pago_id, :proveedor_preferencia_id, "
                ":link_pago, :fecha_operacion, :fecha_conciliacion)"
            ),
            {
                "id": cobro_id,
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "turno_id": turno_id,
                "presupuesto_id": presupuesto_id,
                "creado_por": creado_por,
                "tipo": tipo,
                "medio": medio,
                "estado": estado,
                "monto": monto,
                "proveedor_pago_id": proveedor_pago_id,
                "proveedor_preferencia_id": proveedor_preferencia_id,
                "link_pago": link_pago,
                "fecha_operacion": fecha_operacion,
                "fecha_conciliacion": fecha_conciliacion,
            },
        )
    return cobro_id


async def insertar_movimiento_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    caja_id: uuid.UUID,
    tipo: str = "ingreso",
    concepto: str = "Cobro de prueba",
    monto: str = "15000.00",
    medio: str = "efectivo",
    cobro_id: uuid.UUID | None = None,
    creado_por: uuid.UUID | None = None,
    movimiento_id: uuid.UUID | None = None,
) -> uuid.UUID:
    movimiento_id = movimiento_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO movimientos_caja "
                "(id, caja_id, tipo, concepto, monto, medio, cobro_id, "
                "creado_por) "
                "VALUES (:id, :caja_id, :tipo, :concepto, :monto, :medio, "
                ":cobro_id, :creado_por)"
            ),
            {
                "id": movimiento_id,
                "caja_id": caja_id,
                "tipo": tipo,
                "concepto": concepto,
                "monto": monto,
                "medio": medio,
                "cobro_id": cobro_id,
                "creado_por": creado_por,
            },
        )
    return movimiento_id
