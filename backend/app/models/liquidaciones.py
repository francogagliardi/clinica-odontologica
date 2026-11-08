"""Insurance settlement models (C-14, design D9/D12).

A settlement groups covered budget lines of one obra social for an inclusive
period. Its period may not overlap another live settlement of the same
agreement: a GiST exclusion constraint enforces it in PostgreSQL (`23P01`),
using `btree_gist` for the UUID equality part.

A line (`items_liquidacion`) snapshots the covered amount and keeps the
traceability RN-OS-03 asks for (budget, budget line, payment and service). A
partial unique index makes the same budget line settleable only once while it
is live.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_ESTADOS_LIQUIDACION = "'borrador','cerrada'"
_CIERRE_COHERENTE = (
    "(estado = 'borrador' AND cerrada_por IS NULL AND cerrada_at IS NULL) "
    "OR (estado = 'cerrada' AND cerrada_por IS NOT NULL "
    "AND cerrada_at IS NOT NULL)"
)


class LiquidacionObraSocial(Base, AuditMixin):
    """Period settlement header for one agreement (RN-OS-03, US-031)."""

    __tablename__ = "liquidaciones_obras_sociales"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"estado IN ({_ESTADOS_LIQUIDACION})", name="estado_valido"
        ),
        CheckConstraint("desde <= hasta", name="periodo_valido"),
        CheckConstraint(_CIERRE_COHERENTE, name="cierre_coherente"),
        CheckConstraint(
            "total_cobertura >= 0 AND cantidad_practicas >= 0",
            name="totales_no_negativos",
        ),
        Index(
            "ix_liquidaciones_obras_social_periodo",
            "consultorio_id",
            "obra_social_id",
            "desde",
        ),
        Index("ix_liquidaciones_estado", "estado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    consultorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("consultorios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    obra_social_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("obras_sociales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    creado_por: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    desde: Mapped[date] = mapped_column(Date, nullable=False)
    hasta: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
    )
    total_cobertura: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default=text("0")
    )
    cantidad_practicas: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    observaciones: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    cerrada_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cerrada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# Expression-based constraint appended once the columns exist (same pattern as
# C-06 appointment exclusions). `[]` makes the period inclusive on both ends.
LiquidacionObraSocial.__table__.append_constraint(
    ExcludeConstraint(
        (LiquidacionObraSocial.obra_social_id, "="),
        (
            func.daterange(
                LiquidacionObraSocial.desde,
                LiquidacionObraSocial.hasta,
                "[]",
            ),
            "&&",
        ),
        using="gist",
        where=text("deleted_at IS NULL"),
        name="ex_liquidaciones_periodo",
    )
)


class ItemLiquidacion(Base, AuditMixin):
    """Settled budget line with a snapshot of what the agreement covers."""

    __tablename__ = "items_liquidacion"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("cobertura_item >= 0", name="cobertura_no_negativa"),
        Index("ix_items_liquidacion_liquidacion", "liquidacion_id"),
        Index("ix_items_liquidacion_presupuesto", "presupuesto_id"),
        Index("ix_items_liquidacion_cobro", "cobro_id"),
        Index(
            "uq_items_liquidacion_item",
            "item_presupuesto_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    liquidacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("liquidaciones_obras_sociales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("items_presupuesto.id", ondelete="RESTRICT"),
        nullable=False,
    )
    presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("presupuestos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cobro_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cobros.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("prestaciones.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prestacion_codigo: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    pieza: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    cobertura_item: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
