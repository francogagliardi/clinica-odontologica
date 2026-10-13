"""Baseline marker revision (C-01): intentionally creates NO domain tables.

Domain tables arrive as versioned migrations from C-02 onward (R-04).

Revision ID: 0001_base
Revises: None
"""

from collections.abc import Sequence

revision: str = "0001_base"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
