"""Builders for the C-16 audit viewer tests (fictional data only)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import RegistroAuditoria


async def insertar_auditoria(
    session_factory: async_sessionmaker[AsyncSession],
    filas: list[
        tuple[uuid.UUID, uuid.UUID | None, str, str, str, datetime]
    ],
    *,
    ip: str = "127.0.0.1",
    dispositivo: str = "pytest-auditoria",
) -> None:
    """Insert audit rows with explicit timestamps (the default is `now()`)."""
    async with session_factory() as session, session.begin():
        for fila_id, usuario_id, accion, entidad, entidad_id, momento in filas:
            await session.execute(
                text(
                    "INSERT INTO registro_auditoria "
                    "(id, usuario_id, accion, entidad, entidad_id, ip, "
                    "dispositivo, timestamp) "
                    "VALUES (:id, :usuario_id, :accion, :entidad, :entidad_id, "
                    ":ip, :dispositivo, :momento)"
                ),
                {
                    "id": fila_id,
                    "usuario_id": usuario_id,
                    "accion": accion,
                    "entidad": entidad,
                    "entidad_id": entidad_id,
                    "ip": ip,
                    "dispositivo": dispositivo,
                    "momento": momento,
                },
            )


async def contar_auditoria(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.count()).select_from(RegistroAuditoria)
        )
    return int(total or 0)
