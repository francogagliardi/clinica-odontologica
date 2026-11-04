"""Waiting-list entry and its atomic retention of a freed slot (C-10).

The entry is the FIFO queue (RN-TU-05) and, while it holds an offer, a
booking resource of its own: the freed professional, chair and interval are
stored in the entry and two partial GiST exclusion constraints make
overlapping offers impossible even from raw SQL (design D2/D7).

The retention only exists while `estado = 'ofrecido'`: converting, expiring or
soft-deleting the row takes it out of the index in the same statement, so no
cleanup job is needed to release the slot.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_ESTADOS = "'pendiente','ofrecido','convertido','vencido'"
_OFERTA_COMPLETA = (
    "estado <> 'ofrecido' OR ("
    "oferta_inicio IS NOT NULL "
    "AND oferta_fin > oferta_inicio "
    "AND oferta_profesional_id IS NOT NULL "
    "AND oferta_sillon_id IS NOT NULL "
    "AND oferta_expira_en IS NOT NULL)"
)
_SIN_RETENCION_FUERA_DE_OFERTA = (
    "estado = 'ofrecido' OR ("
    "oferta_inicio IS NULL "
    "AND oferta_fin IS NULL "
    "AND oferta_profesional_id IS NULL "
    "AND oferta_sillon_id IS NULL "
    "AND oferta_expira_en IS NULL)"
)
_PREDICADO_RETENCION = "estado = 'ofrecido' AND deleted_at IS NULL"
_SIN_PROFESIONAL = "'00000000-0000-0000-0000-000000000000'::uuid"


class EntradaListaEspera(Base, AuditMixin):
    """FIFO entry that can retain the freed slot while its offer is live."""

    __tablename__ = "entradas_lista_espera"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="estado_valido"),
        CheckConstraint(_OFERTA_COMPLETA, name="oferta_completa"),
        CheckConstraint(
            "estado <> 'convertido' OR turno_id IS NOT NULL",
            name="conversion_con_turno",
        ),
        CheckConstraint(
            _SIN_RETENCION_FUERA_DE_OFERTA,
            name="sin_retencion_fuera_de_oferta",
        ),
        Index(
            "ix_entradas_lista_espera_cola",
            "consultorio_id",
            "estado",
            "orden",
        ),
        Index(
            "ix_entradas_lista_espera_prestacion",
            "prestacion_id",
            "estado",
            "orden",
        ),
        Index(
            "ix_entradas_lista_espera_vencimiento",
            "estado",
            "oferta_expira_en",
        ),
        Index(
            "ix_entradas_lista_espera_retencion_profesional",
            "oferta_profesional_id",
            "oferta_inicio",
        ),
        Index(
            "ix_entradas_lista_espera_retencion_sillon",
            "oferta_sillon_id",
            "oferta_inicio",
        ),
        Index(
            "uq_entradas_lista_espera_pendiente",
            "paciente_id",
            "prestacion_id",
            text(f"coalesce(profesional_id, {_SIN_PROFESIONAL})"),
            unique=True,
            postgresql_where=text(
                "estado = 'pendiente' AND deleted_at IS NULL"
            ),
        ),
        Index(
            "uq_entradas_lista_espera_turno",
            "turno_id",
            unique=True,
            postgresql_where=text("turno_id IS NOT NULL"),
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
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("prestaciones.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profesional_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("profesionales.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Monotonic FIFO order: an identity column is race-free (design D3).
    orden: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), nullable=False, unique=True
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente",
        server_default=text("'pendiente'"),
    )
    oferta_profesional_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("profesionales.id", ondelete="RESTRICT"),
        nullable=True,
    )
    oferta_sillon_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sillones.id", ondelete="RESTRICT"),
        nullable=True,
    )
    oferta_inicio: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    oferta_fin: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    oferta_expira_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("turnos.id", ondelete="RESTRICT"),
        nullable=True,
    )


# Expression-based exclusion constraints need the table columns already built,
# exactly like `Turno` (C-06).
for _nombre, _recurso in (
    ("ex_lista_espera_profesional", EntradaListaEspera.oferta_profesional_id),
    ("ex_lista_espera_sillon", EntradaListaEspera.oferta_sillon_id),
):
    EntradaListaEspera.__table__.append_constraint(
        ExcludeConstraint(
            (_recurso, "="),
            (
                func.tstzrange(
                    EntradaListaEspera.oferta_inicio,
                    EntradaListaEspera.oferta_fin,
                    "[)",
                ),
                "&&",
            ),
            using="gist",
            where=text(_PREDICADO_RETENCION),
            name=_nombre,
        )
    )
