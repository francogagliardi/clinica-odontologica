"""Clinical record models (C-11): history, evolutions, odontogram, attachments.

Design D3: the history is one per patient (partial unique index), evolutions are
drafts until signed and immutable afterwards, and the odontogram is a sequence
of complete snapshots. Snapshot tables (`odontogramas`, `hallazgos_dentales`)
deliberately do not inherit `AuditMixin`: they are append-only and protected by
triggers created in migration 0010, exactly like `registro_auditoria`.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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

# Mirrors app.domain.clinica.pieza_fdi_valida (permanent 11-48, temporary 51-85).
_PIEZA_FDI_VALIDA = (
    "((pieza / 10 BETWEEN 1 AND 4 AND pieza % 10 BETWEEN 1 AND 8) "
    "OR (pieza / 10 BETWEEN 5 AND 8 AND pieza % 10 BETWEEN 1 AND 5))"
)
_CARAS_VALIDAS = (
    "'mesial','distal','vestibular','lingual','oclusal','incisal','completa'"
)
_ESTADOS_VALIDOS = (
    "'sano','caries','obturacion','endodoncia','corona','implante','ausente',"
    "'extraccion_indicada','fractura','sellante','protesis'"
)
_CIE10_FORMATO = "^[A-Z][0-9]{2}(\\.[0-9]{1,2})?$"
_MIMES_PERMITIDOS = "'image/jpeg','image/png','image/webp','application/pdf'"
_NOMBRE_SANEADO = (
    "btrim(nombre) <> '' AND nombre NOT LIKE '%..%' "
    "AND nombre !~ '[/\\\\]'"
)
_TIPOS_CONSENTIMIENTO = "'procedimiento_invasivo'"
_HASH_HEX = "^[0-9a-f]{64}$"
_FIRMA_REF = "^sha256:[0-9a-f]{64}$"
MAX_ADJUNTO_BYTES = 5 * 1024 * 1024


class HistoriaClinica(Base, AuditMixin):
    """Patient clinical file: one active history per patient (design D3)."""

    __tablename__ = "historias_clinicas"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        Index(
            "uq_historias_clinicas_paciente_activa",
            "paciente_id",
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
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("pacientes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    abierta_por: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fecha_apertura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Evolucion(Base, AuditMixin):
    """Clinical evolution: editable draft, frozen once signed (RN-CL-04)."""

    __tablename__ = "evoluciones"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            "firmada = (firmada_por IS NOT NULL AND fecha_firma IS NOT NULL)",
            name="firma_coherente",
        ),
        CheckConstraint("btrim(texto) <> ''", name="texto_no_vacio"),
        Index(
            "uq_evoluciones_rectificacion_activa",
            "rectifica_a",
            unique=True,
            postgresql_where=text(
                "rectifica_a IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        Index("ix_evoluciones_historia_fecha", "historia_id", "fecha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    historia_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("historias_clinicas.id", ondelete="RESTRICT"),
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
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    firmada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    firmada_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    fecha_firma: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rectifica_a: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("evoluciones.id", ondelete="RESTRICT"),
        nullable=True,
    )


class Odontograma(Base):
    """Complete immutable snapshot of the dental state (design D6)."""

    __tablename__ = "odontogramas"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positiva"),
        UniqueConstraint(
            "historia_id",
            "version",
            name="uq_odontogramas_historia_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    historia_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("historias_clinicas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HallazgoDental(Base):
    """One finding per tooth/face inside a snapshot (RN-CL-01)."""

    __tablename__ = "hallazgos_dentales"
    __table_args__ = (
        CheckConstraint(_PIEZA_FDI_VALIDA, name="pieza_fdi_valida"),
        CheckConstraint(f"cara IN ({_CARAS_VALIDAS})", name="cara_valida"),
        CheckConstraint(f"estado IN ({_ESTADOS_VALIDOS})", name="estado_valido"),
        CheckConstraint(
            f"cie10 IS NULL OR cie10 ~ '{_CIE10_FORMATO}'",
            name="cie10_formato",
        ),
        UniqueConstraint(
            "odontograma_id",
            "pieza",
            "cara",
            name="uq_hallazgos_dentales_odontograma_pieza_cara",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    odontograma_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("odontogramas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pieza: Mapped[int] = mapped_column(Integer, nullable=False)
    cara: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    diagnostico: Mapped[str | None] = mapped_column(Text, nullable=True)
    cie10: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Adjunto(Base, AuditMixin):
    """Clinical attachment stored in PostgreSQL as BYTEA (design D7)."""

    __tablename__ = "adjuntos"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"mime IN ({_MIMES_PERMITIDOS})", name="mime_permitido"
        ),
        CheckConstraint(
            f"tamano > 0 AND tamano <= {MAX_ADJUNTO_BYTES}",
            name="tamano_valido",
        ),
        CheckConstraint(
            "tamano = octet_length(contenido)", name="tamano_coherente"
        ),
        CheckConstraint(_NOMBRE_SANEADO, name="nombre_saneado"),
        Index("ix_adjuntos_historia", "historia_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    historia_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("historias_clinicas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(60), nullable=False)
    tamano: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    subido_por: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )


class Consentimiento(Base, AuditMixin):
    """Versioned informed consent: append-only, hashes computed server-side."""

    __tablename__ = "consentimientos"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            f"tipo IN ({_TIPOS_CONSENTIMIENTO})", name="tipo_valido"
        ),
        CheckConstraint(f"texto_hash ~ '{_HASH_HEX}'", name="texto_hash_formato"),
        CheckConstraint(f"firma_ref ~ '{_FIRMA_REF}'", name="firma_ref_formato"),
        Index(
            "ix_consentimientos_paciente_fecha",
            "consultorio_id",
            "paciente_id",
            "fecha",
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
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    texto_version: Mapped[str] = mapped_column(String(20), nullable=False)
    texto_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    firma_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    registrado_por: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False,
    )
