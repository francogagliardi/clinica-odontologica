"""Pydantic schemas for budgets (C-12, design D10).

Clients send references and quantities only: prices, coverage and totals are
server-owned, so every extra field (`precio_unitario`, `subtotal`, …) is
rejected with 422 by `extra='forbid'` instead of being ignored.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.clinica import pieza_fdi_valida
from app.domain.presupuestos import ESTADOS


class ItemPresupuestoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prestacion_id: uuid.UUID
    pieza: int | None = None
    cantidad: int = Field(gt=0)

    @field_validator("pieza")
    @classmethod
    def _pieza_fdi(cls, value: int | None) -> int | None:
        if value is not None and not pieza_fdi_valida(value):
            raise ValueError("La pieza no es una pieza FDI válida")
        return value


class PresupuestoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    items: list[ItemPresupuestoCreate] = Field(min_length=1)


class PresupuestoUpdate(PresupuestoCreate):
    """Full replacement of a draft: same contract as creation (design D10)."""


class RecalculoRequest(BaseModel):
    """Empty body on purpose: recalculation cannot smuggle new amounts."""

    model_config = ConfigDict(extra="forbid")


class EstadoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: str

    @field_validator("estado")
    @classmethod
    def _estado_valido(cls, value: str) -> str:
        if value not in ESTADOS:
            raise ValueError("Estado de presupuesto no válido")
        return value


class ItemPresupuestoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    prestacion_id: uuid.UUID
    pieza: int | None
    cantidad: int
    precio_unitario: Decimal
    cobertura_item: Decimal
    copago_item: Decimal


class PresupuestoResumenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    creado_por: uuid.UUID
    estado: str
    cobertura_estado: str
    subtotal: Decimal
    cobertura_calculada: Decimal
    copago: Decimal
    created_at: datetime
    updated_at: datetime


class PresupuestoResponse(PresupuestoResumenResponse):
    items: list[ItemPresupuestoResponse]
