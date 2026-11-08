"""Boundary and response schemas for exportations (C-15, D9/D13)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Alcance = Literal["paciente", "consultorio"]
EstadoExportacion = Literal["pendiente", "generando", "lista", "fallida"]


class ExportacionCreate(BaseModel):
    """Only the scope and, for a patient, its id; no format or range in v1."""

    model_config = ConfigDict(extra="forbid")

    alcance: Alcance
    paciente_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _alcance_coherente(self) -> "ExportacionCreate":
        if self.alcance == "paciente" and self.paciente_id is None:
            raise ValueError("El alcance paciente exige paciente_id")
        if self.alcance == "consultorio" and self.paciente_id is not None:
            raise ValueError(
                "El alcance consultorio no admite paciente_id"
            )
        return self


class ExportacionListadoQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: EstadoExportacion | None = None
    alcance: Alcance | None = None


class ExportacionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    solicitado_por: uuid.UUID
    alcance: Alcance
    paciente_id: uuid.UUID | None
    estado: EstadoExportacion
    tamano_bytes: int | None
    generada_at: datetime | None
    ultimo_error: str | None
    intentos: int
    created_at: datetime
    updated_at: datetime
