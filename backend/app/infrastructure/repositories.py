"""Generic repository: reads/writes only, never commits (R-04).

Transaction boundaries belong to `UnitOfWork`. There is deliberately no
physical-delete operation: business entities are soft-deleted only.
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Generic, TypeVar

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.turnos import ESTADOS_ACTIVOS
from app.models import (
    Adjunto,
    Base,
    Bloqueo,
    CajaDiaria,
    Cobro,
    Comprobante,
    ComprobanteEnvio,
    Consentimiento,
    Consultorio,
    EntradaListaEspera,
    Evolucion,
    HallazgoDental,
    HistoriaClinica,
    ItemLiquidacion,
    ItemPresupuesto,
    LiquidacionObraSocial,
    MensajeWhatsApp,
    MovimientoCaja,
    ObraSocial,
    Odontograma,
    Paciente,
    Prestacion,
    Presupuesto,
    Profesional,
    ProfesionalSillon,
    Recordatorio,
    RegistroAuditoria,
    Rol,
    SecuenciaComprobante,
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

    async def existe_para_paciente(
        self,
        paciente_id: uuid.UUID,
        *,
        estados: tuple[str, ...],
        profesional_id: uuid.UUID | None = None,
    ) -> bool:
        """Clinical access helper: is there a live turn linking the patient?

        `profesional_id` narrows the check to "the patient is mine"; omitting it
        answers "the patient is being attended now" for the assistant (design D8).
        """
        statement = select(Turno.id).where(
            Turno.paciente_id == paciente_id,
            Turno.deleted_at.is_(None),
            Turno.estado.in_(estados),
        )
        if profesional_id is not None:
            statement = statement.where(
                Turno.profesional_id == profesional_id
            )
        return await self._session.scalar(statement.limit(1)) is not None


class ListaEsperaRepository(BaseRepository[EntradaListaEspera]):
    """FIFO queue and live retentions of a freed slot (C-10, D3/D4/D7)."""

    model = EntradaListaEspera

    async def list_by_consultorio(
        self,
        consultorio_id: uuid.UUID,
        *,
        estado: str | None = None,
        prestacion_id: uuid.UUID | None = None,
        profesional_id: uuid.UUID | None = None,
    ) -> list[EntradaListaEspera]:
        """Queue listing in FIFO order (RN-TU-05)."""
        statement = select(EntradaListaEspera).where(
            EntradaListaEspera.consultorio_id == consultorio_id,
            EntradaListaEspera.deleted_at.is_(None),
        )
        if estado is not None:
            statement = statement.where(EntradaListaEspera.estado == estado)
        if prestacion_id is not None:
            statement = statement.where(
                EntradaListaEspera.prestacion_id == prestacion_id
            )
        if profesional_id is not None:
            statement = statement.where(
                EntradaListaEspera.profesional_id == profesional_id
            )
        statement = statement.order_by(
            EntradaListaEspera.orden, EntradaListaEspera.created_at
        )
        result = await self._session.scalars(statement)
        return list(result)

    async def get_for_update(
        self, entrada_id: uuid.UUID
    ) -> EntradaListaEspera | None:
        """Lock the entry row for the conversion/rejection critical section."""
        result = await self._session.scalars(
            select(EntradaListaEspera)
            .where(EntradaListaEspera.id == entrada_id)
            .with_for_update()
        )
        return result.first()

    async def list_ofertas_vencidas(
        self, now: datetime
    ) -> list[EntradaListaEspera]:
        """Offers whose TTL elapsed, in FIFO order, for the scheduler sweep."""
        result = await self._session.scalars(
            select(EntradaListaEspera)
            .where(
                EntradaListaEspera.estado == "ofrecido",
                EntradaListaEspera.deleted_at.is_(None),
                EntradaListaEspera.oferta_expira_en <= now,
            )
            .order_by(EntradaListaEspera.orden)
        )
        return list(result)

    async def get_pendiente(
        self,
        *,
        consultorio_id: uuid.UUID,
        paciente_id: uuid.UUID,
        prestacion_id: uuid.UUID,
        profesional_id: uuid.UUID | None = None,
    ) -> EntradaListaEspera | None:
        """Duplicate detector: a patient waits once per service/professional."""
        statement = select(EntradaListaEspera).where(
            EntradaListaEspera.consultorio_id == consultorio_id,
            EntradaListaEspera.paciente_id == paciente_id,
            EntradaListaEspera.prestacion_id == prestacion_id,
            EntradaListaEspera.estado == "pendiente",
            EntradaListaEspera.deleted_at.is_(None),
        )
        if profesional_id is None:
            statement = statement.where(
                EntradaListaEspera.profesional_id.is_(None)
            )
        else:
            statement = statement.where(
                EntradaListaEspera.profesional_id == profesional_id
            )
        result = await self._session.scalars(statement)
        return result.first()

    async def siguiente_pendiente_compatible(
        self,
        *,
        consultorio_id: uuid.UUID,
        prestacion_id: uuid.UUID,
        profesional_id: uuid.UUID,
    ) -> EntradaListaEspera | None:
        """Claim the oldest compatible entry, skipping rows locked elsewhere.

        `FOR UPDATE SKIP LOCKED` makes two simultaneous freed slots pick
        different entries instead of offering the same one twice (design D4).
        """
        statement = (
            select(EntradaListaEspera)
            .where(
                EntradaListaEspera.consultorio_id == consultorio_id,
                EntradaListaEspera.prestacion_id == prestacion_id,
                EntradaListaEspera.estado == "pendiente",
                EntradaListaEspera.deleted_at.is_(None),
                or_(
                    EntradaListaEspera.profesional_id.is_(None),
                    EntradaListaEspera.profesional_id == profesional_id,
                ),
            )
            .order_by(
                EntradaListaEspera.orden, EntradaListaEspera.created_at
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.scalars(statement)
        return result.first()

    async def retenciones_vigentes(
        self,
        *,
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID,
        desde: datetime,
        hasta: datetime,
        now: datetime,
        exclude_id: uuid.UUID | None = None,
    ) -> list[EntradaListaEspera]:
        """Live offers overlapping the range for the professional or the chair.

        Lazy expiry (D5): a row past `oferta_expira_en` no longer blocks, even if
        the worker has not swept it yet.
        """
        statement = select(EntradaListaEspera).where(
            EntradaListaEspera.estado == "ofrecido",
            EntradaListaEspera.deleted_at.is_(None),
            EntradaListaEspera.oferta_expira_en > now,
            EntradaListaEspera.oferta_inicio < hasta,
            EntradaListaEspera.oferta_fin > desde,
            or_(
                EntradaListaEspera.oferta_profesional_id == profesional_id,
                EntradaListaEspera.oferta_sillon_id == sillon_id,
            ),
        )
        if exclude_id is not None:
            statement = statement.where(EntradaListaEspera.id != exclude_id)
        result = await self._session.scalars(statement)
        return list(result)

    async def list_retenciones_en_rango(
        self,
        *,
        desde: datetime,
        hasta: datetime,
        now: datetime,
        profesional_id: uuid.UUID | None = None,
        sillon_id: uuid.UUID | None = None,
    ) -> list[EntradaListaEspera]:
        """Live retentions used to hide slots from both availability views."""
        statement = select(EntradaListaEspera).where(
            EntradaListaEspera.estado == "ofrecido",
            EntradaListaEspera.deleted_at.is_(None),
            EntradaListaEspera.oferta_expira_en > now,
            EntradaListaEspera.oferta_inicio < hasta,
            EntradaListaEspera.oferta_fin > desde,
        )
        recursos = []
        if profesional_id is not None:
            recursos.append(
                EntradaListaEspera.oferta_profesional_id == profesional_id
            )
        if sillon_id is not None:
            recursos.append(
                EntradaListaEspera.oferta_sillon_id == sillon_id
            )
        if recursos:
            statement = statement.where(or_(*recursos))
        result = await self._session.scalars(statement)
        return list(result)


class RecordatorioRepository(BaseRepository[Recordatorio]):
    model = Recordatorio

    async def list_rango(
        self,
        *,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        turno_id: uuid.UUID | None = None,
    ) -> list[Recordatorio]:
        statement = select(Recordatorio)
        if desde is not None:
            statement = statement.where(Recordatorio.programado_para >= desde)
        if hasta is not None:
            statement = statement.where(Recordatorio.programado_para <= hasta)
        if turno_id is not None:
            statement = statement.where(Recordatorio.turno_id == turno_id)
        statement = statement.order_by(Recordatorio.programado_para)
        result = await self._session.scalars(statement)
        return list(result)


class MensajeWhatsAppRepository(BaseRepository[MensajeWhatsApp]):
    model = MensajeWhatsApp

    async def list_rango(
        self,
        *,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        estado: str | None = None,
    ) -> list[MensajeWhatsApp]:
        statement = select(MensajeWhatsApp)
        if desde is not None:
            statement = statement.where(MensajeWhatsApp.created_at >= desde)
        if hasta is not None:
            statement = statement.where(MensajeWhatsApp.created_at <= hasta)
        if estado is not None:
            statement = statement.where(
                MensajeWhatsApp.estado_envio == estado
            )
        statement = statement.order_by(MensajeWhatsApp.created_at.desc())
        result = await self._session.scalars(statement)
        return list(result)

class HistoriaClinicaRepository(BaseRepository[HistoriaClinica]):
    """One active history per patient; the partial unique index backs it."""

    model = HistoriaClinica

    async def get_activa_por_paciente(
        self, paciente_id: uuid.UUID
    ) -> HistoriaClinica | None:
        result = await self._session.scalars(
            select(HistoriaClinica).where(
                HistoriaClinica.paciente_id == paciente_id,
                HistoriaClinica.deleted_at.is_(None),
            )
        )
        return result.first()

    async def get_for_update(
        self, historia_id: uuid.UUID
    ) -> HistoriaClinica | None:
        """Lock the history for the odontogram snapshot critical section."""
        result = await self._session.scalars(
            select(HistoriaClinica)
            .where(HistoriaClinica.id == historia_id)
            .with_for_update()
        )
        return result.first()


class EvolucionRepository(BaseRepository[Evolucion]):
    """Signed evolutions are read-only; drafts can be corrected or discarded."""

    model = Evolucion

    async def list_by_historia(
        self, historia_id: uuid.UUID
    ) -> list[Evolucion]:
        result = await self._session.scalars(
            select(Evolucion)
            .where(
                Evolucion.historia_id == historia_id,
                Evolucion.deleted_at.is_(None),
            )
            .order_by(Evolucion.fecha.desc(), Evolucion.created_at.desc())
        )
        return list(result)

    async def get_rectificatoria_activa(
        self, rectifica_a: uuid.UUID
    ) -> Evolucion | None:
        result = await self._session.scalars(
            select(Evolucion).where(
                Evolucion.rectifica_a == rectifica_a,
                Evolucion.deleted_at.is_(None),
            )
        )
        return result.first()


class OdontogramaRepository(BaseRepository[Odontograma]):
    """Immutable snapshots: reads only plus the next-version calculation."""

    model = Odontograma

    async def proxima_version(self, historia_id: uuid.UUID) -> int:
        """`COALESCE(MAX(version), 0) + 1`; the unique index is the safety net."""
        actual = await self._session.scalar(
            select(func.coalesce(func.max(Odontograma.version), 0)).where(
                Odontograma.historia_id == historia_id
            )
        )
        return int(actual or 0) + 1

    async def get_vigente(
        self, historia_id: uuid.UUID
    ) -> Odontograma | None:
        result = await self._session.scalars(
            select(Odontograma)
            .where(Odontograma.historia_id == historia_id)
            .order_by(Odontograma.version.desc())
            .limit(1)
        )
        return result.first()

    async def get_por_version(
        self, historia_id: uuid.UUID, version: int
    ) -> Odontograma | None:
        result = await self._session.scalars(
            select(Odontograma).where(
                Odontograma.historia_id == historia_id,
                Odontograma.version == version,
            )
        )
        return result.first()


class HallazgoDentalRepository(BaseRepository[HallazgoDental]):
    """Findings belong to one immutable snapshot; reads and inserts only."""

    model = HallazgoDental

    async def list_by_odontograma(
        self, odontograma_id: uuid.UUID
    ) -> list[HallazgoDental]:
        result = await self._session.scalars(
            select(HallazgoDental)
            .where(HallazgoDental.odontograma_id == odontograma_id)
            .order_by(HallazgoDental.pieza, HallazgoDental.cara)
        )
        return list(result)


class AdjuntoRepository(BaseRepository[Adjunto]):
    """Clinical attachments: metadata and bytes always tied to a history."""

    model = Adjunto

    async def list_by_historia(self, historia_id: uuid.UUID) -> list[Adjunto]:
        result = await self._session.scalars(
            select(Adjunto)
            .where(
                Adjunto.historia_id == historia_id,
                Adjunto.deleted_at.is_(None),
            )
            .order_by(Adjunto.created_at.desc())
        )
        return list(result)


class ConsentimientoRepository(BaseRepository[Consentimiento]):
    """Append-only consents ordered from the most recent act."""

    model = Consentimiento

    async def list_by_paciente(
        self, paciente_id: uuid.UUID
    ) -> list[Consentimiento]:
        result = await self._session.scalars(
            select(Consentimiento)
            .where(
                Consentimiento.paciente_id == paciente_id,
                Consentimiento.deleted_at.is_(None),
            )
            .order_by(
                Consentimiento.fecha.desc(),
                Consentimiento.created_at.desc(),
            )
        )
        return list(result)


class PresupuestoRepository(BaseRepository[Presupuesto]):
    """Budget header: detail with live lines and filtered, newest-first lists."""

    model = Presupuesto

    async def get_con_items(
        self, presupuesto_id: uuid.UUID
    ) -> tuple[Presupuesto | None, list[ItemPresupuesto]]:
        """Return the header plus only active lines (design D3/D11)."""
        presupuesto = await self.get(presupuesto_id)
        if presupuesto is None or presupuesto.deleted_at is not None:
            return None, []
        result = await self._session.scalars(
            select(ItemPresupuesto)
            .where(
                ItemPresupuesto.presupuesto_id == presupuesto_id,
                ItemPresupuesto.deleted_at.is_(None),
            )
            .order_by(
                ItemPresupuesto.created_at, ItemPresupuesto.id
            )
        )
        return presupuesto, list(result)

    async def list_filtrado(
        self,
        consultorio_id: uuid.UUID,
        *,
        paciente_id: uuid.UUID | None = None,
        profesional_id: uuid.UUID | None = None,
        estado: str | None = None,
    ) -> list[Presupuesto]:
        """Consultorio scope plus optional filters, newest first (US-021)."""
        statement = select(Presupuesto).where(
            Presupuesto.consultorio_id == consultorio_id,
            Presupuesto.deleted_at.is_(None),
        )
        if paciente_id is not None:
            statement = statement.where(
                Presupuesto.paciente_id == paciente_id
            )
        if profesional_id is not None:
            statement = statement.where(
                Presupuesto.profesional_id == profesional_id
            )
        if estado is not None:
            statement = statement.where(Presupuesto.estado == estado)
        statement = statement.order_by(
            Presupuesto.created_at.desc(), Presupuesto.id.desc()
        )
        result = await self._session.scalars(statement)
        return list(result)


class ItemPresupuestoRepository(BaseRepository[ItemPresupuesto]):
    """Budget lines: soft-deleted when a draft replaces its items."""

    model = ItemPresupuesto

    async def list_by_presupuesto(
        self,
        presupuesto_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> list[ItemPresupuesto]:
        statement = select(ItemPresupuesto).where(
            ItemPresupuesto.presupuesto_id == presupuesto_id
        )
        if not include_inactive:
            statement = statement.where(
                ItemPresupuesto.deleted_at.is_(None)
            )
        statement = statement.order_by(
            ItemPresupuesto.created_at, ItemPresupuesto.id
        )
        result = await self._session.scalars(statement)
        return list(result)

    async def desactivar_de_presupuesto(
        self, presupuesto_id: uuid.UUID
    ) -> int:
        """Soft-delete every live line of a draft; history is preserved."""
        result = await self._session.execute(
            update(ItemPresupuesto)
            .where(
                ItemPresupuesto.presupuesto_id == presupuesto_id,
                ItemPresupuesto.deleted_at.is_(None),
            )
            .values(is_active=False, deleted_at=func.now()),
            execution_options={"synchronize_session": False},
        )
        return result.rowcount or 0


class CobroRepository(BaseRepository[Cobro]):
    """Payments: live deposit per appointment and approved treatment total."""

    model = Cobro

    async def get_sena_viva_por_turno(
        self, turno_id: uuid.UUID
    ) -> Cobro | None:
        """A deposit is live while it is pending, approved or already lost.

        Rejected/refunded deposits are terminal and must not block a retry
        (design D7).
        """
        result = await self._session.scalars(
            select(Cobro).where(
                Cobro.turno_id == turno_id,
                Cobro.tipo == "sena",
                Cobro.estado.in_(("pendiente", "aprobado", "perdido")),
                Cobro.deleted_at.is_(None),
            )
        )
        return result.first()

    async def get_by_proveedor_pago_id(
        self, proveedor_pago_id: str
    ) -> Cobro | None:
        """Idempotency lookup for the Mercado Pago webhook (design D7)."""
        result = await self._session.scalars(
            select(Cobro).where(
                Cobro.proveedor_pago_id == proveedor_pago_id,
                Cobro.deleted_at.is_(None),
            )
        )
        return result.first()

    async def sumar_tratamientos_aprobados(
        self, presupuesto_id: uuid.UUID
    ) -> Decimal:
        """Money already collected for a budget, used to compute the balance."""
        total = await self._session.scalar(
            select(func.coalesce(func.sum(Cobro.monto), 0)).where(
                Cobro.presupuesto_id == presupuesto_id,
                Cobro.tipo == "tratamiento",
                Cobro.estado == "aprobado",
                Cobro.deleted_at.is_(None),
            )
        )
        return Decimal(total or 0).quantize(Decimal("0.01"))

    async def list_filtrado(
        self,
        consultorio_id: uuid.UUID,
        *,
        paciente_id: uuid.UUID | None = None,
        turno_id: uuid.UUID | None = None,
        presupuesto_id: uuid.UUID | None = None,
        estado: str | None = None,
        medio: str | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        profesional_id: uuid.UUID | None = None,
    ) -> list[Cobro]:
        """Consultorio scope plus the declared filters, newest first (D10).

        `profesional_id` narrows to payments whose appointment or budget
        belongs to that professional, which is how the odontologist reads only
        their own rows (design D8).
        """
        statement = select(Cobro).where(
            Cobro.consultorio_id == consultorio_id,
            Cobro.deleted_at.is_(None),
        )
        if profesional_id is not None:
            statement = statement.outerjoin(
                Turno, Cobro.turno_id == Turno.id
            ).outerjoin(
                Presupuesto, Cobro.presupuesto_id == Presupuesto.id
            )
            statement = statement.where(
                or_(
                    Turno.profesional_id == profesional_id,
                    Presupuesto.profesional_id == profesional_id,
                )
            )
        if paciente_id is not None:
            statement = statement.where(Cobro.paciente_id == paciente_id)
        if turno_id is not None:
            statement = statement.where(Cobro.turno_id == turno_id)
        if presupuesto_id is not None:
            statement = statement.where(
                Cobro.presupuesto_id == presupuesto_id
            )
        if estado is not None:
            statement = statement.where(Cobro.estado == estado)
        if medio is not None:
            statement = statement.where(Cobro.medio == medio)
        if fecha_desde is not None:
            statement = statement.where(
                Cobro.fecha_operacion >= fecha_desde
            )
        if fecha_hasta is not None:
            statement = statement.where(
                Cobro.fecha_operacion <= fecha_hasta
            )
        statement = statement.order_by(
            Cobro.fecha_operacion.desc(),
            Cobro.created_at.desc(),
            Cobro.id.desc(),
        )
        result = await self._session.scalars(statement)
        return list(result)


class CajaDiariaRepository(BaseRepository[CajaDiaria]):
    """One register per consultorio and local date; closing locks the row."""

    model = CajaDiaria

    async def get_por_consultorio_fecha(
        self,
        consultorio_id: uuid.UUID,
        fecha: date,
        *,
        for_update: bool = False,
    ) -> CajaDiaria | None:
        """Read the day's register, optionally locking it for the close.

        `FOR UPDATE` serializes two simultaneous closings and prevents a
        movement from being inserted while the snapshot is being taken
        (design D10).
        """
        statement = select(CajaDiaria).where(
            CajaDiaria.consultorio_id == consultorio_id,
            CajaDiaria.fecha == fecha,
            CajaDiaria.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.scalars(statement)
        return result.first()


class MovimientoCajaRepository(BaseRepository[MovimientoCaja]):
    """Cash movements of a register (income, expense, debt)."""

    model = MovimientoCaja

    async def list_by_caja(self, caja_id: uuid.UUID) -> list[MovimientoCaja]:
        result = await self._session.scalars(
            select(MovimientoCaja)
            .where(
                MovimientoCaja.caja_id == caja_id,
                MovimientoCaja.deleted_at.is_(None),
            )
            .order_by(MovimientoCaja.created_at, MovimientoCaja.id)
        )
        return list(result)

    async def get_by_cobro(self, cobro_id: uuid.UUID) -> MovimientoCaja | None:
        """One payment yields one movement (design D7)."""
        result = await self._session.scalars(
            select(MovimientoCaja).where(
                MovimientoCaja.cobro_id == cobro_id,
                MovimientoCaja.deleted_at.is_(None),
            )
        )
        return result.first()


class ComprobanteRepository(BaseRepository[Comprobante]):
    """Internal receipts and their fiscal queue (C-14, design D1/D4/D5)."""

    model = Comprobante

    async def get_by_cobro(self, cobro_id: uuid.UUID) -> Comprobante | None:
        """The unique receipt of a payment (idempotent creation lookup)."""
        result = await self._session.scalars(
            select(Comprobante).where(
                Comprobante.cobro_id == cobro_id,
                Comprobante.deleted_at.is_(None),
            )
        )
        return result.first()

    async def list_filtrado(
        self,
        consultorio_id: uuid.UUID,
        *,
        cobro_id: uuid.UUID | None = None,
        paciente_id: uuid.UUID | None = None,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        tipo: str | None = None,
    ) -> list[Comprobante]:
        """Consultorio scope plus the declared filters, newest first (D13)."""
        statement = select(Comprobante).where(
            Comprobante.consultorio_id == consultorio_id,
            Comprobante.deleted_at.is_(None),
        )
        if cobro_id is not None:
            statement = statement.where(Comprobante.cobro_id == cobro_id)
        if paciente_id is not None:
            statement = statement.where(
                Comprobante.paciente_id == paciente_id
            )
        if estado is not None:
            statement = statement.where(Comprobante.estado == estado)
        if desde is not None:
            statement = statement.where(
                Comprobante.fecha_emision >= desde
            )
        if hasta is not None:
            statement = statement.where(Comprobante.fecha_emision <= hasta)
        if tipo is not None:
            statement = statement.where(Comprobante.tipo == tipo)
        statement = statement.order_by(
            Comprobante.fecha_emision.desc(),
            Comprobante.created_at.desc(),
            Comprobante.id.desc(),
        )
        result = await self._session.scalars(statement)
        return list(result)

    async def list_pendientes_vencidos(
        self,
        ahora: datetime,
        *,
        limite: int = 50,
        claim_timeout_seconds: int = 300,
    ) -> list[Comprobante]:
        """Due `pendiente` rows whose claim (if any) already expired (D4).

        This is the durable sweep: it does not depend on Redis, so a lost queue
        message cannot hide a receipt forever.
        """
        limite_claim = ahora - timedelta(seconds=claim_timeout_seconds)
        statement = (
            select(Comprobante)
            .where(
                Comprobante.estado == "pendiente",
                Comprobante.deleted_at.is_(None),
                or_(
                    Comprobante.proximo_intento.is_(None),
                    Comprobante.proximo_intento <= ahora,
                ),
                or_(
                    Comprobante.reclamado_at.is_(None),
                    Comprobante.reclamado_at < limite_claim,
                ),
            )
            .order_by(Comprobante.created_at, Comprobante.id)
            .limit(limite)
        )
        result = await self._session.scalars(statement)
        return list(result)

    async def reclamar(
        self,
        comprobante_id: uuid.UUID,
        *,
        token: uuid.UUID,
        ahora: datetime,
        claim_timeout_seconds: int = 300,
    ) -> Comprobante | None:
        """Atomically take one receipt; None means another worker owns it (D4).

        The provider call happens outside this transaction, so the claim expires
        after five minutes instead of holding a row lock while waiting.
        """
        limite_claim = ahora - timedelta(seconds=claim_timeout_seconds)
        statement = (
            update(Comprobante)
            .where(
                Comprobante.id == comprobante_id,
                Comprobante.estado == "pendiente",
                Comprobante.deleted_at.is_(None),
                or_(
                    Comprobante.proximo_intento.is_(None),
                    Comprobante.proximo_intento <= ahora,
                ),
                or_(
                    Comprobante.reclamado_at.is_(None),
                    Comprobante.reclamado_at < limite_claim,
                ),
            )
            .values(claim_token=token, reclamado_at=ahora)
            .returning(Comprobante)
            .execution_options(synchronize_session=False)
        )
        result = await self._session.scalars(statement)
        return result.first()


class ComprobanteEnvioRepository(BaseRepository[ComprobanteEnvio]):
    """Simulated invoice delivery, one row per receipt and channel (D10)."""

    model = ComprobanteEnvio

    async def get_por_canal(
        self, comprobante_id: uuid.UUID, canal: str
    ) -> ComprobanteEnvio | None:
        result = await self._session.scalars(
            select(ComprobanteEnvio).where(
                ComprobanteEnvio.comprobante_id == comprobante_id,
                ComprobanteEnvio.canal == canal,
                ComprobanteEnvio.deleted_at.is_(None),
            )
        )
        return result.first()

    async def list_by_comprobante(
        self, comprobante_id: uuid.UUID
    ) -> list[ComprobanteEnvio]:
        result = await self._session.scalars(
            select(ComprobanteEnvio)
            .where(
                ComprobanteEnvio.comprobante_id == comprobante_id,
                ComprobanteEnvio.deleted_at.is_(None),
            )
            .order_by(ComprobanteEnvio.created_at, ComprobanteEnvio.id)
        )
        return list(result)


class SecuenciaComprobanteRepository:
    """Gapless counters with `UPDATE ... RETURNING` (design D2).

    The row is created on first use and the increment happens inside the
    caller's transaction, so a rollback does not consume a number.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _asegurar(
        self, consultorio_id: uuid.UUID, punto_venta: int
    ) -> None:
        await self._session.execute(
            insert(SecuenciaComprobante)
            .values(
                consultorio_id=consultorio_id,
                punto_venta=punto_venta,
                ultimo_interno=0,
                ultimo_fiscal=0,
            )
            .on_conflict_do_nothing(
                index_elements=["consultorio_id", "punto_venta"]
            )
        )

    async def siguiente_interno(
        self, consultorio_id: uuid.UUID, punto_venta: int
    ) -> int:
        await self._asegurar(consultorio_id, punto_venta)
        valor = await self._session.scalar(
            update(SecuenciaComprobante)
            .where(
                SecuenciaComprobante.consultorio_id == consultorio_id,
                SecuenciaComprobante.punto_venta == punto_venta,
            )
            .values(
                ultimo_interno=SecuenciaComprobante.ultimo_interno + 1
            )
            .returning(SecuenciaComprobante.ultimo_interno)
            .execution_options(synchronize_session=False)
        )
        return int(valor)

    async def siguiente_fiscal(
        self, consultorio_id: uuid.UUID, punto_venta: int
    ) -> int:
        await self._asegurar(consultorio_id, punto_venta)
        valor = await self._session.scalar(
            update(SecuenciaComprobante)
            .where(
                SecuenciaComprobante.consultorio_id == consultorio_id,
                SecuenciaComprobante.punto_venta == punto_venta,
            )
            .values(
                ultimo_fiscal=SecuenciaComprobante.ultimo_fiscal + 1
            )
            .returning(SecuenciaComprobante.ultimo_fiscal)
            .execution_options(synchronize_session=False)
        )
        return int(valor)


class LiquidacionRepository(BaseRepository[LiquidacionObraSocial]):
    """Settlement header plus its live lines (C-14, design D9)."""

    model = LiquidacionObraSocial

    async def get_con_items(
        self, liquidacion_id: uuid.UUID
    ) -> tuple[LiquidacionObraSocial | None, list[ItemLiquidacion]]:
        liquidacion = await self.get(liquidacion_id)
        if liquidacion is None or liquidacion.deleted_at is not None:
            return None, []
        result = await self._session.scalars(
            select(ItemLiquidacion)
            .where(
                ItemLiquidacion.liquidacion_id == liquidacion_id,
                ItemLiquidacion.deleted_at.is_(None),
            )
            .order_by(ItemLiquidacion.created_at, ItemLiquidacion.id)
        )
        return liquidacion, list(result)

    async def get_solapada(
        self,
        *,
        consultorio_id: uuid.UUID,
        obra_social_id: uuid.UUID,
        desde: date,
        hasta: date,
        exclude_id: uuid.UUID | None = None,
    ) -> LiquidacionObraSocial | None:
        """A live settlement of the same agreement whose period overlaps."""
        statement = select(LiquidacionObraSocial).where(
            LiquidacionObraSocial.consultorio_id == consultorio_id,
            LiquidacionObraSocial.obra_social_id == obra_social_id,
            LiquidacionObraSocial.deleted_at.is_(None),
            LiquidacionObraSocial.desde <= hasta,
            LiquidacionObraSocial.hasta >= desde,
        )
        if exclude_id is not None:
            statement = statement.where(
                LiquidacionObraSocial.id != exclude_id
            )
        result = await self._session.scalars(statement)
        return result.first()

    async def list_filtrado(
        self,
        consultorio_id: uuid.UUID,
        *,
        obra_social_id: uuid.UUID | None = None,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[LiquidacionObraSocial]:
        """Consultorio scope plus the declared period/agreement filters."""
        statement = select(LiquidacionObraSocial).where(
            LiquidacionObraSocial.consultorio_id == consultorio_id,
            LiquidacionObraSocial.deleted_at.is_(None),
        )
        if obra_social_id is not None:
            statement = statement.where(
                LiquidacionObraSocial.obra_social_id == obra_social_id
            )
        if estado is not None:
            statement = statement.where(
                LiquidacionObraSocial.estado == estado
            )
        if desde is not None:
            statement = statement.where(
                LiquidacionObraSocial.hasta >= desde
            )
        if hasta is not None:
            statement = statement.where(
                LiquidacionObraSocial.desde <= hasta
            )
        statement = statement.order_by(
            LiquidacionObraSocial.desde.desc(),
            LiquidacionObraSocial.created_at.desc(),
            LiquidacionObraSocial.id.desc(),
        )
        result = await self._session.scalars(statement)
        return list(result)

    async def list_items_liquidables(
        self,
        *,
        consultorio_id: uuid.UUID,
        obra_social_id: uuid.UUID,
        desde: date,
        hasta: date,
    ) -> list[tuple[ItemPresupuesto, Presupuesto, Cobro]]:
        """D9 selection: covered budget lines of a treatment payment.

        A payment is the closest signal of realised practice; one payment per
        budget is enough, and a line already in a live settlement is excluded.
        """
        cobros = list(
            await self._session.scalars(
                select(Cobro)
                .join(Paciente, Paciente.id == Cobro.paciente_id)
                .where(
                    Cobro.consultorio_id == consultorio_id,
                    Cobro.tipo == "tratamiento",
                    Cobro.estado == "aprobado",
                    Cobro.fecha_operacion >= desde,
                    Cobro.fecha_operacion <= hasta,
                    Cobro.deleted_at.is_(None),
                    Paciente.obra_social_id == obra_social_id,
                    Paciente.consultorio_id == consultorio_id,
                    Paciente.deleted_at.is_(None),
                )
                .order_by(Cobro.fecha_operacion, Cobro.id)
            )
        )
        por_presupuesto: dict[uuid.UUID, Cobro] = {}
        for cobro in cobros:
            if cobro.presupuesto_id is not None:
                por_presupuesto.setdefault(cobro.presupuesto_id, cobro)
        if not por_presupuesto:
            return []

        presupuestos = {
            presupuesto.id: presupuesto
            for presupuesto in await self._session.scalars(
                select(Presupuesto).where(
                    Presupuesto.id.in_(list(por_presupuesto)),
                    Presupuesto.consultorio_id == consultorio_id,
                    Presupuesto.estado.in_(
                        ("aceptado", "en_curso", "finalizado")
                    ),
                    Presupuesto.deleted_at.is_(None),
                )
            )
        }
        if not presupuestos:
            return []

        items = list(
            await self._session.scalars(
                select(ItemPresupuesto)
                .where(
                    ItemPresupuesto.presupuesto_id.in_(
                        list(presupuestos)
                    ),
                    ItemPresupuesto.deleted_at.is_(None),
                    ItemPresupuesto.cobertura_item > 0,
                )
                .order_by(
                    ItemPresupuesto.presupuesto_id,
                    ItemPresupuesto.created_at,
                    ItemPresupuesto.id,
                )
            )
        )
        if not items:
            return []

        ya_liquidados = set(
            await self._session.scalars(
                select(ItemLiquidacion.item_presupuesto_id).where(
                    ItemLiquidacion.item_presupuesto_id.in_(
                        [item.id for item in items]
                    ),
                    ItemLiquidacion.deleted_at.is_(None),
                )
            )
        )
        return [
            (
                item,
                presupuestos[item.presupuesto_id],
                por_presupuesto[item.presupuesto_id],
            )
            for item in items
            if item.id not in ya_liquidados
        ]


class ItemLiquidacionRepository(BaseRepository[ItemLiquidacion]):
    """Settled lines: the duplicate guard and per-settlement detail."""

    model = ItemLiquidacion

    async def list_by_liquidacion(
        self, liquidacion_id: uuid.UUID
    ) -> list[ItemLiquidacion]:
        result = await self._session.scalars(
            select(ItemLiquidacion)
            .where(
                ItemLiquidacion.liquidacion_id == liquidacion_id,
                ItemLiquidacion.deleted_at.is_(None),
            )
            .order_by(ItemLiquidacion.created_at, ItemLiquidacion.id)
        )
        return list(result)

    async def ids_ya_liquidados(
        self, item_presupuesto_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Which budget lines already belong to a live settlement."""
        if not item_presupuesto_ids:
            return set()
        result = await self._session.scalars(
            select(ItemLiquidacion.item_presupuesto_id).where(
                ItemLiquidacion.item_presupuesto_id.in_(
                    item_presupuesto_ids
                ),
                ItemLiquidacion.deleted_at.is_(None),
            )
        )
        return set(result)

    async def soft_delete_by_liquidacion(
        self, liquidacion_id: uuid.UUID
    ) -> int:
        """Release every live line when a draft is deleted (D9)."""
        result = await self._session.execute(
            update(ItemLiquidacion)
            .where(
                ItemLiquidacion.liquidacion_id == liquidacion_id,
                ItemLiquidacion.deleted_at.is_(None),
            )
            .values(is_active=False, deleted_at=func.now()),
            execution_options={"synchronize_session": False},
        )
        return result.rowcount or 0
