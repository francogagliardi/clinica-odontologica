"""Tokens de un solo uso para enlaces públicos (C-03, RN-NO-03).

Se persiste solo el digest SHA-256: una filtración de la base no entrega
enlaces vivos de reserva/recordatorio.

Revision ID: 0003_tokens_un_solo_uso
Revises: 0002_core_models_seguridad
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_tokens_un_solo_uso"
down_revision: str | None = "0002_core_models_seguridad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_USADO_COHERENTE = "(usado) = (usado_at IS NOT NULL)"


def upgrade() -> None:
    op.create_table(
        "tokens_un_solo_uso",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("entidad_tipo", sa.String(length=40), nullable=False),
        sa.Column("entidad_id", sa.String(length=64), nullable=False),
        sa.Column(
            "usado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("usado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(_USADO_COHERENTE, name="usado_coherente"),
        sa.PrimaryKeyConstraint("id", name="pk_tokens_un_solo_uso"),
    )
    op.create_index(
        "uq_tokens_un_solo_uso_token_hash",
        "tokens_un_solo_uso",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_tokens_un_solo_uso_entidad",
        "tokens_un_solo_uso",
        ["tipo", "entidad_tipo", "entidad_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tokens_un_solo_uso_entidad", table_name="tokens_un_solo_uso")
    op.drop_index(
        "uq_tokens_un_solo_uso_token_hash", table_name="tokens_un_solo_uso"
    )
    op.drop_table("tokens_un_solo_uso")
