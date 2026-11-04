"""Generic repository: reads/writes only, never commits (R-04).

Transaction boundaries belong to `UnitOfWork`. There is deliberately no
physical-delete operation: business entities are soft-deleted only.
"""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.turnos import ESTADOS_ACTIVOS
from app.models import (
    Base,
    Bloqueo,
    Consultorio,
    ObraSocial,
    Paciente,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    RegistroAuditoria,
    Rol,
    Sillon,
    Turno,
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

    async def get_by_slug(
        self, slug: str, include_inactive: bool = False
    ) -> Consultorio | None:
        """Resolve a consultorio by its stable slug (demo tenant in v1)."""
        statement = select(Consultorio).where(Consultorio.slug == slug)
        if not include_inactive:
            statement = statement.where(Consultorio.deleted_at.is_(None))
        result = await self._session.scalars(statement)
        return result.first()


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


class ProfesionalRepository(BaseRepository[Profesional]):
    model = Profesional

    async def get_by_matricula(
        self,
        consultorio_id: uuid.UUID,
        matricula: str,
        exclude_id: uuid.UUID | None = None,
    ) -> Profesional | None:
        statement = select(Profesional).where(
            Profesional.consultorio_id == consultorio_id,
            Profesional.matricula == matricula,
            Profesional.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(Profesional.id != exclude_id)
        result = await self._session.scalars(statement)
        return result.first()

    async def get_by_usuario(
        self,
        usuario_id: uuid.UUID,
        exclude_id: uuid.UUID | None = None,
    ) -> Profesional | None:
        statement = select(Profesional).where(
            Profesional.usuario_id == usuario_id,
            Profesional.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(Profesional.id != exclude_id)
        result = await self._session.scalars(statement)
        return result.first()

    async def list_by_consultorio(
        self, consultorio_id: uuid.UUID
    ) -> list[Profesional]:
        result = await self._session.scalars(
            select(Profesional).where(
                Profesional.consultorio_id == consultorio_id,
                Profesional.deleted_at.is_(None),
            )
        )
        return list(result)


class SillonRepository(BaseRepository[Sillon]):
    model = Sillon

    async def get_by_nombre(
        self,
        consultorio_id: uuid.UUID,
        nombre: str,
        exclude_id: uuid.UUID | None = None,
    ) -> Sillon | None:
        statement = select(Sillon).where(
            Sillon.consultorio_id == consultorio_id,
            Sillon.nombre == nombre,
            Sillon.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(Sillon.id != exclude_id)
        result = await self._session.scalars(statement)
        return result.first()

    async def list_by_consultorio(
        self, consultorio_id: uuid.UUID
    ) -> list[Sillon]:
        result = await self._session.scalars(
            select(Sillon).where(
                Sillon.consultorio_id == consultorio_id,
                Sillon.deleted_at.is_(None),
            )
        )
        return list(result)


class ProfesionalSillonRepository:
    """Idempotent habilitation link (composite PK, no soft delete)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, profesional_id: uuid.UUID, sillon_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            insert(ProfesionalSillon)
            .values(profesional_id=profesional_id, sillon_id=sillon_id)
            .on_conflict_do_nothing(
                index_elements=["profesional_id", "sillon_id"]
            )
        )

    async def delete(
        self, profesional_id: uuid.UUID, sillon_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            delete(ProfesionalSillon).where(
                ProfesionalSillon.profesional_id == profesional_id,
                ProfesionalSillon.sillon_id == sillon_id,
            )
        )

    async def list_sillon_ids(
        self, profesional_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await self._session.scalars(
            select(ProfesionalSillon.sillon_id).where(
                ProfesionalSillon.profesional_id == profesional_id
            )
        )
        return list(result)


class PrestacionRepository(BaseRepository[Prestacion]):
    model = Prestacion

    async def get_by_codigo(
        self, codigo: str, exclude_id: uuid.UUID | None = None
    ) -> Prestacion | None:
        statement = select(Prestacion).where(
            Prestacion.codigo == codigo,
            Prestacion.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(Prestacion.id != exclude_id)
        result = await self._session.scalars(statement)
        return result.first()

    async def codigos_activos(self, codigos: list[str]) -> set[str]:
        """Return which of the given codes exist in the active catalogue."""
        if not codigos:
            return set()
        result = await self._session.scalars(
            select(Prestacion.codigo).where(
                Prestacion.codigo.in_(codigos),
                Prestacion.deleted_at.is_(None),
            )
        )
        return set(result)


class ObraSocialRepository(BaseRepository[ObraSocial]):
    model = ObraSocial

    async def get_by_nombre(
        self,
        consultorio_id: uuid.UUID,
        nombre: str,
        exclude_id: uuid.UUID | None = None,
    ) -> ObraSocial | None:
        """Case-insensitive lookup used to keep agreement names unique."""
        statement = select(ObraSocial).where(
            ObraSocial.consultorio_id == consultorio_id,
            func.lower(ObraSocial.nombre) == nombre.strip().lower(),
            ObraSocial.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(ObraSocial.id != exclude_id)
        result = await self._session.scalars(statement)
        return result.first()

    async def list_by_consultorio(
        self, consultorio_id: uuid.UUID
    ) -> list[ObraSocial]:
        result = await self._session.scalars(
            select(ObraSocial)
            .where(
                ObraSocial.consultorio_id == consultorio_id,
                ObraSocial.deleted_at.is_(None),
            )
            .order_by(ObraSocial.nombre)
        )
        return list(result)


class PacienteRepository(BaseRepository[Paciente]):
    model = Paciente

    async def get_by_dni(
        self,
        consultorio_id: uuid.UUID,
        dni: str,
        exclude_id: uuid.UUID | None = None,
    ) -> Paciente | None:
        statement = select(Paciente).where(
            Paciente.consultorio_id == consultorio_id,
            Paciente.dni == dni,
            Paciente.deleted_at.is_(None),
        )
        if exclude_id is not None:
            statement = statement.where(Paciente.id != exclude_id)
        result = await self._session.scalars(statement)
        return result.first()

    async def search(
        self,
        consultorio_id: uuid.UUID,
        *,
        dni: str | None = None,
        telefono: str | None = None,
        apellido: str | None = None,
    ) -> list[Paciente]:
        """Bounded lookup: callers must pass at least one criterion (D4)."""
        statement = select(Paciente).where(
            Paciente.consultorio_id == consultorio_id,
            Paciente.deleted_at.is_(None),
        )
        if dni is not None:
            statement = statement.where(Paciente.dni == dni)
        if telefono is not None:
            statement = statement.where(Paciente.telefono == telefono)
        if apellido is not None:
            statement = statement.where(
                func.lower(Paciente.apellido).like(
                    f"{apellido.strip().lower()}%"
                )
            )
        statement = statement.order_by(Paciente.apellido, Paciente.nombre)
        result = await self._session.scalars(statement)
        return list(result)


class BloqueoRepository(BaseRepository[Bloqueo]):
    model = Bloqueo

    async def list_vigentes(
        self,
        *,
        profesional_id: uuid.UUID | None = None,
        sillon_id: uuid.UUID | None = None,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> list[Bloqueo]:
        """Active blocks, optionally filtered by resource and overlap window."""
        statement = select(Bloqueo).where(Bloqueo.deleted_at.is_(None))
        if profesional_id is not None:
            statement = statement.where(
                Bloqueo.profesional_id == profesional_id
            )
        if sillon_id is not None:
            statement = statement.where(Bloqueo.sillon_id == sillon_id)
        if desde is not None:
            statement = statement.where(Bloqueo.hasta > desde)
        if hasta is not None:
            statement = statement.where(Bloqueo.desde < hasta)
        result = await self._session.scalars(statement)
        return list(result)

    async def list_para_disponibilidad(
        self,
        *,
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID | None,
        desde: datetime,
        hasta: datetime,
    ) -> list[Bloqueo]:
        """Blocks of the professional plus, if given, those of the chair."""
        recursos = [Bloqueo.profesional_id == profesional_id]
        if sillon_id is not None:
            recursos.append(Bloqueo.sillon_id == sillon_id)
        statement = select(Bloqueo).where(
            Bloqueo.deleted_at.is_(None),
            Bloqueo.hasta > desde,
            Bloqueo.desde < hasta,
            or_(*recursos),
        )
        result = await self._session.scalars(statement)
        return list(result)


class TurnoRepository(BaseRepository[Turno]):
    model = Turno

    async def list_rango(
        self,
        consultorio_id: uuid.UUID,
        *,
        desde: datetime,
        hasta: datetime,
        profesional_id: uuid.UUID | None = None,
        sillon_id: uuid.UUID | None = None,
        estado: str | None = None,
    ) -> list[Turno]:
        statement = select(Turno).where(
            Turno.consultorio_id == consultorio_id,
            Turno.deleted_at.is_(None),
            Turno.inicio >= desde,
            Turno.inicio < hasta,
        )
        if profesional_id is not None:
            statement = statement.where(Turno.profesional_id == profesional_id)
        if sillon_id is not None:
            statement = statement.where(Turno.sillon_id == sillon_id)
        if estado is not None:
            statement = statement.where(Turno.estado == estado)
        statement = statement.order_by(Turno.inicio)
        result = await self._session.scalars(statement)
        return list(result)

    async def list_solapados(
        self,
        *,
        consultorio_id: uuid.UUID,
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID,
        inicio: datetime,
        fin: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> list[Turno]:
        """Active turns sharing the professional or the chair with the range."""
        statement = select(Turno).where(
            Turno.consultorio_id == consultorio_id,
            Turno.deleted_at.is_(None),
            Turno.estado.in_(tuple(ESTADOS_ACTIVOS)),
            Turno.inicio < fin,
            Turno.fin > inicio,
            or_(
                Turno.profesional_id == profesional_id,
                Turno.sillon_id == sillon_id,
            ),
        )
        if exclude_id is not None:
            statement = statement.where(Turno.id != exclude_id)
        result = await self._session.scalars(statement)
        return list(result)

    async def list_activos_en_rango(
        self,
        *,
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID | None,
        desde: datetime,
        hasta: datetime,
    ) -> list[Turno]:
        recursos = [Turno.profesional_id == profesional_id]
        if sillon_id is not None:
            recursos.append(Turno.sillon_id == sillon_id)
        statement = select(Turno).where(
            Turno.deleted_at.is_(None),
            Turno.estado.in_(tuple(ESTADOS_ACTIVOS)),
            Turno.inicio < hasta,
            Turno.fin > desde,
            or_(*recursos),
        )
        result = await self._session.scalars(statement)
        return list(result)
