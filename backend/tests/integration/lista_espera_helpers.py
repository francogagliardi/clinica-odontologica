"""Builders for waiting-list retention tests (fictional data only).

C-10 slice 2/3 will add the `/lista-espera` CRUD; until then these helpers
insert entries directly to exercise the retention, availability and 409 rules.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import EntradaListaEspera


async def insertar_entrada(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    estado: str = "pendiente",
    profesional_id: uuid.UUID | None = None,
    oferta_profesional_id: uuid.UUID | None = None,
    oferta_sillon_id: uuid.UUID | None = None,
    oferta_inicio: datetime | None = None,
    oferta_fin: datetime | None = None,
    oferta_expira_en: datetime | None = None,
    turno_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Direct insert (bypasses the API) for a given state of the entry."""
    entrada = EntradaListaEspera(
        id=uuid.uuid4(),
        consultorio_id=consultorio_id,
        paciente_id=paciente_id,
        prestacion_id=prestacion_id,
        profesional_id=profesional_id,
        estado=estado,
        oferta_profesional_id=oferta_profesional_id,
        oferta_sillon_id=oferta_sillon_id,
        oferta_inicio=oferta_inicio,
        oferta_fin=oferta_fin,
        oferta_expira_en=oferta_expira_en,
        turno_id=turno_id,
    )
    async with session_factory() as session, session.begin():
        session.add(entrada)
        await session.flush()
    return entrada.id


async def convertir_entrada(
    session_factory: async_sessionmaker[AsyncSession],
    entrada_id: uuid.UUID,
    turno_id: uuid.UUID,
) -> None:
    """Simulate the acceptance: `convertido` with its turn and no retention."""
    async with session_factory() as session, session.begin():
        entrada = await session.get(EntradaListaEspera, entrada_id)
        assert entrada is not None
        entrada.estado = "convertido"
        entrada.turno_id = turno_id
        entrada.oferta_profesional_id = None
        entrada.oferta_sillon_id = None
        entrada.oferta_inicio = None
        entrada.oferta_fin = None
        entrada.oferta_expira_en = None
        await session.flush()


async def vencer_entrada(
    session_factory: async_sessionmaker[AsyncSession],
    entrada_id: uuid.UUID,
) -> None:
    """Simulate the expiry sweep: `vencido` and retention released."""
    async with session_factory() as session, session.begin():
        entrada = await session.get(EntradaListaEspera, entrada_id)
        assert entrada is not None
        entrada.estado = "vencido"
        entrada.oferta_profesional_id = None
        entrada.oferta_sillon_id = None
        entrada.oferta_inicio = None
        entrada.oferta_fin = None
        entrada.oferta_expira_en = None
        await session.flush()


async def contar_estado(
    session_factory: async_sessionmaker[AsyncSession], estado: str
) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count())
            .select_from(EntradaListaEspera)
            .where(EntradaListaEspera.estado == estado)
        )
