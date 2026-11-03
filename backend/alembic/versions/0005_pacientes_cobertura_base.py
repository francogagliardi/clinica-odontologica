"""Patients and social-security agreements (C-05).

Hand-written for the same reason as 0004: autogenerate does not detect partial
unique indexes, expression indexes or CHECK constraints.

Revision ID: 0005_pacientes_cobertura_base
Revises: 0004_recursos_agendables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_pacientes_cobertura_base"
down_revision: str | None = "0004_recursos_agendables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_DNI_FORMATO = r"^[0-9]{7,8}$"
_TELEFONO_FORMATO = r"^\+549[0-9]{10}$"
_COBERTURA_COHERENTE = (
    "(obra_social_id IS NOT NULL) OR (nro_afiliado IS NULL)"
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
    op.create_table(
        "obras_sociales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("nomenclador_ref", sa.String(length=60), nullable=True),
        sa.Column(
            "reglas_cobertura",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "validacion_externa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint("btrim(nombre) <> ''", name="nombre_no_vacio"),
        sa.CheckConstraint(
            "jsonb_typeof(reglas_cobertura) = 'object'",
            name="reglas_objeto",
        ),
        sa.CheckConstraint(
            "NOT validacion_externa", name="sin_validacion_externa"
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_obras_sociales_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_obras_sociales"),
    )
    op.create_index(
        "uq_obras_sociales_nombre_activo",
        "obras_sociales",
        ["consultorio_id", sa.text("lower(nombre)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "pacientes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("apellido", sa.String(length=120), nullable=False),
        sa.Column("dni", sa.String(length=8), nullable=False),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("telefono", sa.String(length=16), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("obra_social_id", sa.Uuid(), nullable=True),
        sa.Column("nro_afiliado", sa.String(length=40), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"dni ~ '{_DNI_FORMATO}'", name="dni_formato"
        ),
        sa.CheckConstraint(
            f"telefono ~ '{_TELEFONO_FORMATO}'", name="telefono_formato"
        ),
        sa.CheckConstraint(
            _COBERTURA_COHERENTE, name="cobertura_coherente"
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_pacientes_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["obra_social_id"],
            ["obras_sociales.id"],
            name="fk_pacientes_obra_social_id_obras_sociales",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pacientes"),
    )
    op.create_index(
        "uq_pacientes_dni_activo",
        "pacientes",
        ["consultorio_id", "dni"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_pacientes_telefono", "pacientes", ["consultorio_id", "telefono"]
    )
    op.create_index(
        "ix_pacientes_apellido_lower",
        "pacientes",
        [sa.text("lower(apellido) text_pattern_ops")],
    )


def downgrade() -> None:
    op.drop_index("ix_pacientes_apellido_lower", table_name="pacientes")
    op.drop_index("ix_pacientes_telefono", table_name="pacientes")
    op.drop_index("uq_pacientes_dni_activo", table_name="pacientes")
    op.drop_table("pacientes")

    op.drop_index(
        "uq_obras_sociales_nombre_activo", table_name="obras_sociales"
    )
    op.drop_table("obras_sociales")
