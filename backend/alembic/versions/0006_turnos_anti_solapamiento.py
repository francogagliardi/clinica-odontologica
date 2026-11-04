"""Appointments with database-level anti-overlap (C-06).

The exclusion constraints are written as SQL because Alembic autogenerate does
not emit `EXCLUDE USING gist`. `btree_gist` lets a GiST index combine UUID
equality with time-range overlap.

Revision ID: 0006_turnos_anti_solapamiento
Revises: 0005_pacientes_cobertura_base
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_turnos_anti_solapamiento"
down_revision: str | None = "0005_pacientes_cobertura_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_ESTADOS = "'reservado','confirmado','en_sala','atendido','cancelado','ausente'"
_ORIGENES = "'recepcion','online','whatsapp'"
_ESTADOS_ACTIVOS = "'reservado','confirmado','en_sala','atendido'"
_PREDICADO_EXCLUSION = (
    "deleted_at IS NULL AND NOT es_sobreturno "
    f"AND estado IN ({_ESTADOS_ACTIVOS})"
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

    op.add_column(
        "consultorios",
        sa.Column(
            "plazo_cancelacion_horas",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("24"),
        ),
    )
    op.create_check_constraint(
        "plazo_cancelacion_valido",
        "consultorios",
        "plazo_cancelacion_horas BETWEEN 0 AND 720",
    )

    op.create_table(
        "turnos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("profesional_id", sa.Uuid(), nullable=False),
        sa.Column("sillon_id", sa.Uuid(), nullable=False),
        sa.Column("prestacion_id", sa.Uuid(), nullable=True),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'reservado'"),
        ),
        sa.Column(
            "origen",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'recepcion'"),
        ),
        sa.Column(
            "es_sobreturno",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("color_sobreturno", sa.String(length=7), nullable=True),
        sa.Column("token_publico", sa.String(length=64), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint("fin > inicio", name="rango_coherente"),
        sa.CheckConstraint(f"estado IN ({_ESTADOS})", name="estado_valido"),
        sa.CheckConstraint(f"origen IN ({_ORIGENES})", name="origen_valido"),
        sa.CheckConstraint(
            "es_sobreturno = (color_sobreturno IS NOT NULL)",
            name="sobreturno_coherente",
        ),
        sa.CheckConstraint(
            "color_sobreturno IS NULL "
            "OR color_sobreturno ~ '^#[0-9A-Fa-f]{6}$'",
            name="color_sobreturno_formato",
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_turnos_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_turnos_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesionales.id"],
            name="fk_turnos_profesional_id_profesionales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sillon_id"],
            ["sillones.id"],
            name="fk_turnos_sillon_id_sillones",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prestacion_id"],
            ["prestaciones.id"],
            name="fk_turnos_prestacion_id_prestaciones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_turnos"),
    )
    op.create_index(
        "ix_turnos_profesional_inicio", "turnos", ["profesional_id", "inicio"]
    )
    op.create_index(
        "ix_turnos_sillon_inicio", "turnos", ["sillon_id", "inicio"]
    )
    op.create_index("ix_turnos_estado", "turnos", ["estado"])
    op.create_index(
        "uq_turnos_token_publico",
        "turnos",
        ["token_publico"],
        unique=True,
        postgresql_where=sa.text("token_publico IS NOT NULL"),
    )

    op.execute(
        "ALTER TABLE turnos ADD CONSTRAINT ex_turnos_profesional "
        "EXCLUDE USING gist ("
        "profesional_id WITH =, "
        "tstzrange(inicio, fin, '[)') WITH &&"
        f") WHERE ({_PREDICADO_EXCLUSION})"
    )
    op.execute(
        "ALTER TABLE turnos ADD CONSTRAINT ex_turnos_sillon "
        "EXCLUDE USING gist ("
        "sillon_id WITH =, "
        "tstzrange(inicio, fin, '[)') WITH &&"
        f") WHERE ({_PREDICADO_EXCLUSION})"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE turnos DROP CONSTRAINT IF EXISTS ex_turnos_sillon"
    )
    op.execute(
        "ALTER TABLE turnos DROP CONSTRAINT IF EXISTS ex_turnos_profesional"
    )
    op.drop_index("uq_turnos_token_publico", table_name="turnos")
    op.drop_index("ix_turnos_estado", table_name="turnos")
    op.drop_index("ix_turnos_sillon_inicio", table_name="turnos")
    op.drop_index("ix_turnos_profesional_inicio", table_name="turnos")
    op.drop_table("turnos")

    op.execute(
        "ALTER TABLE consultorios "
        "DROP CONSTRAINT IF EXISTS ck_consultorios_plazo_cancelacion_valido"
    )
    op.drop_column("consultorios", "plazo_cancelacion_horas")
    # `btree_gist` is intentionally kept: other schemas may depend on it.
