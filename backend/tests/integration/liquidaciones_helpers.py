"""Builders for coverage and settlement integration tests (fictional data)."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Cobro,
    ItemLiquidacion,
    ItemPresupuesto,
    LiquidacionObraSocial,
)
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.presupuestos_helpers import (
    insertar_item_db,
    insertar_presupuesto_db,
    setup_presupuestos,
)
from tests.integration.recursos_helpers import bearer

FECHA_LIQ = date(2026, 11, 4)
DESDE_LIQ = date(2026, 11, 1)
HASTA_LIQ = date(2026, 11, 30)


async def setup_liquidaciones(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    data = await setup_presupuestos(session_factory)
    return {
        **data,
        "fecha_liq": FECHA_LIQ,
        "desde": DESDE_LIQ,
        "hasta": HASTA_LIQ,
    }


async def crear_paciente_os(
    session_factory: async_sessionmaker[AsyncSession],
    data: dict[str, object],
    *,
    obra_social_id: uuid.UUID | None = None,
    nro_afiliado: str | None = "AF-9001",
) -> object:
    obra = obra_social_id or data["obra_social_demo_id"]
    return await create_paciente(
        session_factory,
        data["consultorio_id"],
        nombre="Cobertura",
        apellido=f"Liq {uuid.uuid4().hex[:5]}",
        dni=f"4{uuid.uuid4().int % 10_000_000:07d}",
        telefono="+5491177770901",
        obra_social_id=obra,
        nro_afiliado=nro_afiliado,
    )


async def crear_escenario(
    session_factory: async_sessionmaker[AsyncSession],
    data: dict[str, object],
    *,
    estado: str = "aceptado",
    paciente_id: uuid.UUID | None = None,
    prestacion: str = "CONS",
    cobertura_item: str = "6000.00",
    copago_item: str = "4000.00",
    cantidad: int = 1,
    pieza: int | None = None,
    con_cobro: bool = True,
    fecha_cobro: date = FECHA_LIQ,
    estado_cobro: str = "aprobado",
    monto_cobro: str | None = None,
) -> dict[str, object]:
    """Create a budget with one line and, optionally, its treatment payment."""
    consultorio_id = data["consultorio_id"]
    paciente = paciente_id or data["paciente_os_demo"].id
    prestacion_model = data["prestaciones"][prestacion]
    cobertura = f"{float(cobertura_item):.2f}"
    copago = f"{float(copago_item):.2f}"
    subtotal = f"{float(cobertura_item) + float(copago_item):.2f}"

    presupuesto_id = await insertar_presupuesto_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente,
        profesional_id=data["profesional"].id,
        creado_por=data["actores"]["administrador"].id,
        estado=estado,
        subtotal=subtotal,
        cobertura_calculada=cobertura,
        copago=copago,
    )
    item_id = await insertar_item_db(
        session_factory,
        presupuesto_id=presupuesto_id,
        prestacion_id=prestacion_model.id,
        pieza=pieza,
        cantidad=cantidad,
        precio_unitario=str(prestacion_model.precio_base),
        cobertura_item=cobertura,
        copago_item=copago,
    )

    cobro_id = None
    if con_cobro:
        cobro_id = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente,
            tipo="tratamiento",
            medio="efectivo",
            estado=estado_cobro,
            monto=monto_cobro or subtotal,
            presupuesto_id=presupuesto_id,
            fecha_operacion=fecha_cobro,
        )
    return {
        "presupuesto_id": presupuesto_id,
        "item_id": item_id,
        "cobro_id": cobro_id,
        "paciente_id": paciente,
        "prestacion_id": prestacion_model.id,
        "cobertura_item": cobertura,
        "subtotal": subtotal,
    }


def post_liquidacion(
    api_client,
    data: dict[str, object],
    *,
    desde: date | None = None,
    hasta: date | None = None,
    obra_social_id: uuid.UUID | None = None,
    actor: str = "administrador",
    observaciones: str | None = None,
    **overrides: object,
):
    payload: dict[str, object] = {
        "obra_social_id": str(
            obra_social_id or data["obra_social_demo_id"]
        ),
        "desde": (desde or data["desde"]).isoformat(),
        "hasta": (hasta or data["hasta"]).isoformat(),
    }
    if observaciones is not None:
        payload["observaciones"] = observaciones
    payload.update(overrides)
    return api_client.post(
        "/obras-sociales/liquidaciones",
        json=payload,
        headers={
            **bearer(data["actores"][actor]),
            "User-Agent": "pytest-ua-c14-liq",
        },
    )


def get_cobertura(
    api_client,
    data: dict[str, object],
    *,
    paciente_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    actor: str = "recepcionista",
):
    return api_client.get(
        "/obras-sociales/cobertura",
        params={
            "paciente_id": str(paciente_id),
            "prestacion_id": str(prestacion_id),
        },
        headers=bearer(data["actores"][actor]),
    )


async def leer_liquidacion(
    session_factory: async_sessionmaker[AsyncSession],
    liquidacion_id: uuid.UUID,
) -> LiquidacionObraSocial | None:
    async with session_factory() as session:
        return await session.get(LiquidacionObraSocial, liquidacion_id)


async def items_de(
    session_factory: async_sessionmaker[AsyncSession],
    liquidacion_id: uuid.UUID,
) -> list[ItemLiquidacion]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(ItemLiquidacion)
                .where(ItemLiquidacion.liquidacion_id == liquidacion_id)
                .order_by(ItemLiquidacion.created_at, ItemLiquidacion.id)
            )
        )


async def contar_liquidaciones(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(LiquidacionObraSocial)
            )
            or 0
        )


async def contar_tablas_mutables(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Row counts used to prove a read-only validation wrote nothing."""

    async def contar(model) -> int:
        async with session_factory() as session:
            return int(
                await session.scalar(select(func.count()).select_from(model))
                or 0
            )

    return {
        "cobros": await contar(Cobro),
        "items_presupuesto": await contar(ItemPresupuesto),
        "items_liquidacion": await contar(ItemLiquidacion),
        "liquidaciones": await contar(LiquidacionObraSocial),
    }
