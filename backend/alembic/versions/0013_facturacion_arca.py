"""Billing receipts, ARCA issuance and insurance settlements (C-14).

Hand-written because Alembic autogenerate does not emit the partial unique
indexes (D5), the fiscal-coherence CHECKs (D12) nor `EXCLUDE USING gist`
(D9). This revision only creates five new tables; it does not alter any table
owned by C-01..C-13 nor backfills historic payments.

Invariants and the object that covers each one:

- One receipt per payment → `uq_comprobantes_cobro`.
- Gapless internal numbering per consultorio/POS
  → `uq_comprobantes_numero_interno`.
- A CAE is never reused in an environment → `uq_comprobantes_cae` (partial).
- Fiscal numbering is unique per consultorio/POS
  → `uq_comprobantes_fiscal` (partial).
- `emitido` has CAE/vencimiento/numero/QR/fecha and the other states forbid
  them → `ck_comprobantes_estado_fiscal_coherente`.
- A failed receipt explains why → `ck_comprobantes_fallido_con_error`.
- Receipt totals are positive, retries non-negative and CAE is 14 digits
  → `ck_comprobantes_importe_positivo`,
    `ck_comprobantes_intentos_no_negativos`, `ck_comprobantes_cae_formato`.
- One simulated delivery per receipt and channel
  → `uq_comprobantes_envios_comprobante_canal`.
- Settlement period `desde <= hasta` → `ck_liquidaciones_obras_sociales_*`.
- Two live settlements of one agreement cannot overlap
  → `ex_liquidaciones_periodo` (`23P01`).
- A budget line is settled once while live → `uq_items_liquidacion_item`.

Downgrade order: `items_liquidacion` → `liquidaciones_obras_sociales` →
`secuencias_comprobantes` → `comprobantes_envios` → `comprobantes`, so the FKs
never block the rollback. `btree_gist` is intentionally kept.

Revision ID: 0013_facturacion_arca
Revises: 0012_caja_cobros
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0013_facturacion_arca"
down_revision: str | None = "0012_caja_cobros"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"
_TIPOS_COMPROBANTE = "'B','C'"
_AMBIENTES = "'homologacion'"
_ESTADOS_FISCALES = "'pendiente','emitido','fallido'"
_CANALES_ENVIO = "'whatsapp'"
_ESTADOS_ENVIO = "'registrado','fallido'"
_ESTADOS_LIQUIDACION = "'borrador','cerrada'"
_CAE_FORMATO = "^[0-9]{14}$"
_ESTADO_FISCAL_COHERENTE = (
    "(estado = 'emitido' AND cae IS NOT NULL "
    "AND cae_vencimiento IS NOT NULL AND numero_fiscal IS NOT NULL "
    "AND qr_fiscal IS NOT NULL AND fecha_emision_fiscal IS NOT NULL) "
    "OR (estado IN ('pendiente','fallido') AND cae IS NULL "
    "AND cae_vencimiento IS NULL AND numero_fiscal IS NULL "
    "AND qr_fiscal IS NULL AND fecha_emision_fiscal IS NULL)"
)
_CIERRE_COHERENTE = (
    "(estado = 'borrador' AND cerrada_por IS NULL AND cerrada_at IS NULL) "
    "OR (estado = 'cerrada' AND cerrada_por IS NOT NULL "
    "AND cerrada_at IS NOT NULL)"
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
        "comprobantes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("cobro_id", sa.Uuid(), nullable=False),
        sa.Column("paciente_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=1), nullable=False),
        sa.Column(
            "ambiente",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'homologacion'"),
        ),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        sa.Column("numero_interno", sa.BigInteger(), nullable=False),
        sa.Column("punto_venta", sa.Integer(), nullable=False),
        sa.Column("numero_fiscal", sa.BigInteger(), nullable=True),
        sa.Column("cae", sa.String(length=14), nullable=True),
        sa.Column("cae_vencimiento", sa.Date(), nullable=True),
        sa.Column("qr_interno", sa.Text(), nullable=False),
        sa.Column("qr_fiscal", sa.Text(), nullable=True),
        sa.Column("receptor_nombre", sa.String(length=200), nullable=False),
        sa.Column(
            "receptor_documento", sa.String(length=20), nullable=False
        ),
        sa.Column(
            "receptor_tipo_documento",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'DNI'"),
        ),
        sa.Column(
            "condicion_fiscal_receptor",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'consumidor_final'"),
        ),
        sa.Column(
            "condicion_fiscal_emisor", sa.String(length=30), nullable=False
        ),
        sa.Column("importe_total", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column(
            "fecha_emision_fiscal",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.Column("payload_envio", JSONB(), nullable=True),
        sa.Column(
            "respuesta_proveedor",
            JSONB(),
            nullable=True,
        ),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"tipo IN ({_TIPOS_COMPROBANTE})", name="tipo_valido"
        ),
        sa.CheckConstraint(
            f"ambiente IN ({_AMBIENTES})", name="ambiente_valido"
        ),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_FISCALES})", name="estado_valido"
        ),
        sa.CheckConstraint(
            "numero_interno > 0", name="numero_interno_positivo"
        ),
        sa.CheckConstraint("punto_venta > 0", name="punto_venta_positivo"),
        sa.CheckConstraint(
            "numero_fiscal IS NULL OR numero_fiscal > 0",
            name="numero_fiscal_positivo",
        ),
        sa.CheckConstraint("importe_total > 0", name="importe_positivo"),
        sa.CheckConstraint(
            "intentos >= 0", name="intentos_no_negativos"
        ),
        sa.CheckConstraint(
            f"cae IS NULL OR cae ~ '{_CAE_FORMATO}'", name="cae_formato"
        ),
        sa.CheckConstraint(
            _ESTADO_FISCAL_COHERENTE, name="estado_fiscal_coherente"
        ),
        sa.CheckConstraint(
            "estado <> 'fallido' OR ultimo_error IS NOT NULL",
            name="fallido_con_error",
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_comprobantes_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cobro_id"],
            ["cobros.id"],
            name="fk_comprobantes_cobro_id_cobros",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paciente_id"],
            ["pacientes.id"],
            name="fk_comprobantes_paciente_id_pacientes",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_comprobantes"),
    )
    op.create_index(
        "uq_comprobantes_cobro",
        "comprobantes",
        ["cobro_id"],
        unique=True,
    )
    op.create_index(
        "uq_comprobantes_numero_interno",
        "comprobantes",
        ["consultorio_id", "punto_venta", "numero_interno"],
        unique=True,
    )
    op.create_index(
        "uq_comprobantes_cae",
        "comprobantes",
        ["ambiente", "cae"],
        unique=True,
        postgresql_where=sa.text("cae IS NOT NULL"),
    )
    op.create_index(
        "uq_comprobantes_fiscal",
        "comprobantes",
        ["ambiente", "punto_venta", "numero_fiscal"],
        unique=True,
        postgresql_where=sa.text("numero_fiscal IS NOT NULL"),
    )
    op.create_index(
        "ix_comprobantes_estado_proximo",
        "comprobantes",
        ["estado", "proximo_intento"],
    )
    op.create_index(
        "ix_comprobantes_paciente", "comprobantes", ["paciente_id"]
    )
    op.create_index(
        "ix_comprobantes_fecha",
        "comprobantes",
        ["consultorio_id", "fecha_emision"],
    )

    op.create_table(
        "comprobantes_envios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comprobante_id", sa.Uuid(), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("destino", sa.String(length=120), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'registrado'"),
        ),
        sa.Column(
            "proveedor_mensaje_id", sa.String(length=100), nullable=True
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"canal IN ({_CANALES_ENVIO})", name="canal_valido"
        ),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_ENVIO})", name="estado_valido"
        ),
        sa.CheckConstraint(
            "btrim(destino) <> ''", name="destino_no_vacio"
        ),
        sa.ForeignKeyConstraint(
            ["comprobante_id"],
            ["comprobantes.id"],
            name="fk_comprobantes_envios_comprobante_id_comprobantes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_comprobantes_envios_creado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_comprobantes_envios"),
    )
    op.create_index(
        "uq_comprobantes_envios_comprobante_canal",
        "comprobantes_envios",
        ["comprobante_id", "canal"],
        unique=True,
    )
    op.create_index(
        "ix_comprobantes_envios_comprobante",
        "comprobantes_envios",
        ["comprobante_id"],
    )

    op.create_table(
        "secuencias_comprobantes",
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("punto_venta", sa.Integer(), nullable=False),
        sa.Column(
            "ultimo_interno",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "ultimo_fiscal",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint("punto_venta > 0", name="punto_venta_positivo"),
        sa.CheckConstraint(
            "ultimo_interno >= 0 AND ultimo_fiscal >= 0",
            name="contadores_no_negativos",
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_secuencias_comprobantes_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "consultorio_id",
            "punto_venta",
            name="pk_secuencias_comprobantes",
        ),
    )

    op.create_table(
        "liquidaciones_obras_sociales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consultorio_id", sa.Uuid(), nullable=False),
        sa.Column("obra_social_id", sa.Uuid(), nullable=False),
        sa.Column("creado_por", sa.Uuid(), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'borrador'"),
        ),
        sa.Column(
            "total_cobertura",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cantidad_practicas",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("observaciones", sa.String(length=500), nullable=True),
        sa.Column("cerrada_por", sa.Uuid(), nullable=True),
        sa.Column(
            "cerrada_at", sa.DateTime(timezone=True), nullable=True
        ),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint(
            f"estado IN ({_ESTADOS_LIQUIDACION})", name="estado_valido"
        ),
        sa.CheckConstraint("desde <= hasta", name="periodo_valido"),
        sa.CheckConstraint(_CIERRE_COHERENTE, name="cierre_coherente"),
        sa.CheckConstraint(
            "total_cobertura >= 0 AND cantidad_practicas >= 0",
            name="totales_no_negativos",
        ),
        sa.ForeignKeyConstraint(
            ["consultorio_id"],
            ["consultorios.id"],
            name="fk_liquidaciones_obras_sociales_consultorio_id_consultorios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["obra_social_id"],
            ["obras_sociales.id"],
            name="fk_liquidaciones_obras_sociales_obra_social_id_obras_sociales",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_liquidaciones_obras_sociales_creado_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cerrada_por"],
            ["usuarios.id"],
            name="fk_liquidaciones_obras_sociales_cerrada_por_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id", name="pk_liquidaciones_obras_sociales"
        ),
    )
    op.create_index(
        "ix_liquidaciones_obras_social_periodo",
        "liquidaciones_obras_sociales",
        ["consultorio_id", "obra_social_id", "desde"],
    )
    op.create_index(
        "ix_liquidaciones_estado",
        "liquidaciones_obras_sociales",
        ["estado"],
    )
    op.execute(
        "ALTER TABLE liquidaciones_obras_sociales "
        "ADD CONSTRAINT ex_liquidaciones_periodo "
        "EXCLUDE USING gist ("
        "obra_social_id WITH =, "
        "daterange(desde, hasta, '[]') WITH &&"
        ") WHERE (deleted_at IS NULL)"
    )

    op.create_table(
        "items_liquidacion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("liquidacion_id", sa.Uuid(), nullable=False),
        sa.Column("item_presupuesto_id", sa.Uuid(), nullable=False),
        sa.Column("presupuesto_id", sa.Uuid(), nullable=False),
        sa.Column("cobro_id", sa.Uuid(), nullable=False),
        sa.Column("prestacion_id", sa.Uuid(), nullable=False),
        sa.Column("prestacion_codigo", sa.String(length=20), nullable=False),
        sa.Column("pieza", sa.Integer(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("cobertura_item", sa.Numeric(12, 2), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        sa.CheckConstraint(
            "cobertura_item >= 0", name="cobertura_no_negativa"
        ),
        sa.ForeignKeyConstraint(
            ["liquidacion_id"],
            ["liquidaciones_obras_sociales.id"],
            name="fk_items_liquidacion_liquidacion_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_presupuesto_id"],
            ["items_presupuesto.id"],
            name="fk_items_liquidacion_item_presupuesto_id_items_presupuesto",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["presupuesto_id"],
            ["presupuestos.id"],
            name="fk_items_liquidacion_presupuesto_id_presupuestos",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cobro_id"],
            ["cobros.id"],
            name="fk_items_liquidacion_cobro_id_cobros",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prestacion_id"],
            ["prestaciones.id"],
            name="fk_items_liquidacion_prestacion_id_prestaciones",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_items_liquidacion"),
    )
    op.create_index(
        "ix_items_liquidacion_liquidacion",
        "items_liquidacion",
        ["liquidacion_id"],
    )
    op.create_index(
        "ix_items_liquidacion_presupuesto",
        "items_liquidacion",
        ["presupuesto_id"],
    )
    op.create_index(
        "ix_items_liquidacion_cobro",
        "items_liquidacion",
        ["cobro_id"],
    )
    op.create_index(
        "uq_items_liquidacion_item",
        "items_liquidacion",
        ["item_presupuesto_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE liquidaciones_obras_sociales "
        "DROP CONSTRAINT IF EXISTS ex_liquidaciones_periodo"
    )
    for _indice in (
        "uq_items_liquidacion_item",
        "ix_items_liquidacion_cobro",
        "ix_items_liquidacion_presupuesto",
        "ix_items_liquidacion_liquidacion",
    ):
        op.drop_index(_indice, table_name="items_liquidacion")
    op.drop_table("items_liquidacion")

    op.drop_index(
        "ix_liquidaciones_estado",
        table_name="liquidaciones_obras_sociales",
    )
    op.drop_index(
        "ix_liquidaciones_obras_social_periodo",
        table_name="liquidaciones_obras_sociales",
    )
    op.drop_table("liquidaciones_obras_sociales")

    op.drop_table("secuencias_comprobantes")

    op.drop_index(
        "ix_comprobantes_envios_comprobante",
        table_name="comprobantes_envios",
    )
    op.drop_index(
        "uq_comprobantes_envios_comprobante_canal",
        table_name="comprobantes_envios",
    )
    op.drop_table("comprobantes_envios")

    for _indice in (
        "ix_comprobantes_fecha",
        "ix_comprobantes_paciente",
        "ix_comprobantes_estado_proximo",
        "uq_comprobantes_fiscal",
        "uq_comprobantes_cae",
        "uq_comprobantes_numero_interno",
        "uq_comprobantes_cobro",
    ):
        op.drop_index(_indice, table_name="comprobantes")
    op.drop_table("comprobantes")
    # `btree_gist` is intentionally kept: other schemas may depend on it.
