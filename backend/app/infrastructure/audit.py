"""Audit helper: write-only by construction (RN-SE-02).

There is no update/delete function in this module on purpose. PostgreSQL
triggers reject such statements even if someone writes raw SQL.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegistroAuditoria


async def registrar(
    session: AsyncSession,
    *,
    accion: str,
    entidad: str,
    entidad_id: str | uuid.UUID,
    usuario_id: uuid.UUID | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> RegistroAuditoria:
    """Append one audit row inside the caller's transaction."""
    registro = RegistroAuditoria(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id),
        ip=ip,
        dispositivo=dispositivo,
    )
    session.add(registro)
    await session.flush()
    return registro
