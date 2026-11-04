"""Commercial catalogue models (C-04): services with optional deposit.

The Spanish business term is `seña`; the identifier is ASCII (`requiere_sena`,
`monto_sena`) to avoid Unicode column names. RN-TU-08/DD-10 only allow a deposit
when the service requires it, so a CHECK enforces the three valid shapes:
no deposit, or a required deposit with a strictly positive amount.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_SENA_COHERENTE = (
    "(requiere_sena AND monto_sena IS NOT NULL AND monto_sena > 0) "
    "OR (NOT requiere_sena AND monto_sena IS NULL)"
)


class Prestacion(Base, AuditMixin):
    """Service catalogue row: duration drives the appointment (RN-TU-02)."""

    __tablename__ = "prestaciones"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint("duracion_min > 0", name="duracion_positiva"),
        CheckConstraint("precio_base >= 0", name="precio_no_negativo"),
        CheckConstraint(_SENA_COHERENTE, name="sena_coherente"),
        Index(
            "uq_prestaciones_codigo_activo",
            "codigo",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_base: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    especialidad: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    requiere_sena: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    monto_sena: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )


class ObraSocial(Base, AuditMixin):
    """Insurance agreement with local coverage rules (DD-11, RN-OS-01/02).

    v1 validates coverage against these local rules only, so the table refuses
    `validacion_externa = true` instead of storing a flag nothing honours.
    """

    __tablename__ = "obras_sociales"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint("btrim(nombre) <> ''", name="nombre_no_vacio"),
        CheckConstraint(
            "jsonb_typeof(reglas_cobertura) = 'object'",
            name="reglas_objeto",
        ),
        CheckConstraint("NOT validacion_externa", name="sin_validacion_externa"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    consultorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("consultorios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    nomenclador_ref: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )
    reglas_cobertura: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    validacion_externa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


# Agreement names are unique per consultorio, case-insensitively (design D7).
Index(
    "uq_obras_sociales_nombre_activo",
    ObraSocial.consultorio_id,
    func.lower(ObraSocial.nombre),
    unique=True,
    postgresql_where=text("deleted_at IS NULL"),
)

# Budgets (C-12, design D3): the header stores the three totals so C-13/C-14
# keep the agreed amounts even if the catalogue or the convention changes.
# The cross-table invariant (subtotal = SUM(items)) is service-owned; the
# per-row CHECKs below make any direct SQL write reject incoherent money.
_ESTADOS_PRESUPUESTO = (
    "'borrador','aceptado','rechazado','en_curso','finalizado'"
)
_ESTADOS_COBERTURA = "'calculada','pendiente_verificacion'"
_PIEZA_FDI_VALIDA = (
    "((pieza / 10 BETWEEN 1 AND 4 AND pieza % 10 BETWEEN 1 AND 8) "
    "OR (pieza / 10 BETWEEN 5 AND 8 AND pieza % 10 BETWEEN 1 AND 5))"
)


class Presupuesto(Base, AuditMixin):
    """Commercial treatment offer with frozen totals (RN-CL-02, RN-OS-02)."""

    __tablename__ = "presupuestos"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"estado IN ({_ESTADOS_PRESUPUESTO})", name="estado_valido"
        ),
        CheckConstraint(
            f"cobertura_estado IN ({_ESTADOS_COBERTURA})",
            name="cobertura_estado_valido",
        ),
        CheckConstraint(
            "subtotal >= 0 AND cobertura_calculada >= 0 AND copago >= 0",
            name="importes_no_negativos",
        ),
        CheckConstraint(
            "subtotal = cobertura_calculada + copago",
            name="totales_coherentes",
        ),
        Index(
            "ix_presupuestos_paciente_created",
            "consultorio_id",
            "paciente_id",
            "created_at",
        ),
        Index(
            "ix_presupuestos_profesional_estado",
            "profesional_id",
            "estado",
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
    creado_por: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="borrador",
        server_default=text("'borrador'"),
    )
    cobertura_estado: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="calculada",
        server_default=text("'calculada'"),
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    cobertura_calculada: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    copago: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class ItemPresupuesto(Base, AuditMixin):
    """Budget line: the price is a snapshot of `precio_base` (design D7).

    Replaced lines are soft-deleted, never physically removed, so the offer
    history survives an edit of the draft.
    """

    __tablename__ = "items_presupuesto"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint(
            "precio_unitario >= 0 AND cobertura_item >= 0 "
            "AND copago_item >= 0",
            name="importes_no_negativos",
        ),
        CheckConstraint(
            "cobertura_item + copago_item = precio_unitario * cantidad",
            name="totales_item_coherentes",
        ),
        CheckConstraint(
            f"pieza IS NULL OR {_PIEZA_FDI_VALIDA}",
            name="pieza_fdi_valida",
        ),
        Index("ix_items_presupuesto_presupuesto", "presupuesto_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    presupuesto_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("presupuestos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("prestaciones.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pieza: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    cobertura_item: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    copago_item: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

