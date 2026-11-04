"""Public booking: deposit state on appointments (C-07).

Revision ID: 0007_reserva_publica
Revises: 0006_turnos_anti_solapamiento
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_reserva_publica"
down_revision: str | None = "0006_turnos_anti_solapamiento"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "turnos",
        sa.Column(
            "sena_estado",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'no_requiere'"),
        ),
    )
    op.create_check_constraint(
        "sena_estado_valido",
        "turnos",
        "sena_estado IN ('no_requiere','pendiente','pagada','perdida')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE turnos "
        "DROP CONSTRAINT IF EXISTS ck_turnos_sena_estado_valido"
    )
    op.drop_column("turnos", "sena_estado")
