"""Audit viewer indexes (C-16, design D11).

`0015_admin_auditoria` only adds the three indexes that sustain the audit
viewer order and filters:

- `ix_registro_auditoria_timestamp` → `(timestamp DESC, id DESC)`;
- `ix_registro_auditoria_accion_timestamp` → `(accion, timestamp DESC)`;
- `ix_registro_auditoria_entidad_timestamp` → `(entidad, timestamp DESC)`.

There are no new tables, no column changes and no backfill. The append-only
triggers of C-02 are untouched, and no privacy-acceptance index is added
because acceptance is out of scope (design D7/D11).

Downgrade drops exactly those three indexes.

Revision ID: 0015_admin_auditoria
Revises: 0014_reportes
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_admin_auditoria"
down_revision: str | None = "0014_reportes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDICES = (
    "ix_registro_auditoria_timestamp",
    "ix_registro_auditoria_accion_timestamp",
    "ix_registro_auditoria_entidad_timestamp",
)


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_registro_auditoria_timestamp "
        "ON registro_auditoria (timestamp DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX ix_registro_auditoria_accion_timestamp "
        "ON registro_auditoria (accion, timestamp DESC)"
    )
    op.execute(
        "CREATE INDEX ix_registro_auditoria_entidad_timestamp "
        "ON registro_auditoria (entidad, timestamp DESC)"
    )


def downgrade() -> None:
    for nombre in _INDICES:
        op.execute(f"DROP INDEX IF EXISTS {nombre}")
