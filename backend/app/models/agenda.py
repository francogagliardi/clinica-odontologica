"""Agenda supply models (C-04): professionals, chairs and blocks.

`Profesional` carries the agenda configuration as explicit columns so PostgreSQL
can validate it with CHECKs (design D3): duration, ISO weekdays (0=Monday..6),
and a coherent time window. `ProfesionalSillon` is a composite-PK link that
tolerates repeated habilitation, mirroring `usuario_roles` in C-02.
"""

import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_DIAS_EN_RANGO = "dias_atencion <@ ARRAY[0,1,2,3,4,5,6]::integer[]"
_XOR_RECURSO = (
    "(profesional_id IS NOT NULL) <> (sillon_id IS NOT NULL)"
)
_ESTADOS_TURNO = (
    "'reservado','confirmado','en_sala','atendido','cancelado','ausente'"
)
_ORIGENES_TURNO = "'recepcion','online','whatsapp'"
_ESTADOS_ACTIVOS = "'reservado','confirmado','en_sala','atendido'"
_PREDICADO_EXCLUSION = (
    "deleted_at IS NULL AND NOT es_sobreturno "
    f"AND estado IN ({_ESTADOS_ACTIVOS})"
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


class Turno(Base, AuditMixin):
    """Appointment: the heart of the agenda (RN-TU-01/02/06/07).

    Anti-overlap is a PostgreSQL exclusion constraint, not only an application
    check: two normal rows cannot share a professional or a chair at the same
    time. Sobreturnos are excluded from the index on purpose and must carry a
    visible colour (RN-TU-06).
    """

    __tablename__ = "turnos"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint("fin > inicio", name="rango_coherente"),
        CheckConstraint(f"estado IN ({_ESTADOS_TURNO})", name="estado_valido"),
        CheckConstraint(
            f"origen IN ({_ORIGENES_TURNO})", name="origen_valido"
        ),
        CheckConstraint(
            "es_sobreturno = (color_sobreturno IS NOT NULL)",
            name="sobreturno_coherente",
        ),
        CheckConstraint(
            "color_sobreturno IS NULL "
            "OR color_sobreturno ~ '^#[0-9A-Fa-f]{6}$'",
            name="color_sobreturno_formato",
        ),
        Index("ix_turnos_profesional_inicio", "profesional_id", "inicio"),
        Index("ix_turnos_sillon_inicio", "sillon_id", "inicio"),
        Index("ix_turnos_estado", "estado"),
        Index(
            "uq_turnos_token_publico",
            "token_publico",
            unique=True,
            postgresql_where=text("token_publico IS NOT NULL"),
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
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("pacientes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("profesionales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sillon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("sillones.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prestacion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("prestaciones.id", ondelete="RESTRICT"),
        nullable=True,
    )
    inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="reservado",
        server_default=text("'reservado'"),
    )
    origen: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="recepcion",
        server_default=text("'recepcion'"),
    )
    es_sobreturno: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    color_sobreturno: Mapped[str | None] = mapped_column(
        String(7), nullable=True
    )
    token_publico: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )


# Expression-based exclusion constraints need the table columns already built.
for _nombre, _recurso in (
    ("ex_turnos_profesional", Turno.profesional_id),
    ("ex_turnos_sillon", Turno.sillon_id),
):
    Turno.__table__.append_constraint(
        ExcludeConstraint(
            (_recurso, "="),
            (func.tstzrange(Turno.inicio, Turno.fin, "[)"), "&&"),
            using="gist",
            where=text(_PREDICADO_EXCLUSION),
            name=_nombre,
        )
    )
