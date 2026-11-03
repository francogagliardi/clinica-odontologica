"""Agenda supply models (C-04): professionals, chairs and blocks.

`Profesional` carries the agenda configuration as explicit columns so PostgreSQL
can validate it with CHECKs (design D3): duration, ISO weekdays (0=Monday..6),
and a coherent time window. `ProfesionalSillon` is a composite-PK link that
tolerates repeated habilitation, mirroring `usuario_roles` in C-02.
"""

import uuid
from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_DIAS_EN_RANGO = "dias_atencion <@ ARRAY[0,1,2,3,4,5,6]::integer[]"
_XOR_RECURSO = (
    "(profesional_id IS NOT NULL) <> (sillon_id IS NOT NULL)"
)


class Profesional(Base, AuditMixin):
    """Agendable professional with a validated base schedule (RN-TU-02)."""

    __tablename__ = "profesionales"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint("duracion_base_min > 0", name="duracion_base_positiva"),
        CheckConstraint("hora_hasta > hora_desde", name="horario_coherente"),
        CheckConstraint("cardinality(dias_atencion) > 0", name="dias_no_vacios"),
        CheckConstraint(_DIAS_EN_RANGO, name="dias_en_rango"),
        Index(
            "uq_profesionales_matricula_activo",
            "consultorio_id",
            "matricula",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_profesionales_usuario_activo",
            "usuario_id",
            unique=True,
            postgresql_where=text(
                "usuario_id IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        Index("ix_profesionales_consultorio", "consultorio_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    consultorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("consultorios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    matricula: Mapped[str] = mapped_column(String(40), nullable=False)
    especialidades: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)),
        nullable=False,
        default=list,
        server_default=text("'{}'::character varying[]"),
    )
    duracion_base_min: Mapped[int] = mapped_column(Integer, nullable=False)
    dias_atencion: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False
    )
    hora_desde: Mapped[time] = mapped_column(Time, nullable=False)
    hora_hasta: Mapped[time] = mapped_column(Time, nullable=False)


class Sillon(Base, AuditMixin):
    """Physical chair/box of a consultorio (exclusion resource, RN-TU-01)."""

    __tablename__ = "sillones"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        Index(
            "uq_sillones_nombre_activo",
            "consultorio_id",
            "nombre",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    consultorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("consultorios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)


class ProfesionalSillon(Base):
    """Idempotent habilitation: composite PK makes repeated inserts harmless."""

    __tablename__ = "profesionales_sillones"

    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("profesionales.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    sillon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sillones.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class Bloqueo(Base, AuditMixin):
    """Agenda block affecting exactly one resource (RN-TU-07)."""

    __tablename__ = "bloqueos"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(_XOR_RECURSO, name="recurso_exclusivo"),
        CheckConstraint("hasta > desde", name="rango_coherente"),
        Index("ix_bloqueos_profesional_desde", "profesional_id", "desde"),
        Index("ix_bloqueos_sillon_desde", "sillon_id", "desde"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    profesional_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("profesionales.id", ondelete="RESTRICT"),
        nullable=True,
    )
    sillon_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sillones.id", ondelete="RESTRICT"),
        nullable=True,
    )
    desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    hasta: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    motivo: Mapped[str] = mapped_column(String(200), nullable=False)
