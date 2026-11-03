"""Patient registry models (C-05).

A patient is identified inside a consultorio by its DNI, unique only among
active rows so a soft-deleted patient frees the number. The phone is canonical
(`+549...`) because WhatsApp is the clinic channel, and a national insurance
number cannot exist without an insurance agreement. Format and coherence are
enforced in PostgreSQL as well as at the HTTP edge (design D2/D3/D6/D11).
"""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_DNI_FORMATO = "^[0-9]{7,8}$"
_TELEFONO_FORMATO = "^\\+549[0-9]{10}$"
_COBERTURA_COHERENTE = (
    "(obra_social_id IS NOT NULL) OR (nro_afiliado IS NULL)"
)


class Paciente(Base, AuditMixin):
    """Person who books and receives care (RN-TU-01, RN-OS-01)."""

    __tablename__ = "pacientes"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(f"dni ~ '{_DNI_FORMATO}'", name="dni_formato"),
        CheckConstraint(
            f"telefono ~ '{_TELEFONO_FORMATO}'", name="telefono_formato"
        ),
        CheckConstraint(_COBERTURA_COHERENTE, name="cobertura_coherente"),
        Index(
            "uq_pacientes_dni_activo",
            "consultorio_id",
            "dni",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_pacientes_telefono", "consultorio_id", "telefono"),
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
    apellido: Mapped[str] = mapped_column(String(120), nullable=False)
    dni: Mapped[str] = mapped_column(String(8), nullable=False)
    fecha_nacimiento: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    telefono: Mapped[str] = mapped_column(String(16), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    obra_social_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("obras_sociales.id", ondelete="RESTRICT"),
        nullable=True,
    )
    nro_afiliado: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


# Expression index for case-insensitive surname prefix search (design D4).
Index(
    "ix_pacientes_apellido_lower",
    func.lower(Paciente.apellido),
    postgresql_ops={"lower": "text_pattern_ops"},
)
