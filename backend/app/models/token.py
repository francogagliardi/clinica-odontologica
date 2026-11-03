"""Single-use public link tokens (C-03, RN-NO-03).

Only the SHA-256 digest of the token is persisted: a database leak must not
hand over live booking/reminder links. The raw value is returned once to the
caller and never stored.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_USADO_COHERENTE = "(usado) = (usado_at IS NOT NULL)"


class TokenUnSoloUso(Base):
    """Opaque single-use token with expiration (RN-NO-03).

    `usado` and `usado_at` must change together; the CHECK guarantees it even
    for direct SQL, matching the audit-safety criterion used across the schema.
    """

    __tablename__ = "tokens_un_solo_uso"
    __table_args__ = (
        CheckConstraint(_USADO_COHERENTE, name="usado_coherente"),
        Index("uq_tokens_un_solo_uso_token_hash", "token_hash", unique=True),
        Index("ix_tokens_un_solo_uso_entidad", "tipo", "entidad_tipo", "entidad_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    entidad_tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    entidad_id: Mapped[str] = mapped_column(String(64), nullable=False)
    usado: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    usado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expira_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
