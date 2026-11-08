"""Cash register and payment models (C-13, design D1/D7/D9).

`Cobro` stores the economic fact (who paid, how much and through which
provider); `CajaDiaria` and `MovimientoCaja` explain the physical cash of the
day, including expenses and debts that a payment can never represent. All money
is `Numeric(12, 2)` and every coherence rule is also a named CHECK, so a direct
SQL write cannot leave a half-consistent row behind (R-04/R-05).

Idempotency lives in PostgreSQL (design D7):

- `uq_cobros_proveedor_pago` — one payment id can be reconciled only once.
- `uq_cobros_sena_turno` — at most one live deposit per appointment.
- `uq_movimientos_caja_cobro` — at most one cash movement per payment.
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_TIPOS_COBRO = "'sena','tratamiento','otro'"
_MEDIOS_PAGO = "'efectivo','mercadopago'"
_ESTADOS_COBRO = "'pendiente','aprobado','rechazado','reembolsado','perdido'"
_TIPOS_MOVIMIENTO = "'ingreso','gasto','deuda'"
_ESTADOS_CAJA = "'abierta','cerrada'"

# Design D9: a deposit points to the appointment only, a treatment payment to
# the budget only, and an "other" payment to neither.
_REFERENCIAS_COBRO = (
    "(tipo = 'sena' AND turno_id IS NOT NULL AND presupuesto_id IS NULL) "
    "OR (tipo = 'tratamiento' AND presupuesto_id IS NOT NULL "
    "AND turno_id IS NULL) "
    "OR (tipo = 'otro' AND turno_id IS NULL AND presupuesto_id IS NULL)"
)
# Cash is paid on the spot: only a Mercado Pago payment can remain pending.
_EFECTIVO_NO_PENDIENTE = "medio <> 'efectivo' OR estado <> 'pendiente'"
_PROVEEDOR_PAGO_SOLO_MP = (
    "proveedor_pago_id IS NULL OR medio = 'mercadopago'"
)
# Closing snapshots the system cash and demands a coherent difference; an open
# register cannot carry any closing data.
_CIERRE_COHERENTE = (
    "(estado = 'abierta' AND monto_sistema_efectivo IS NULL "
    "AND monto_contado IS NULL AND diferencia IS NULL "
    "AND cerrada_por IS NULL AND cerrada_at IS NULL) "
    "OR (estado = 'cerrada' AND monto_sistema_efectivo IS NOT NULL "
    "AND monto_contado IS NOT NULL "
    "AND diferencia = monto_contado - monto_sistema_efectivo "
    "AND cerrada_por IS NOT NULL AND cerrada_at IS NOT NULL)"
)


class Cobro(Base, AuditMixin):
    """Economic fact tied to a patient, an appointment or a budget (US-030)."""

    __tablename__ = "cobros"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(f"tipo IN ({_TIPOS_COBRO})", name="tipo_valido"),
        CheckConstraint(f"medio IN ({_MEDIOS_PAGO})", name="medio_valido"),
        CheckConstraint(f"estado IN ({_ESTADOS_COBRO})", name="estado_valido"),
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint(_REFERENCIAS_COBRO, name="referencias_coherentes"),
        CheckConstraint(
            _EFECTIVO_NO_PENDIENTE, name="efectivo_no_pendiente"
        ),
        CheckConstraint(
            _PROVEEDOR_PAGO_SOLO_MP, name="proveedor_pago_solo_mp"
        ),
        Index(
            "ix_cobros_paciente_fecha",
            "consultorio_id",
            "paciente_id",
            "fecha_operacion",
        ),
        Index("ix_cobros_turno", "turno_id"),
        Index("ix_cobros_presupuesto", "presupuesto_id"),
        Index("ix_cobros_estado", "consultorio_id", "estado"),
        Index(
            "uq_cobros_proveedor_pago",
            "proveedor_pago_id",
            unique=True,
            postgresql_where=text("proveedor_pago_id IS NOT NULL"),
        ),
        Index(
            "uq_cobros_sena_turno",
            "turno_id",
            unique=True,
            postgresql_where=text(
                "tipo = 'sena' "
                "AND estado IN ('pendiente','aprobado','perdido')"
            ),
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
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("turnos.id", ondelete="RESTRICT"),
        nullable=True,
    )
    presupuesto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("presupuestos.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # NULL means the system acted (webhook reconciliation, design D8).
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    medio: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente",
        server_default=text("'pendiente'"),
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    proveedor_pago_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    proveedor_preferencia_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    link_pago: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_operacion: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_conciliacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CajaDiaria(Base, AuditMixin):
    """One register per consultorio and Argentine date (RN-AD-03)."""

    __tablename__ = "cajas_diarias"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"estado IN ({_ESTADOS_CAJA})", name="estado_valido"
        ),
        CheckConstraint(
            "monto_apertura >= 0", name="monto_apertura_no_negativo"
        ),
        CheckConstraint(_CIERRE_COHERENTE, name="cierre_coherente"),
        UniqueConstraint(
            "consultorio_id",
            "fecha",
            name="uq_cajas_diarias_consultorio_fecha",
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
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="abierta",
        server_default=text("'abierta'"),
    )
    monto_apertura: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    monto_sistema_efectivo: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    monto_contado: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    diferencia: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    cerrada_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cerrada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observaciones: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )


class MovimientoCaja(Base, AuditMixin):
    """Cash entry/exit: the only way to explain expenses and debts (D1)."""

    __tablename__ = "movimientos_caja"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"tipo IN ({_TIPOS_MOVIMIENTO})", name="tipo_valido"
        ),
        CheckConstraint(f"medio IN ({_MEDIOS_PAGO})", name="medio_valido"),
        CheckConstraint("monto > 0", name="monto_positivo"),
        Index("ix_movimientos_caja_caja", "caja_id"),
        Index(
            "uq_movimientos_caja_cobro",
            "cobro_id",
            unique=True,
            postgresql_where=text("cobro_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    caja_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cajas_diarias.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    medio: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="efectivo",
        server_default=text("'efectivo'"),
    )
    cobro_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("cobros.id", ondelete="RESTRICT"),
        nullable=True,
    )
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
