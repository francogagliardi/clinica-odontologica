"""Builders for budget integration tests (fictional data only)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ObraSocial, Prestacion
from tests.integration.clinica_helpers import setup_clinica
from tests.integration.pacientes_helpers import create_paciente

# The spec scenario uses 10.000,00 for CONS, so the tests pin that catalogue
# price instead of the seed default (the snapshot is what matters here).
PRECIOS_TEST = {
    "CONS": Decimal("10000.00"),
    "OBT": Decimal("25000.00"),
    "EXO": Decimal("30000.00"),
}


async def cargar_prestaciones(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Prestacion]:
    """Active catalogue keyed by code, with the test prices applied."""
    async with session_factory() as session, session.begin():
        for codigo, precio in PRECIOS_TEST.items():
            await session.execute(
                update(Prestacion)
                .where(
                    Prestacion.codigo == codigo,
                    Prestacion.deleted_at.is_(None),
                )
                .values(precio_base=precio)
            )
        result = await session.scalars(
            select(Prestacion).where(Prestacion.deleted_at.is_(None))
        )
        return {prestacion.codigo: prestacion for prestacion in result}


async def crear_convenio(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    *,
    nombre: str,
    reglas_cobertura: dict[str, object],
    activo: bool = True,
) -> ObraSocial:
    """Agreement with the exact local rules the coverage matrix needs."""
    async with session_factory() as session, session.begin():
        obra = ObraSocial(
            id=uuid.uuid4(),
            consultorio_id=consultorio_id,
            nombre=nombre,
            reglas_cobertura=reglas_cobertura,
        )
        if not activo:
            obra.soft_delete()
        session.add(obra)
    return obra


async def desactivar_convenio(
    session_factory: async_sessionmaker[AsyncSession], obra_social_id: uuid.UUID
) -> None:
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE obras_sociales "
                "SET is_active = false, deleted_at = now() WHERE id = :id"
            ),
            {"id": obra_social_id},
        )


async def cambiar_precio_prestacion(
    session_factory: async_sessionmaker[AsyncSession],
    prestacion_id: uuid.UUID,
    precio: Decimal,
) -> None:
    """Move the catalogue price; existing budgets must keep their snapshot."""
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Prestacion)
            .where(Prestacion.id == prestacion_id)
            .values(precio_base=precio)
        )


async def actualizar_reglas_cobertura(
    session_factory: async_sessionmaker[AsyncSession],
    obra_social_id: uuid.UUID,
    reglas: dict[str, object],
) -> None:
    """Correct a convention after a budget was stored as pending."""
    async with session_factory() as session, session.begin():
        obra = await session.get(ObraSocial, obra_social_id)
        assert obra is not None
        obra.reglas_cobertura = reglas


async def setup_presupuestos(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Clinical fixtures plus the coverage variants the budget needs."""
    data = await setup_clinica(session_factory)
    consultorio_id = data["consultorio_id"]
    prestaciones = await cargar_prestaciones(session_factory)

    async with session_factory() as session:
        os_demo_id = await session.scalar(
            select(ObraSocial.id).where(
                ObraSocial.nombre == "OS Demo",
                ObraSocial.deleted_at.is_(None),
            )
        )
    assert os_demo_id is not None

    paciente_os_demo = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Cobertura",
        apellido="Demo",
        dni="42112001",
        telefono="+5491177770201",
        obra_social_id=os_demo_id,
        nro_afiliado="DEMO-1201",
    )

    sin_porcentaje = await crear_convenio(
        session_factory,
        consultorio_id,
        nombre="OS Sin Porcentaje",
        reglas_cobertura={"prestaciones_cubiertas": ["CONS"]},
    )
    paciente_sin_porcentaje = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Pendiente",
        apellido="SinPorcentaje",
        dni="42112002",
        telefono="+5491177770202",
        obra_social_id=sin_porcentaje.id,
        nro_afiliado="SP-1202",
    )

    inactiva = await crear_convenio(
        session_factory,
        consultorio_id,
        nombre="OS Inactiva",
        reglas_cobertura={
            "cobertura_porcentaje": 60,
            "prestaciones_cubiertas": ["CONS"],
        },
        activo=False,
    )
    paciente_convenio_inactivo = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Pendiente",
        apellido="Inactiva",
        dni="42112003",
        telefono="+5491177770203",
        obra_social_id=inactiva.id,
        nro_afiliado="IN-1203",
    )

    return {
        **data,
        "prestaciones": prestaciones,
        "paciente_os_demo": paciente_os_demo,
        "paciente_sin_porcentaje": paciente_sin_porcentaje,
        "paciente_convenio_inactivo": paciente_convenio_inactivo,
        "obra_social_demo_id": os_demo_id,
        "obra_social_sin_porcentaje_id": sin_porcentaje.id,
        "obra_social_inactiva_id": inactiva.id,
    }


async def insertar_presupuesto_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    creado_por: uuid.UUID,
    estado: str = "borrador",
    cobertura_estado: str = "calculada",
    subtotal: str = "10000.00",
    cobertura_calculada: str = "6000.00",
    copago: str = "4000.00",
    creado_en: datetime | None = None,
    presupuesto_id: uuid.UUID | None = None,
) -> uuid.UUID:
    presupuesto_id = presupuesto_id or uuid.uuid4()
    columnas = (
        "id, consultorio_id, paciente_id, profesional_id, "
        "creado_por, estado, cobertura_estado, subtotal, "
        "cobertura_calculada, copago"
    )
    valores = (
        ":id, :consultorio_id, :paciente_id, :profesional_id, "
        ":creado_por, :estado, :cobertura_estado, :subtotal, "
        ":cobertura_calculada, :copago"
    )
    parametros: dict[str, object] = {
        "id": presupuesto_id,
        "consultorio_id": consultorio_id,
        "paciente_id": paciente_id,
        "profesional_id": profesional_id,
        "creado_por": creado_por,
        "estado": estado,
        "cobertura_estado": cobertura_estado,
        "subtotal": subtotal,
        "cobertura_calculada": cobertura_calculada,
        "copago": copago,
    }
    if creado_en is not None:
        columnas += ", created_at"
        valores += ", :creado_en"
        parametros["creado_en"] = creado_en
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                f"INSERT INTO presupuestos ({columnas}) "
                f"VALUES ({valores})"
            ),
            parametros,
        )
    return presupuesto_id


async def insertar_item_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    presupuesto_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    pieza: int | None = None,
    cantidad: int = 1,
    precio_unitario: str = "10000.00",
    cobertura_item: str = "6000.00",
    copago_item: str = "4000.00",
    item_id: uuid.UUID | None = None,
) -> uuid.UUID:
    item_id = item_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO items_presupuesto "
                "(id, presupuesto_id, prestacion_id, pieza, cantidad, "
                "precio_unitario, cobertura_item, copago_item) "
                "VALUES (:id, :presupuesto_id, :prestacion_id, :pieza, "
                ":cantidad, :precio_unitario, :cobertura_item, :copago_item)"
            ),
            {
                "id": item_id,
                "presupuesto_id": presupuesto_id,
                "prestacion_id": prestacion_id,
                "pieza": pieza,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "cobertura_item": cobertura_item,
                "copago_item": copago_item,
            },
        )
    return item_id
