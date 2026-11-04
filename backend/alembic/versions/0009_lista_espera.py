"""Waiting list with atomic retention of a freed slot (C-10).

The retention is protected by two partial GiST exclusion constraints, written
as SQL because Alembic autogenerate does not emit `EXCLUDE USING gist`. The
offer message has no appointment yet, so `mensajes_whatsapp.turno_id` becomes
nullable and gains an optional `lista_espera_id`.

Revision ID: 0009_lista_espera
Revises: 0008_whatsapp_recordatorios
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_lista_espera"
down_revision: str | None = "0008_whatsapp_recordatorios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_ESTADOS = "'pendiente','ofrecido','convertido','vencido'"
_OFERTA_COMPLETA = (
    "estado <> 'ofrecido' OR ("
    "oferta_inicio IS NOT NULL "
    "AND oferta_fin > oferta_inicio "
    "AND oferta_profesional_id IS NOT NULL "
    "AND oferta_sillon_id IS NOT NULL "
    "AND oferta_expira_en IS NOT NULL)"
)
_SIN_RETENCION_FUERA_DE_OFERTA = (
    "estado = 'ofrecido' OR ("
    "oferta_inicio IS NULL "
    "AND oferta_fin IS NULL "
    "AND oferta_profesional_id IS NULL "
    "AND oferta_sillon_id IS NULL "
    "AND oferta_expira_en IS NULL)"
)
_PREDICADO_RETENCION = "estado = 'ofrecido' AND deleted_at IS NULL"
_SIN_PROFESIONAL = "'00000000-0000-0000-0000-000000000000'::uuid"
_RESPUESTAS = (
    "'ninguna','confirmado','cancelado','reprogramado','derivado',"
    "'aceptado','rechazado'"
)
_RESPUESTAS_ANTERIORES = (
    "'ninguna','confirmado','cancelado','reprogramado','derivado'"
)
_INDICES_LISTA_ESPERA = (
    "ix_entradas_lista_espera_cola",
    "ix_entradas_lista_espera_prestacion",
    "ix_entradas_lista_espera_vencimiento",
    "ix_entradas_lista_espera_retencion_profesional",
    "ix_entradas_lista_espera_retencion_sillon",
    "uq_entradas_lista_espera_pendiente",
    "uq_entradas_lista_espera_turno",
)


def _audit_columns() -> list[sa.Column]:
    """Columns shared by business entities (mirrors AuditMixin)."""
    return [
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "entradas_lista_espera",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("prestacion_id", sa.Uuid(), nullable=False),
        sa.Column("profesional_id", sa.Uuid(), nullable=True),
        sa.Column(
            "orden",
            sa.BigInteger(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column("oferta_profesional_id", sa.Uuid(), nullable=True),
        sa.Column("oferta_sillon_id", sa.Uuid(), nullable=True),
        sa.Column(
            "oferta_inicio", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("oferta_fin", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "oferta_expira_en", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("turno_id", sa.Uuid(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(f"estado IN ({_ESTADOS})", name="estado_valido"),
        sa.CheckConstraint(_OFERTA_COMPLETA, name="oferta_completa"),
        sa.CheckConstraint(
            "estado <> 'convertido' OR turno_id IS NOT NULL",
            name="conversion_con_turno",
        ),
        sa.CheckConstraint(
            _SIN_RETENCION_FUERA_DE_OFERTA,
            name="sin_retencion_fuera_de_oferta",
        ),
        sa.UniqueConstraint("orden", name="uq_entradas_lista_espera_orden"),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_entradas_lista_espera_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_entradas_lista_espera_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prestacion_id"],
            ["prestaciones.id"],
            name="fk_entradas_lista_espera_prestacion_id_prestaciones",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesionales.id"],
            name="fk_entradas_lista_espera_profesional_id_profesionales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["oferta_profesional_id"],
            ["profesionales.id"],
            name=(
                "fk_entradas_lista_espera_oferta_profesional_id_profesionales"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["oferta_sillon_id"],
            ["sillones.id"],
            name="fk_entradas_lista_espera_oferta_sillon_id_sillones",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["turno_id"],
            ["turnos.id"],
            name="fk_entradas_lista_espera_turno_id_turnos",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entradas_lista_espera"),
    )
    op.create_index(
        "ix_entradas_lista_espera_cola",
        "entradas_lista_espera",
        ["consultorio_id", "estado", "orden"],
    )
    op.create_index(
        "ix_entradas_lista_espera_prestacion",
        "entradas_lista_espera",
        ["prestacion_id", "estado", "orden"],
    )
    op.create_index(
        "ix_entradas_lista_espera_vencimiento",
        "entradas_lista_espera",
        ["estado", "oferta_expira_en"],
    )
    op.create_index(
        "ix_entradas_lista_espera_retencion_profesional",
        "entradas_lista_espera",
        ["oferta_profesional_id", "oferta_inicio"],
    )
    op.create_index(
        "ix_entradas_lista_espera_retencion_sillon",
        "entradas_lista_espera",
        ["oferta_sillon_id", "oferta_inicio"],
    )
    op.create_index(
        "uq_entradas_lista_espera_pendiente",
        "entradas_lista_espera",
        [
            "paciente_id",
            "prestacion_id",
            sa.text(f"coalesce(profesional_id, {_SIN_PROFESIONAL})"),
        ],
        unique=True,
        postgresql_where=sa.text(
            "estado = 'pendiente' AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "uq_entradas_lista_espera_turno",
        "entradas_lista_espera",
        ["turno_id"],
        unique=True,
        postgresql_where=sa.text("turno_id IS NOT NULL"),
    )

    op.execute(
        "ALTER TABLE entradas_lista_espera "
        "ADD CONSTRAINT ex_lista_espera_profesional "
        "EXCLUDE USING gist ("
        "oferta_profesional_id WITH =, "
        "tstzrange(oferta_inicio, oferta_fin, '[)') WITH &&"
        f") WHERE ({_PREDICADO_RETENCION})"
    )
    op.execute(
        "ALTER TABLE entradas_lista_espera "
        "ADD CONSTRAINT ex_lista_espera_sillon "
        "EXCLUDE USING gist ("
        "oferta_sillon_id WITH =, "
        "tstzrange(oferta_inicio, oferta_fin, '[)') WITH &&"
        f") WHERE ({_PREDICADO_RETENCION})"
    )

    # An offer message exists before any appointment: nullable turn plus link.
    op.alter_column(
        "mensajes_whatsapp",
        "turno_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.add_column(
        "mensajes_whatsapp",
        sa.Column("lista_espera_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_mensajes_whatsapp_lista_espera_id_entradas_lista_espera",
        "mensajes_whatsapp",
        "entradas_lista_espera",
        ["lista_espera_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_mensajes_whatsapp_lista_espera",
        "mensajes_whatsapp",
        ["lista_espera_id"],
    )
    op.execute(
        "ALTER TABLE mensajes_whatsapp "
        "DROP CONSTRAINT IF EXISTS ck_mensajes_whatsapp_respuesta_valida"
    )
    op.create_check_constraint(
        "respuesta_valida",
        "mensajes_whatsapp",
        f"respuesta IN ({_RESPUESTAS})",
    )
    op.create_check_constraint(
        "turno_o_lista_espera",
        "mensajes_whatsapp",
        "turno_id IS NOT NULL OR lista_espera_id IS NOT NULL",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE mensajes_whatsapp "
        "DROP CONSTRAINT IF EXISTS ck_mensajes_whatsapp_turno_o_lista_espera"
    )
    op.execute(
        "ALTER TABLE mensajes_whatsapp "
        "DROP CONSTRAINT IF EXISTS ck_mensajes_whatsapp_respuesta_valida"
    )
    op.drop_index(
        "ix_mensajes_whatsapp_lista_espera", table_name="mensajes_whatsapp"
    )
    op.drop_constraint(
        "fk_mensajes_whatsapp_lista_espera_id_entradas_lista_espera",
        "mensajes_whatsapp",
        type_="foreignkey",
    )
    op.drop_column("mensajes_whatsapp", "lista_espera_id")
    # Offer messages have no appointment; they cannot survive a NOT NULL turn.
    op.execute("DELETE FROM mensajes_whatsapp WHERE turno_id IS NULL")
    op.alter_column(
        "mensajes_whatsapp",
        "turno_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_check_constraint(
        "respuesta_valida",
        "mensajes_whatsapp",
        f"respuesta IN ({_RESPUESTAS_ANTERIORES})",
    )

    op.execute(
        "ALTER TABLE entradas_lista_espera "
        "DROP CONSTRAINT IF EXISTS ex_lista_espera_sillon"
    )
    op.execute(
        "ALTER TABLE entradas_lista_espera "
        "DROP CONSTRAINT IF EXISTS ex_lista_espera_profesional"
    )
    for _indice in _INDICES_LISTA_ESPERA:
        op.drop_index(_indice, table_name="entradas_lista_espera")
    op.drop_table("entradas_lista_espera")
    # `btree_gist` is intentionally kept: other schemas may depend on it.
