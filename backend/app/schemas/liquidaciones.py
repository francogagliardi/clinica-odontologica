"""Boundary schemas for insurance settlements (C-14, design D9/D13)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoLiquidacion = Literal["borrador", "cerrada"]


class LiquidacionCreate(BaseModel):
    """POST /obras-sociales/liquidaciones: agreement and inclusive period."""

    model_config = ConfigDict(extra="forbid")

    obra_social_id: uuid.UUID
    desde: date
    hasta: date
    observaciones: str | None = Field(default=None, max_length=500)


class LiquidacionObservacionesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observaciones: str | None = Field(default=None, max_length=500)


class ItemLiquidacionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    item_presupuesto_id: uuid.UUID
    presupuesto_id: uuid.UUID
    cobro_id: uuid.UUID
    prestacion_id: uuid.UUID
    prestacion_codigo: str
    pieza: int | None
    cantidad: int
    cobertura_item: Decimal


class LiquidacionResumenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    obra_social_id: uuid.UUID
    creado_por: uuid.UUID
    desde: date
    hasta: date
    estado: EstadoLiquidacion
    total_cobertura: Decimal
    cantidad_practicas: int
    observaciones: str | None
    cerrada_por: uuid.UUID | None
    cerrada_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LiquidacionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    obra_social_id: uuid.UUID
    creado_por: uuid.UUID
    desde: date
    hasta: date
    estado: EstadoLiquidacion
    total_cobertura: Decimal
    cantidad_practicas: int
    observaciones: str | None
    cerrada_por: uuid.UUID | None
    cerrada_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[ItemLiquidacionResponse]
