"""Security and identity models (C-02).

UUID v4 primary keys generated in the application (never exposed sequences),
partial unique indexes that only apply to active rows (a soft-deleted value can
be reused), a composite-PK role link that tolerates repeated assignment, and an
append-only audit table protected in PostgreSQL (RN-SE-02).
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
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"


class Consultorio(Base, AuditMixin):
    """Tenant root: the clinic/consultorio the rest of the domain hangs from."""

    __tablename__ = "consultorios"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        CheckConstraint(
            "plazo_cancelacion_horas BETWEEN 0 AND 720",
            name="plazo_cancelacion_valido",
        ),
        Index(
            "uq_consultorios_slug_activo",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    plazo_cancelacion_horas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
        server_default=text("24"),
    )


class Rol(Base, AuditMixin):
    """Role catalogue (global in v1: one set of roles for the deployment)."""

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        Index(
            "uq_roles_nombre_activo",
            "nombre",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)


class UsuarioRol(Base):
    """Usuario ↔ Rol link: composite PK makes repeated assignment harmless."""

    __tablename__ = "usuario_roles"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    rol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class Usuario(Base, AuditMixin):
    """Person who can authenticate in the backoffice (login lands in C-03)."""

    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        Index(
            "uq_usuarios_email_activo",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hash_password: Mapped[str] = mapped_column(String(255), nullable=False)

    roles: Mapped[list[Rol]] = relationship(
        secondary="usuario_roles", lazy="selectin"
    )


class RegistroAuditoria(Base):
    """Append-only trace: who did what, when (RN-SE-02).

    Deliberately has no `AuditMixin`: no updated_at, no deleted_at. PostgreSQL
    triggers reject UPDATE/DELETE (per row) and TRUNCATE (per statement).
    `usuario_id` is nullable because system/bot actors are not people.
    """

    __tablename__ = "registro_auditoria"
    __table_args__ = (
        Index("ix_registro_auditoria_usuario_timestamp", "usuario_id", "timestamp"),
        Index("ix_registro_auditoria_entidad", "entidad", "entidad_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=True,
    )
    accion: Mapped[str] = mapped_column(String(120), nullable=False)
    entidad: Mapped[str] = mapped_column(String(60), nullable=False)
    entidad_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    dispositivo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
