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
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    text,
)
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
