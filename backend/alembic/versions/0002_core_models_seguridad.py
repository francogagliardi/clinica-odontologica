"""Core security models (C-02): identity, roles and append-only audit.

Hand-written on purpose (design decision): autogenerate does not detect
partial unique indexes, CHECK constraints or triggers, so the diff would be
incomplete. Constraint/index names follow the project naming convention and
are asserted by the migration tests.

Revision ID: 0002_core_models_seguridad
Revises: 0001_base
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_models_seguridad"
down_revision: str | None = "0001_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOWA_LOGICA = "(deleted_at IS NULL) = is_active"

_APPEND_ONLY_FUNCTION = """
CREATE FUNCTION registro_auditoria_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'registro_auditoria es append-only (RN-SE-02): % no permitido', TG_OP
        USING ERRCODE = 'P0001';
END;
$$ LANGUAGE plpgsql;
"""


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
        "consultorios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=60), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            _LOWA_LOGICA, name="baja_logica_coherente"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consultorios"),
    )
    op.create_index(
        "uq_consultorios_slug_activo",
        "consultorios",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=40), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(_LOWA_LOGICA, name="baja_logica_coherente"),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
    )
    op.create_index(
        "uq_roles_nombre_activo",
        "roles",
        ["nombre"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hash_password", sa.String(length=255), nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            _LOWA_LOGICA, name="baja_logica_coherente"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usuarios"),
    )
    op.create_index(
        "uq_usuarios_email_activo",
        "usuarios",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "usuario_roles",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("rol_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_usuario_roles_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rol_id"],
            ["roles.id"],
            name="fk_usuario_roles_rol_id_roles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "rol_id", name="pk_usuario_roles"),
    )

    op.create_table(
        "registro_auditoria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("accion", sa.String(length=120), nullable=False),
        sa.Column("entidad", sa.String(length=60), nullable=False),
        sa.Column("entidad_id", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("dispositivo", sa.String(length=120), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_registro_auditoria_usuario_id_usuarios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_registro_auditoria"),
    )
    op.create_index(
        "ix_registro_auditoria_usuario_timestamp",
        "registro_auditoria",
        ["usuario_id", "timestamp"],
    )
    op.create_index(
        "ix_registro_auditoria_entidad",
        "registro_auditoria",
        ["entidad", "entidad_id"],
    )

    # Append-only: row triggers catch UPDATE/DELETE, the statement trigger
    # catches TRUNCATE (PostgreSQL does not fire row triggers for TRUNCATE).
    op.execute(_APPEND_ONLY_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER trg_registro_auditoria_sin_update_delete
        BEFORE UPDATE OR DELETE ON registro_auditoria
        FOR EACH ROW EXECUTE FUNCTION registro_auditoria_append_only();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_registro_auditoria_sin_truncate
        BEFORE TRUNCATE ON registro_auditoria
        FOR EACH STATEMENT EXECUTE FUNCTION registro_auditoria_append_only();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_registro_auditoria_sin_truncate "
        "ON registro_auditoria;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_registro_auditoria_sin_update_delete "
        "ON registro_auditoria;"
    )
    op.execute("DROP FUNCTION IF EXISTS registro_auditoria_append_only();")

    op.drop_index(
        "ix_registro_auditoria_entidad", table_name="registro_auditoria"
    )
    op.drop_index(
        "ix_registro_auditoria_usuario_timestamp",
        table_name="registro_auditoria",
    )
    op.drop_table("registro_auditoria")

    op.drop_table("usuario_roles")

    op.drop_index("uq_usuarios_email_activo", table_name="usuarios")
    op.drop_table("usuarios")

    op.drop_index("uq_roles_nombre_activo", table_name="roles")
    op.drop_table("roles")

    op.drop_index("uq_consultorios_slug_activo", table_name="consultorios")
    op.drop_table("consultorios")
