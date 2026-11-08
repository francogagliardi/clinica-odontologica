"""Cash register, payments and cash movements (C-13).

Hand-written because Alembic autogenerate does not emit the partial unique
indexes (design D7) nor the type/reference CHECKs of D9. This revision only
creates three new tables; it does not alter any table owned by C-01..C-12.

Invariants and the constraint/index that covers each one:

- `cobros.tipo|medio|estado` belong to their catalogues
  → `ck_cobros_tipo_valido`, `ck_cobros_medio_valido`,
    `ck_cobros_estado_valido`.
- A payment is always positive → `ck_cobros_monto_positivo`.
- A deposit points only to an appointment, a treatment only to a budget and
  "otro" to neither → `ck_cobros_referencias_coherentes`.
- Cash cannot remain `pendiente` → `ck_cobros_efectivo_no_pendiente`.
- Only a Mercado Pago payment can carry `proveedor_pago_id`
  → `ck_cobros_proveedor_pago_solo_mp`.
- Soft delete is coherent → `ck_cobros_baja_logica_coherente`.
- One payment id is reconciled once → `uq_cobros_proveedor_pago` (partial).
- One live deposit per appointment → `uq_cobros_sena_turno` (partial).
- One register per consultorio and local date
  → `uq_cajas_diarias_consultorio_fecha`.
- A closed register has the full snapshot and a coherent difference
  → `ck_cajas_diarias_cierre_coherente`.
- Movements are positive and typed → `ck_movimientos_caja_monto_positivo`,
  `ck_movimientos_caja_tipo_valido`.
- One cash movement per payment → `uq_movimientos_caja_cobro` (partial).

Downgrade order: `movimientos_caja` → `cajas_diarias` → `cobros`, so the FKs
never block the rollback. No existing table or historic deposit is touched.

Revision ID: 0012_caja_cobros
Revises: 0011_presupuestos
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_caja_cobros"
down_revision: str | None = "0011_presupuestos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_TIPOS_COBRO = "'sena','tratamiento','otro'"
_MEDIOS_PAGO = "'efectivo','mercadopago'"
_ESTADOS_COBRO = "'pendiente','aprobado','rechazado','reembolsado','perdido'"
_TIPOS_MOVIMIENTO = "'ingreso','gasto','deuda'"
_ESTADOS_CAJA = "'abierta','cerrada'"
_REFERENCIAS_COBRO = (
    "(tipo = 'sena' AND turno_id IS NOT NULL AND presupuesto_id IS NULL) "
    "OR (tipo = 'tratamiento' AND presupuesto_id IS NOT NULL "
    "AND turno_id IS NULL) "
    "OR (tipo = 'otro' AND turno_id IS NULL AND presupuesto_id IS NULL)"
)
_EFECTIVO_NO_PENDIENTE = "medio <> 'efectivo' OR estado <> 'pendiente'"
_PROVEEDOR_PAGO_SOLO_MP = (
    "proveedor_pago_id IS NULL OR medio = 'mercadopago'"
)
_CIERRE_COHERENTE = (
    "(estado = 'abierta' AND monto_sistema_efectivo IS NULL "
    "AND monto_contado IS NULL AND diferencia IS NULL "
    "AND cerrada_por IS NULL AND cerrada_at IS NULL) "
    "OR (estado = 'cerrada' AND monto_sistema_efectivo IS NOT NULL "
    "AND monto_contado IS NOT NULL "
    "AND diferencia = monto_contado - monto_sistema_efectivo "
    "AND cerrada_por IS NOT NULL AND cerrada_at IS NOT NULL)"
)
_PREDICADO_SENA_VIVA = (
    "tipo = 'sena' AND estado IN ('pendiente','aprobado','perdido')"
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
        "cobros",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("turno_id", sa.Uuid(), nullable=True),
        sa.Column("presupuesto_id", sa.Uuid(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("medio", sa.String(length=20), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("proveedor_pago_id", sa.String(length=100), nullable=True),
        sa.Column(
            "proveedor_preferencia_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("link_pago", sa.Text(), nullable=True),
        sa.Column("fecha_operacion", sa.Date(), nullable=False),
        sa.Column(
            "fecha_conciliacion",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(f"tipo IN ({_TIPOS_COBRO})", name="tipo_valido"),
        sa.CheckConstraint(f"medio IN ({_MEDIOS_PAGO})", name="medio_valido"),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_COBRO})", name="estado_valido"
        ),
        sa.CheckConstraint("monto > 0", name="monto_positivo"),
        sa.CheckConstraint(
            _REFERENCIAS_COBRO, name="referencias_coherentes"
        ),
        sa.CheckConstraint(
            _EFECTIVO_NO_PENDIENTE, name="efectivo_no_pendiente"
        ),
        sa.CheckConstraint(
            _PROVEEDOR_PAGO_SOLO_MP, name="proveedor_pago_solo_mp"
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_cobros_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_cobros_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["turno_id"],
            ["turnos.id"],
            name="fk_cobros_turno_id_turnos",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["presupuesto_id"],
            ["presupuestos.id"],
            name="fk_cobros_presupuesto_id_presupuestos",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_cobros_creado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cobros"),
    )
    op.create_index(
        "ix_cobros_paciente_fecha",
        "cobros",
        ["consultorio_id", "paciente_id", "fecha_operacion"],
    )
    op.create_index("ix_cobros_turno", "cobros", ["turno_id"])
    op.create_index(
        "ix_cobros_presupuesto", "cobros", ["presupuesto_id"]
    )
    op.create_index(
        "ix_cobros_estado", "cobros", ["consultorio_id", "estado"]
    )
    op.create_index(
        "uq_cobros_proveedor_pago",
        "cobros",
        ["proveedor_pago_id"],
        unique=True,
        postgresql_where=sa.text("proveedor_pago_id IS NOT NULL"),
    )
    op.create_index(
        "uq_cobros_sena_turno",
        "cobros",
        ["turno_id"],
        unique=True,
        postgresql_where=sa.text(_PREDICADO_SENA_VIVA),
    )

    op.create_table(
        "cajas_diarias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'abierta'"),
        ),
        sa.Column("monto_apertura", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "monto_sistema_efectivo", sa.Numeric(12, 2), nullable=True
        ),
        sa.Column("monto_contado", sa.Numeric(12, 2), nullable=True),
        sa.Column("diferencia", sa.Numeric(12, 2), nullable=True),
        sa.Column("cerrada_por", sa.Uuid(), nullable=True),
        sa.Column(
            "cerrada_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("observaciones", sa.String(length=500), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_CAJA})", name="estado_valido"
        ),
        sa.CheckConstraint(
            "monto_apertura >= 0", name="monto_apertura_no_negativo"
        ),
        sa.CheckConstraint(_CIERRE_COHERENTE, name="cierre_coherente"),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_cajas_diarias_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cerrada_por"],
            ["usuarios.id"],
            name="fk_cajas_diarias_cerrada_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cajas_diarias"),
        sa.UniqueConstraint(
            "consultorio_id",
            "fecha",
            name="uq_cajas_diarias_consultorio_fecha",
        ),
    )

    op.create_table(
        "movimientos_caja",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("caja_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("concepto", sa.String(length=200), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "medio",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'efectivo'"),
        ),
        sa.Column("cobro_id", sa.Uuid(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"tipo IN ({_TIPOS_MOVIMIENTO})", name="tipo_valido"
        ),
        sa.CheckConstraint(f"medio IN ({_MEDIOS_PAGO})", name="medio_valido"),
        sa.CheckConstraint("monto > 0", name="monto_positivo"),
        sa.ForeignKeyConstraint(
            ["caja_id"],
            ["cajas_diarias.id"],
            name="fk_movimientos_caja_caja_id_cajas_diarias",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cobro_id"],
            ["cobros.id"],
            name="fk_movimientos_caja_cobro_id_cobros",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_movimientos_caja_creado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_movimientos_caja"),
    )
    op.create_index(
        "ix_movimientos_caja_caja", "movimientos_caja", ["caja_id"]
    )
    op.create_index(
        "uq_movimientos_caja_cobro",
        "movimientos_caja",
        ["cobro_id"],
        unique=True,
        postgresql_where=sa.text("cobro_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Reverse order: movements reference the register and the payment, and the
    # register references the tenant/user tables only.
    op.drop_index(
        "uq_movimientos_caja_cobro", table_name="movimientos_caja"
    )
    op.drop_index(
        "ix_movimientos_caja_caja", table_name="movimientos_caja"
    )
    op.drop_table("movimientos_caja")
    op.drop_table("cajas_diarias")
    op.drop_index("uq_cobros_sena_turno", table_name="cobros")
    op.drop_index("uq_cobros_proveedor_pago", table_name="cobros")
    op.drop_index("ix_cobros_estado", table_name="cobros")
    op.drop_index("ix_cobros_presupuesto", table_name="cobros")
    op.drop_index("ix_cobros_turno", table_name="cobros")
    op.drop_index("ix_cobros_paciente_fecha", table_name="cobros")
    op.drop_table("cobros")
