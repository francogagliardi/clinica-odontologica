"""Budgets and their lines (C-12).

Hand-written because Alembic autogenerate does not emit the FDI CHECK formula
nor the money-coherence CHECKs that mirror `app.domain.presupuestos` (design
D2/D3). This revision only creates `presupuestos` and `items_presupuesto`; it
does not alter any table created by C-01..C-11.

Invariants and the CHECK that covers each one:

- `presupuestos.estado` belongs to the catalogue
  → `ck_presupuestos_estado_valido`.
- `presupuestos.cobertura_estado` belongs to the coverage catalogue
  → `ck_presupuestos_cobertura_estado_valido`.
- No negative amount in the header
  → `ck_presupuestos_importes_no_negativos`.
- Header totals add up (`subtotal = cobertura_calculada + copago`)
  → `ck_presupuestos_totales_coherentes`.
- Soft delete is coherent (`deleted_at IS NULL` ⇔ `is_active`)
  → `ck_presupuestos_baja_logica_coherente`.
- `items_presupuesto.cantidad > 0`
  → `ck_items_presupuesto_cantidad_positiva`.
- No negative amount in a line
  → `ck_items_presupuesto_importes_no_negativos`.
- Line totals add up
  (`cobertura_item + copago_item = precio_unitario * cantidad`)
  → `ck_items_presupuesto_totales_item_coherentes`.
- Optional tooth is a real FDI tooth (19/49/86 are rejected)
  → `ck_items_presupuesto_pieza_fdi_valida`.
- Soft delete is coherent on a line
  → `ck_items_presupuesto_baja_logica_coherente`.

The cross-table invariant (`subtotal` equals the sum of active lines) cannot
be expressed as a CHECK; the service always derives the three totals from the
lines in the same transaction and integration tests compare both sides.

Downgrade order: `items_presupuesto` first (it references `presupuestos`),
then `presupuestos`, so the FKs never block the rollback.

Revision ID: 0011_presupuestos
Revises: 0010_historia_clinica
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_presupuestos"
down_revision: str | None = "0010_historia_clinica"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_ESTADOS_PRESUPUESTO = (
    "'borrador','aceptado','rechazado','en_curso','finalizado'"
)
_ESTADOS_COBERTURA = "'calculada','pendiente_verificacion'"
_PIEZA_FDI_VALIDA = (
    "((pieza / 10 BETWEEN 1 AND 4 AND pieza % 10 BETWEEN 1 AND 8) "
    "OR (pieza / 10 BETWEEN 5 AND 8 AND pieza % 10 BETWEEN 1 AND 5))"
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
        "presupuestos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("profesional_id", sa.Uuid(), nullable=False),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'borrador'"),
        ),
        sa.Column(
            "cobertura_estado",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'calculada'"),
        ),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "cobertura_calculada", sa.Numeric(12, 2), nullable=False
        ),
        sa.Column("copago", sa.Numeric(12, 2), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_PRESUPUESTO})", name="estado_valido"
        ),
        sa.CheckConstraint(
            f"cobertura_estado IN ({_ESTADOS_COBERTURA})",
            name="cobertura_estado_valido",
        ),
        sa.CheckConstraint(
            "subtotal >= 0 AND cobertura_calculada >= 0 AND copago >= 0",
            name="importes_no_negativos",
        ),
        sa.CheckConstraint(
            "subtotal = cobertura_calculada + copago",
            name="totales_coherentes",
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_presupuestos_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_presupuestos_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profesional_id"],
            ["profesionales.id"],
            name="fk_presupuestos_profesional_id_profesionales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_presupuestos_creado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_presupuestos"),
    )
    op.create_index(
        "ix_presupuestos_paciente_created",
        "presupuestos",
        ["consultorio_id", "paciente_id", "created_at"],
    )
    op.create_index(
        "ix_presupuestos_profesional_estado",
        "presupuestos",
        ["profesional_id", "estado"],
    )

    op.create_table(
        "items_presupuesto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("presupuesto_id", sa.Uuid(), nullable=False),
        sa.Column("prestacion_id", sa.Uuid(), nullable=False),
        sa.Column("pieza", sa.Integer(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("cobertura_item", sa.Numeric(12, 2), nullable=False),
        sa.Column("copago_item", sa.Numeric(12, 2), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        sa.CheckConstraint(
            "precio_unitario >= 0 AND cobertura_item >= 0 "
            "AND copago_item >= 0",
            name="importes_no_negativos",
        ),
        sa.CheckConstraint(
            "cobertura_item + copago_item = precio_unitario * cantidad",
            name="totales_item_coherentes",
        ),
        sa.CheckConstraint(
            f"pieza IS NULL OR {_PIEZA_FDI_VALIDA}",
            name="pieza_fdi_valida",
        ),
        sa.ForeignKeyConstraint(
            ["presupuesto_id"],
            ["presupuestos.id"],
            name="fk_items_presupuesto_presupuesto_id_presupuestos",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prestacion_id"],
            ["prestaciones.id"],
            name="fk_items_presupuesto_prestacion_id_prestaciones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_items_presupuesto"),
    )
    op.create_index(
        "ix_items_presupuesto_presupuesto",
        "items_presupuesto",
        ["presupuesto_id"],
    )


def downgrade() -> None:
    # Reverse order: the lines reference the header.
    op.drop_index(
        "ix_items_presupuesto_presupuesto", table_name="items_presupuesto"
    )
    op.drop_table("items_presupuesto")
    op.drop_index(
        "ix_presupuestos_profesional_estado", table_name="presupuestos"
    )
    op.drop_index(
        "ix_presupuestos_paciente_created", table_name="presupuestos"
    )
    op.drop_table("presupuestos")
