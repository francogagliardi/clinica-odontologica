"""Agenda supply and commercial catalogue (C-04).

Hand-written for the same reason as 0002: autogenerate does not detect partial
unique indexes or CHECK constraints. Names follow the project convention and are
asserted by the migration tests.

Revision ID: 0004_recursos_agendables
Revises: 0003_tokens_un_solo_uso
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_recursos_agendables"
down_revision: str | None = "0003_tokens_un_solo_uso"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_DIAS_EN_RANGO = "dias_atencion <@ ARRAY[0,1,2,3,4,5,6]::integer[]"
_XOR_RECURSO = "(profesional_id IS NOT NULL) <> (sillon_id IS NOT NULL)"
_SENA_COHERENTE = (
    "(requiere_sena AND monto_sena IS NOT NULL AND monto_sena > 0) "
    "OR (NOT requiere_sena AND monto_sena IS NULL)"
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
        "profesionales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("matricula", sa.String(length=40), nullable=False),
        sa.Column(
            "especialidades",
            sa.ARRAY(sa.String(length=60)),
            nullable=False,
            server_default=sa.text("'{}'::character varying[]"),
        ),
        sa.Column("duracion_base_min", sa.Integer(), nullable=False),
        sa.Column(
            "dias_atencion", sa.ARRAY(sa.Integer()), nullable=False
        ),
        sa.Column("hora_desde", sa.Time(), nullable=False),
        sa.Column("hora_hasta", sa.Time(), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            "duracion_base_min > 0", name="duracion_base_positiva"
        ),
        sa.CheckConstraint("hora_hasta > hora_desde", name="horario_coherente"),
        sa.CheckConstraint(
            "cardinality(dias_atencion) > 0", name="dias_no_vacios"
        ),
        sa.CheckConstraint(_DIAS_EN_RANGO, name="dias_en_rango"),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_profesionales_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_profesionales_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profesionales"),
    )
    op.create_index(
        "uq_profesionales_matricula_activo",
        "profesionales",
        ["consultorio_id", "matricula"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_profesionales_usuario_activo",
        "profesionales",
        ["usuario_id"],
        unique=True,
        postgresql_where=sa.text(
            "usuario_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "ix_profesionales_consultorio", "profesionales", ["consultorio_id"]
    )

    op.create_table(
        "sillones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_sillones_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sillones"),
    )
    op.create_index(
        "uq_sillones_nombre_activo",
        "sillones",
        ["consultorio_id", "nombre"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "profesionales_sillones",
        sa.Column("profesional_id", sa.Uuid(), nullable=False),
        sa.Column("sillon_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesionales.id"],
            name="fk_profesionales_sillones_profesional_id_profesionales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sillon_id"],
            ["sillones.id"],
            name="fk_profesionales_sillones_sillon_id_sillones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "profesional_id", "sillon_id", name="pk_profesionales_sillones"
        ),
    )

    op.create_table(
        "prestaciones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("duracion_min", sa.Integer(), nullable=False),
        sa.Column("precio_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("especialidad", sa.String(length=60), nullable=True),
        sa.Column(
            "requiere_sena",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("monto_sena", sa.Numeric(12, 2), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint("duracion_min > 0", name="duracion_positiva"),
        sa.CheckConstraint("precio_base >= 0", name="precio_no_negativo"),
        sa.CheckConstraint(_SENA_COHERENTE, name="sena_coherente"),
        sa.PrimaryKeyConstraint("id", name="pk_prestaciones"),
    )
    op.create_index(
        "uq_prestaciones_codigo_activo",
        "prestaciones",
        ["codigo"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "bloqueos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profesional_id", sa.Uuid(), nullable=True),
        sa.Column("sillon_id", sa.Uuid(), nullable=True),
        sa.Column("desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.String(length=200), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(_XOR_RECURSO, name="recurso_exclusivo"),
        sa.CheckConstraint("hasta > desde", name="rango_coherente"),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesionales.id"],
            name="fk_bloqueos_profesional_id_profesionales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sillon_id"],
            ["sillones.id"],
            name="fk_bloqueos_sillon_id_sillones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bloqueos"),
    )
    op.create_index(
        "ix_bloqueos_profesional_desde", "bloqueos", ["profesional_id", "desde"]
    )
    op.create_index(
        "ix_bloqueos_sillon_desde", "bloqueos", ["sillon_id", "desde"]
    )


def downgrade() -> None:
    op.drop_index("ix_bloqueos_sillon_desde", table_name="bloqueos")
    op.drop_index("ix_bloqueos_profesional_desde", table_name="bloqueos")
    op.drop_table("bloqueos")

    op.drop_index("uq_prestaciones_codigo_activo", table_name="prestaciones")
    op.drop_table("prestaciones")

    op.drop_table("profesionales_sillones")

    op.drop_index("uq_sillones_nombre_activo", table_name="sillones")
    op.drop_table("sillones")

    op.drop_index(
        "uq_profesionales_usuario_activo", table_name="profesionales"
    )
    op.drop_index(
        "uq_profesionales_matricula_activo", table_name="profesionales"
    )
    op.drop_index("ix_profesionales_consultorio", table_name="profesionales")
    op.drop_table("profesionales")
