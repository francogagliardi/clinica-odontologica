"""Exportation jobs and their durable ZIP artifact (C-15, design D3/D7/D12).

Hand-written because Alembic autogenerate does not emit the portable expression
index (`COALESCE(paciente_id, uuid_nil)`) nor the partial predicate that keeps
one identical exportation in progress. Only `exportaciones` is created; no
C-01..C-14 table is altered and there is no backfill.

Invariants and the object that covers each one:

- `alcance` and `paciente_id` agree → `ck_exportaciones_alcance_paciente_coherente`.
- `lista` carries its artifact and the other states forbid it
  → `ck_exportaciones_estado_coherente`.
- A failed exportation explains why → `ck_exportaciones_fallida_con_error`.
- Retries and artifact size stay non-negative/positive
  → `ck_exportaciones_intentos_no_negativos`, `ck_exportaciones_tamano_positivo`.
- One identical job in progress per tenant/requester/scope
  → `uq_exportaciones_en_curso` (partial unique, D7).

Downgrade drops the table and its indexes; it does not touch the domain tables.

Revision ID: 0014_reportes
Revises: 0013_facturacion_arca
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_reportes"
down_revision: str | None = "0013_facturacion_arca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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


def upgrade() -> None:
    op.create_table(
        "exportaciones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("solicitado_por", sa.Uuid(), nullable=False),
        sa.Column("alcance", sa.String(length=20), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=True),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column("contenido", sa.LargeBinary(), nullable=True),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "generada_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "intentos",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "proximo_intento",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column(
            "reclamado_at", sa.DateTime(timezone=True), nullable=True
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
            f"alcance IN ({_ALCANCES})", name="alcance_valido"
        ),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS})", name="estado_valido"
        ),
        sa.CheckConstraint(
            _ALCANCE_PACIENTE_COHERENTE,
            name="alcance_paciente_coherente",
        ),
        sa.CheckConstraint(_ESTADO_COHERENTE, name="estado_coherente"),
        sa.CheckConstraint(
            "estado <> 'fallida' OR ultimo_error IS NOT NULL",
            name="fallida_con_error",
        ),
        sa.CheckConstraint(
            "intentos >= 0", name="intentos_no_negativos"
        ),
        sa.CheckConstraint(
            "tamano_bytes IS NULL OR tamano_bytes > 0",
            name="tamano_positivo",
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_exportaciones_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["solicitado_por"],
            ["usuarios.id"],
            name="fk_exportaciones_solicitado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_exportaciones_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exportaciones"),
    )
    op.create_index(
        "ix_exportaciones_estado_proximo",
        "exportaciones",
        ["estado", "proximo_intento"],
    )
    op.create_index(
        "ix_exportaciones_consultorio_fecha",
        "exportaciones",
        ["consultorio_id", "created_at"],
    )
    op.create_index(
        "ix_exportaciones_paciente", "exportaciones", ["paciente_id"]
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_exportaciones_en_curso "
        "ON exportaciones (consultorio_id, solicitado_por, alcance, "
        f"COALESCE(paciente_id, '{_UUID_NIL}'::uuid)) "
        "WHERE estado IN ('pendiente','generando')"
    )


def downgrade() -> None:
    op.drop_index(
        "uq_exportaciones_en_curso", table_name="exportaciones"
    )
    op.drop_index(
        "ix_exportaciones_paciente", table_name="exportaciones"
    )
    op.drop_index(
        "ix_exportaciones_consultorio_fecha", table_name="exportaciones"
    )
    op.drop_index(
        "ix_exportaciones_estado_proximo", table_name="exportaciones"
    )
    op.drop_table("exportaciones")
