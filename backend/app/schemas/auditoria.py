"""Boundary and response schemas for the audit viewer (C-16, design D5/D12).

The query is strict: only the declared filters exist, `limite` is 1..500 with
100 as default, `offset` is non-negative and an inverted date range is rejected
before touching the database. Dates are local UTC-3 and inclusive.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditoriaQuery(BaseModel):
    """Filters accepted by `GET /auditoria`."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: uuid.UUID | None = None
    entidad: str | None = Field(default=None, max_length=60)
    accion: str | None = Field(default=None, max_length=120)
    desde: date | None = None
    hasta: date | None = None
    limite: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _rango_coherente(self) -> "AuditoriaQuery":
        if self.desde is not None and self.hasta is not None:
            if self.hasta < self.desde:
                raise ValueError(
                    "hasta debe ser posterior o igual a desde"
                )
        return self


class AuditoriaFila(BaseModel):
    """One append-only trace row; never a payload, token or secret."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    usuario_id: uuid.UUID | None
    usuario_email: str | None
    accion: str
    entidad: str
    entidad_id: str
    ip: str | None
    dispositivo: str | None
    timestamp: datetime


class AuditoriaResponse(BaseModel):
    """Bounded page plus the total counted before paginating."""

    model_config = ConfigDict(extra="forbid")

    total: int
    limite: int
    offset: int
    filas: list[AuditoriaFila]
