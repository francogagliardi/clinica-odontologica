"""Declarative base and shared audit columns (R-01, R-04).

Business entities inherit `AuditMixin`: soft delete only, never physical
delete, with UTC timestamps. The coherence between `is_active` and
`deleted_at` is enforced by each table's CHECK constraint (C-02 design), so a
direct UPDATE cannot leave a half-deleted row behind.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint/index names: migrations and tests can assert them.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Single declarative base shared by every model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AuditMixin:
    """Soft-delete + timestamp columns for business entities.

    `deleted_at` non-null and `is_active` false must change together; the
    database CHECK guarantees it even when written around the ORM.
    """

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def soft_delete(self) -> None:
        """Mark the row as deleted without removing history (idempotent)."""
        if self.deleted_at is not None:
            return
        self.deleted_at = datetime.now(timezone.utc)
        self.is_active = False
