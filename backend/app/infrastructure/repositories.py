"""Generic repository: reads/writes only, never commits (R-04).

Transaction boundaries belong to `UnitOfWork`. There is deliberately no
physical-delete operation: business entities are soft-deleted only.
"""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Base,
    Consultorio,
    RegistroAuditoria,
    Rol,
    Usuario,
)
from app.models.base import AuditMixin

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Typed CRUD over one model, bound to an injected session."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity: T) -> T:
        """Persist a new entity inside the caller's transaction."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def get(self, entity_id: uuid.UUID) -> T | None:
        """Return the entity or None; 404 decisions belong to the API layer."""
        return await self._session.get(self.model, entity_id)

    async def list(self, include_inactive: bool = False) -> list[T]:
        """List entities, hiding soft-deleted rows unless explicitly asked."""
        statement = select(self.model)
        if not include_inactive and issubclass(self.model, AuditMixin):
            statement = statement.where(self.model.deleted_at.is_(None))
        result = await self._session.scalars(statement)
        return list(result)

    async def soft_delete(self, entity: T) -> T:
        """Soft delete only (idempotent); physical delete is not exposed."""
        if not isinstance(entity, AuditMixin):
            raise TypeError(
                f"{type(entity).__name__} no admite baja lógica "
                "(no hereda AuditMixin)"
            )
        entity.soft_delete()
        await self._session.flush()
        return entity


class ConsultorioRepository(BaseRepository[Consultorio]):
    model = Consultorio


class RolRepository(BaseRepository[Rol]):
    model = Rol


class UsuarioRepository(BaseRepository[Usuario]):
    model = Usuario

    async def get_by_email(
        self, email: str, include_inactive: bool = False
    ) -> Usuario | None:
        """Find a user by email, case-insensitively, optionally including bajas.

        The comparison is done on `lower(email)` so login does not depend on how
        the address was typed. A duplicate differing only in case is prevented
        by normalizing the address on the write path (seed/alta).
        """
        statement = select(Usuario).where(
            func.lower(Usuario.email) == email.strip().lower()
        )
        if not include_inactive:
            statement = statement.where(Usuario.deleted_at.is_(None))
        result = await self._session.scalars(statement)
        return result.first()


class AuditoriaRepository:
    """Append-only access: add/get/list. No update, no delete, no soft delete."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, registro: RegistroAuditoria) -> RegistroAuditoria:
        self._session.add(registro)
        await self._session.flush()
        return registro

    async def get(self, entity_id: uuid.UUID) -> RegistroAuditoria | None:
        return await self._session.get(RegistroAuditoria, entity_id)

    async def list(self) -> list[RegistroAuditoria]:
        result = await self._session.scalars(select(RegistroAuditoria))
        return list(result)
