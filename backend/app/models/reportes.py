"""Durable exportation job (C-15, design D3/D7/D12).

`exportaciones` is the source of truth of an export request (R-06): Redis only
accelerates the worker, which sweeps this table when the queue is empty or
unavailable. The artifact lives in `contenido` (`BYTEA`) so PostgreSQL remains
the only durable storage (R-04).

Deliberate differences with business entities:

- it does **not** inherit `AuditMixin`: an exportation is never soft-deleted,
  and offering `deleted_at` would suggest a retention window that v1 does not
  have (D11);
- `created_at`/`updated_at` are kept for ordering and observability.

Invariants owned by PostgreSQL (D12):

- `alcance_paciente_coherente`: patient scope needs a patient, consultorio
  scope forbids one.
- `estado_coherente`: `lista` carries content, positive size and generation
  time; the other states forbid all three.
- `fallida_con_error`: a failed job always explains itself.
- `intentos_no_negativos` / `tamano_positivo`: defensive ranges.
- `uq_exportaciones_en_curso`: at most one identical job in progress per
  consultorio, requester and scope; `lista`/`fallida` do not block a retry.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_ALCANCES = "'paciente','consultorio'"
_ESTADOS = "'pendiente','generando','lista','fallida'"
_UUID_NIL = "00000000-0000-0000-0000-000000000000"
_ALCANCE_PACIENTE_COHERENTE = (
    "(alcance = 'paciente' AND paciente_id IS NOT NULL) "
    "OR (alcance = 'consultorio' AND paciente_id IS NULL)"
)
_ESTADO_COHERENTE = (
    "(estado = 'lista' AND contenido IS NOT NULL "
    "AND tamano_bytes IS NOT NULL AND tamano_bytes > 0 "
    "AND generada_at IS NOT NULL) "
    "OR (estado IN ('pendiente','generando','fallida') "
    "AND contenido IS NULL AND tamano_bytes IS NULL "
    "AND generada_at IS NULL)"
)
_FALLIDA_CON_ERROR = "estado <> 'fallida' OR ultimo_error IS NOT NULL"
_TAMANO_POSITIVO = "tamano_bytes IS NULL OR tamano_bytes > 0"


class Exportacion(Base):
    """One export request and, once generated, its ZIP artifact (US-041)."""

    __tablename__ = "exportaciones"
    __table_args__ = (
        CheckConstraint(
            f"alcance IN ({_ALCANCES})", name="alcance_valido"
        ),
        CheckConstraint(f"estado IN ({_ESTADOS})", name="estado_valido"),
        CheckConstraint(
            _ALCANCE_PACIENTE_COHERENTE,
            name="alcance_paciente_coherente",
        ),
        CheckConstraint(_ESTADO_COHERENTE, name="estado_coherente"),
        CheckConstraint(_FALLIDA_CON_ERROR, name="fallida_con_error"),
        CheckConstraint(
            "intentos >= 0", name="intentos_no_negativos"
        ),
        CheckConstraint(_TAMANO_POSITIVO, name="tamano_positivo"),
        Index(
            "ix_exportaciones_estado_proximo",
            "estado",
            "proximo_intento",
        ),
        Index(
            "ix_exportaciones_consultorio_fecha",
            "consultorio_id",
            "created_at",
        ),
        Index("ix_exportaciones_paciente", "paciente_id"),
        Index(
            "uq_exportaciones_en_curso",
            "consultorio_id",
            "solicitado_por",
            "alcance",
            text(f"COALESCE(paciente_id, '{_UUID_NIL}'::uuid)"),
            unique=True,
            postgresql_where=text("estado IN ('pendiente','generando')"),
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
    solicitado_por: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    alcance: Mapped[str] = mapped_column(String(20), nullable=False)
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("pacientes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente",
        server_default=text("'pendiente'"),
    )
    contenido: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    tamano_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    generada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    intentos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    proximo_intento: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True
    )
    reclamado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
