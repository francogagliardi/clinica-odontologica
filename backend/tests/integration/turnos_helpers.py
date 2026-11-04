"""Builders for appointment integration tests (fictional data only)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import Prestacion
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import (
    consultorio_demo_id,
    create_actor,
    create_profesional,
    create_sillon,
    seed_demo,
)

ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
FECHA_LUNES = date(2026, 11, 9)
INICIO = datetime(2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET)


async def prestacion_id(
    session_factory: async_sessionmaker[AsyncSession], codigo: str
) -> uuid.UUID:
    async with session_factory() as session:
        value = await session.scalar(
            select(Prestacion.id).where(Prestacion.codigo == codigo)
        )
    assert value is not None
    return value


def turno_payload(
    *,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    prestacion_id: uuid.UUID | None = None,
    inicio: datetime = INICIO,
    **overrides: Any,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "paciente_id": str(paciente_id),
        "profesional_id": str(profesional_id),
        "sillon_id": str(sillon_id),
        "prestacion_id": str(prestacion_id) if prestacion_id else None,
        "inicio": (
            inicio.isoformat() if hasattr(inicio, "isoformat") else str(inicio)
        ),
        "origen": "recepcion",
        "es_sobreturno": False,
        "color_sobreturno": None,
    }
    payload.update(overrides)
    return payload


async def setup_turnos(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Seed demo data, actors and the minimum agenda resources for C-06."""
    await seed_demo(session_factory)
    consultorio_id = await consultorio_demo_id(session_factory)
    actores = {
        rol: await create_actor(session_factory, rol) for rol in ROLES
    }
    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-TURNOS-1",
        usuario_id=actores["odontologo"].id,
    )
    sillon = await create_sillon(session_factory, consultorio_id, "Sillon A")
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Turno",
        apellido="Demo",
        dni="42000111",
        telefono="+5491177770001",
    )
    return {
        "consultorio_id": consultorio_id,
        "actores": actores,
        "profesional": profesional,
        "sillon": sillon,
        "paciente": paciente,
    }


def iso(value: datetime) -> str:
    return value.isoformat()


async def insertar_turno_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    sillon_id: uuid.UUID,
    inicio: datetime,
    fin: datetime,
    estado: str = "reservado",
) -> uuid.UUID:
    """Direct insert used to set up conflicts without going through the API."""
    from sqlalchemy import text

    turno_id = uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO turnos "
                "(id, consultorio_id, paciente_id, profesional_id, "
                "sillon_id, inicio, fin, estado) "
                "VALUES (:id, :consultorio_id, :paciente_id, "
                ":profesional_id, :sillon_id, :inicio, :fin, :estado)"
            ),
            {
                "id": turno_id,
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "profesional_id": profesional_id,
                "sillon_id": sillon_id,
                "inicio": inicio,
                "fin": fin,
                "estado": estado,
            },
        )
    return turno_id
