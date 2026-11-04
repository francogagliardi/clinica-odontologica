"""Messaging models: reminders and WhatsApp messages (C-09).

PostgreSQL is the source of truth (R-06): Redis only holds queue jobs. A
reminder is unique per appointment/window so a retried booking cannot duplicate
it, and every provider message id is unique to make the webhook idempotent.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_ESTADOS_RECORDATORIO = (
    "'pendiente','encolado','enviado','fallido','cancelado'"
)
_ESTADOS_ENVIO = "'pendiente','enviado','fallido'"
_RESPUESTAS = (
    "'ninguna','confirmado','cancelado','reprogramado','derivado',"
    "'aceptado','rechazado'"
)
_PLANTILLAS = "'recordatorio','confirmacion','oferta_hueco'"


class Recordatorio(Base):
    """48h/24h reminder persisted before any queue interaction."""

    __tablename__ = "recordatorios"
    __table_args__ = (
        CheckConstraint("ventana IN ('48h','24h')", name="ventana_valida"),
        CheckConstraint(
            f"estado IN ({_ESTADOS_RECORDATORIO})", name="estado_valido"
        ),
        Index(
            "uq_recordatorios_turno_ventana",
            "turno_id",
            "ventana",
            unique=True,
        ),
        Index("ix_recordatorios_estado_programado", "estado", "programado_para"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("turnos.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ventana: Mapped[str] = mapped_column(String(3), nullable=False)
    programado_para: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente",
        server_default=text("'pendiente'"),
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


class MensajeWhatsApp(Base):
    """Outbound message with delivery state, retries and inbound response."""

    __tablename__ = "mensajes_whatsapp"
    __table_args__ = (
        CheckConstraint(
            f"plantilla IN ({_PLANTILLAS})", name="plantilla_valida"
        ),
        CheckConstraint(
            f"estado_envio IN ({_ESTADOS_ENVIO})", name="estado_envio_valido"
        ),
        CheckConstraint(
            f"respuesta IN ({_RESPUESTAS})", name="respuesta_valida"
        ),
        CheckConstraint(
            "turno_id IS NOT NULL OR lista_espera_id IS NOT NULL",
            name="turno_o_lista_espera",
        ),
        Index(
            "uq_mensajes_whatsapp_proveedor",
            "proveedor_mensaje_id",
            unique=True,
            postgresql_where=text("proveedor_mensaje_id IS NOT NULL"),
        ),
        Index(
            "ix_mensajes_whatsapp_estado_proximo",
            "estado_envio",
            "proximo_intento",
        ),
        Index("ix_mensajes_whatsapp_turno", "turno_id"),
        Index("ix_mensajes_whatsapp_lista_espera", "lista_espera_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    recordatorio_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("recordatorios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("turnos.id", ondelete="RESTRICT"),
        nullable=True,
    )
    lista_espera_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("entradas_lista_espera.id", ondelete="RESTRICT"),
        nullable=True,
    )
    plantilla: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_envio: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente",
        server_default=text("'pendiente'"),
    )
    respuesta: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ninguna",
        server_default=text("'ninguna'"),
    )
    proveedor_mensaje_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    intentos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    proximo_intento: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
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
