"""Boundary schemas for preventive coverage (C-14, design D8/D13)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoCobertura = Literal[
    "cubierta", "no_cubierta", "pendiente_verificacion"
]


class CoberturaResponse(BaseModel):
    """Only local coverage data: no caps, frequencies or external codes."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: uuid.UUID
    prestacion_id: uuid.UUID
    estado: EstadoCobertura
    cobertura_porcentaje: Decimal | None
    cobertura_monto: Decimal | None
    copago_monto: Decimal | None
