"""Billing receipts and ARCA issuance state (C-14, design D1/D2/D5/D12).

One row per approved payment holds both the internal receipt (own gapless
number, verifiable QR, emission date) and, once ARCA confirms, the fiscal data
(CAE, fiscal number, AFIP QR, fiscal timestamp). `estado` describes only the
fiscal situation: `pendiente` is a valid internal receipt whose invoice is
still queued.

PostgreSQL owns idempotency (D5):

- `uq_comprobantes_cobro` — one receipt per payment.
- `uq_comprobantes_numero_interno` — gapless internal numbering per point of sale.
- `uq_comprobantes_cae` — a CAE is never reused in the same environment.
- `uq_comprobantes_fiscal` — fiscal numbering is unique per point of sale.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_TIPOS_COMPROBANTE = "'B','C'"
_AMBIENTES = "'homologacion'"
_ESTADOS_FISCALES = "'pendiente','emitido','fallido'"
_CANALES_ENVIO = "'whatsapp'"
_ESTADOS_ENVIO = "'registrado','fallido'"
_CAE_FORMATO = "^[0-9]{14}$"

# D12: the fiscal state and its data change together, so a direct SQL write
# cannot leave an "emitted" receipt without a CAE or a pending one with one.
_ESTADO_FISCAL_COHERENTE = (
    "(estado = 'emitido' AND cae IS NOT NULL "
    "AND cae_vencimiento IS NOT NULL AND numero_fiscal IS NOT NULL "
    "AND qr_fiscal IS NOT NULL AND fecha_emision_fiscal IS NOT NULL) "
    "OR (estado IN ('pendiente','fallido') AND cae IS NULL "
    "AND cae_vencimiento IS NULL AND numero_fiscal IS NULL "
    "AND qr_fiscal IS NULL AND fecha_emision_fiscal IS NULL)"
)
_FALLIDO_CON_ERROR = "estado <> 'fallido' OR ultimo_error IS NOT NULL"


class Comprobante(Base, AuditMixin):
    """Internal receipt of a payment plus its fiscal state (US-031, RN-AD-01)."""

    __tablename__ = "comprobantes"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"tipo IN ({_TIPOS_COMPROBANTE})", name="tipo_valido"
        ),
        CheckConstraint(
            f"ambiente IN ({_AMBIENTES})", name="ambiente_valido"
        ),
        CheckConstraint(
            f"estado IN ({_ESTADOS_FISCALES})", name="estado_valido"
        ),
        CheckConstraint("numero_interno > 0", name="numero_interno_positivo"),
        CheckConstraint("punto_venta > 0", name="punto_venta_positivo"),
        CheckConstraint(
            "numero_fiscal IS NULL OR numero_fiscal > 0",
            name="numero_fiscal_positivo",
        ),
        CheckConstraint("importe_total > 0", name="importe_positivo"),
        CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        CheckConstraint(
            f"cae IS NULL OR cae ~ '{_CAE_FORMATO}'", name="cae_formato"
        ),
        CheckConstraint(
            _ESTADO_FISCAL_COHERENTE, name="estado_fiscal_coherente"
        ),
        CheckConstraint(_FALLIDO_CON_ERROR, name="fallido_con_error"),
        Index(
            "uq_comprobantes_cobro",
            "cobro_id",
            unique=True,
        ),
        Index(
            "uq_comprobantes_numero_interno",
            "consultorio_id",
            "punto_venta",
            "numero_interno",
            unique=True,
        ),
        Index(
            "uq_comprobantes_cae",
            "ambiente",
            "cae",
            unique=True,
            postgresql_where=text("cae IS NOT NULL"),
        ),
        Index(
            "uq_comprobantes_fiscal",
            "ambiente",
            "punto_venta",
            "numero_fiscal",
            unique=True,
            postgresql_where=text("numero_fiscal IS NOT NULL"),
        ),
        Index(
            "ix_comprobantes_estado_proximo", "estado", "proximo_intento"
        ),
        Index("ix_comprobantes_paciente", "paciente_id"),
        Index("ix_comprobantes_fecha", "consultorio_id", "fecha_emision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    consultorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("consultorios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cobro_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cobros.id", ondelete="RESTRICT"),
        nullable=False,
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("pacientes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(1), nullable=False)
    ambiente: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="homologacion",
        server_default=text("'homologacion'"),
    )
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente",
        server_default=text("'pendiente'"),
    )
    numero_interno: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    punto_venta: Mapped[int] = mapped_column(Integer, nullable=False)
    numero_fiscal: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    cae: Mapped[str | None] = mapped_column(String(14), nullable=True)
    cae_vencimiento: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    qr_interno: Mapped[str] = mapped_column(Text, nullable=False)
    qr_fiscal: Mapped[str | None] = mapped_column(Text, nullable=True)
    receptor_nombre: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    receptor_documento: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    receptor_tipo_documento: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="DNI",
        server_default=text("'DNI'"),
    )
    condicion_fiscal_receptor: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="consumidor_final",
        server_default=text("'consumidor_final'"),
    )
    condicion_fiscal_emisor: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    importe_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    fecha_emision: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_emision_fiscal: Mapped[datetime | None] = mapped_column(
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
    payload_envio: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )
    respuesta_proveedor: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )


class ComprobanteEnvio(Base, AuditMixin):
    """Simulated invoice delivery, one live row per receipt and channel (D10)."""

    __tablename__ = "comprobantes_envios"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"canal IN ({_CANALES_ENVIO})", name="canal_valido"
        ),
        CheckConstraint(
            f"estado IN ({_ESTADOS_ENVIO})", name="estado_valido"
        ),
        CheckConstraint("btrim(destino) <> ''", name="destino_no_vacio"),
        Index(
            "uq_comprobantes_envios_comprobante_canal",
            "comprobante_id",
            "canal",
            unique=True,
        ),
        Index("ix_comprobantes_envios_comprobante", "comprobante_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    comprobante_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("comprobantes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    destino: Mapped[str] = mapped_column(String(120), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="registrado",
        server_default=text("'registrado'"),
    )
    proveedor_mensaje_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )


class SecuenciaComprobante(Base):
    """Gapless internal and fiscal counters per consultorio and POS (D2).

    No audit columns and no soft delete: it is a counter row, and the
    `UPDATE ... RETURNING` inside the caller's transaction is what guarantees
    that a rolled-back receipt does not consume a number.
    """

    __tablename__ = "secuencias_comprobantes"
    __table_args__ = (
        CheckConstraint("punto_venta > 0", name="punto_venta_positivo"),
        CheckConstraint(
            "ultimo_interno >= 0 AND ultimo_fiscal >= 0",
            name="contadores_no_negativos",
        ),
    )

    consultorio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("consultorios.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    punto_venta: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo_interno: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    ultimo_fiscal: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
