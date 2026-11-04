"""Reminders and WhatsApp messages (C-09).

Revision ID: 0008_whatsapp_recordatorios
Revises: 0007_reserva_publica
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_whatsapp_recordatorios"
down_revision: str | None = "0007_reserva_publica"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESTADOS_RECORDATORIO = (
    "'pendiente','encolado','enviado','fallido','cancelado'"
)
_ESTADOS_ENVIO = "'pendiente','enviado','fallido'"
_RESPUESTAS = "'ninguna','confirmado','cancelado','reprogramado','derivado'"
_PLANTILLAS = "'recordatorio','confirmacion','oferta_hueco'"


def upgrade() -> None:
    op.create_table(
        "recordatorios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("turno_id", sa.Uuid(), nullable=False),
        sa.Column("ventana", sa.String(length=3), nullable=False),
        sa.Column(
            "programado_para", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "ventana IN ('48h','24h')", name="ventana_valida"
        ),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_RECORDATORIO})", name="estado_valido"
        ),
        sa.ForeignKeyConstraint(
            ["turno_id"],
            ["turnos.id"],
            name="fk_recordatorios_turno_id_turnos",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_recordatorios"),
    )
    op.create_index(
        "uq_recordatorios_turno_ventana",
        "recordatorios",
        ["turno_id", "ventana"],
        unique=True,
    )
    op.create_index(
        "ix_recordatorios_estado_programado",
        "recordatorios",
        ["estado", "programado_para"],
    )

    op.create_table(
        "mensajes_whatsapp",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recordatorio_id", sa.Uuid(), nullable=True),
        sa.Column("turno_id", sa.Uuid(), nullable=False),
        sa.Column("plantilla", sa.String(length=20), nullable=False),
        sa.Column(
            "estado_envio",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column(
            "respuesta",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ninguna'"),
        ),
        sa.Column("proveedor_mensaje_id", sa.String(length=80), nullable=True),
        sa.Column(
            "intentos",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "proximo_intento", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"plantilla IN ({_PLANTILLAS})", name="plantilla_valida"
        ),
        sa.CheckConstraint(
            f"estado_envio IN ({_ESTADOS_ENVIO})", name="estado_envio_valido"
        ),
        sa.CheckConstraint(
            f"respuesta IN ({_RESPUESTAS})", name="respuesta_valida"
        ),
        sa.ForeignKeyConstraint(
            ["recordatorio_id"],
            ["recordatorios.id"],
            name="fk_mensajes_whatsapp_recordatorio_id_recordatorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["turno_id"],
            ["turnos.id"],
            name="fk_mensajes_whatsapp_turno_id_turnos",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mensajes_whatsapp"),
    )
    op.create_index(
        "uq_mensajes_whatsapp_proveedor",
        "mensajes_whatsapp",
        ["proveedor_mensaje_id"],
        unique=True,
        postgresql_where=sa.text("proveedor_mensaje_id IS NOT NULL"),
    )
    op.create_index(
        "ix_mensajes_whatsapp_estado_proximo",
        "mensajes_whatsapp",
        ["estado_envio", "proximo_intento"],
    )
    op.create_index(
        "ix_mensajes_whatsapp_turno", "mensajes_whatsapp", ["turno_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mensajes_whatsapp_turno", table_name="mensajes_whatsapp"
    )
    op.drop_index(
        "ix_mensajes_whatsapp_estado_proximo",
        table_name="mensajes_whatsapp",
    )
    op.drop_index(
        "uq_mensajes_whatsapp_proveedor", table_name="mensajes_whatsapp"
    )
    op.drop_table("mensajes_whatsapp")

    op.drop_index(
        "ix_recordatorios_estado_programado", table_name="recordatorios"
    )
    op.drop_index(
        "uq_recordatorios_turno_ventana", table_name="recordatorios"
    )
    op.drop_table("recordatorios")
