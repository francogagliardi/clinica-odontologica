"""Pydantic schemas for agenda resources and the service catalogue (C-04).

Every request schema forbids extra fields (R-01/R-02). Business coherence is
validated here at the edge and again in PostgreSQL with CHECKs, so neither a
buggy client nor direct SQL can persist an invalid row (design D8).
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_DIAS_ISO = range(0, 7)


class AgendaConfig(BaseModel):
    """Nested agenda configuration kept as explicit columns in the table."""

    model_config = ConfigDict(extra="forbid")

    duracion_base_min: int = Field(gt=0, le=720)
    dias_atencion: list[int] = Field(min_length=1, max_length=7)
    hora_desde: time
    hora_hasta: time

    @field_validator("dias_atencion")
    @classmethod
    def _validar_dias(cls, value: list[int]) -> list[int]:
        if any(dia not in _DIAS_ISO for dia in value):
            raise ValueError("Los días de atención deben estar entre 0 y 6")
        if len(set(value)) != len(value):
            raise ValueError("Los días de atención no pueden repetirse")
        return sorted(value)

    @model_validator(mode="after")
    def _validar_horario(self) -> "AgendaConfig":
        if self.hora_hasta <= self.hora_desde:
            raise ValueError("hora_hasta debe ser posterior a hora_desde")
        return self


class ProfesionalBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matricula: str = Field(min_length=1, max_length=40)
    usuario_id: uuid.UUID | None = None
    especialidades: list[str] = Field(default_factory=list, max_length=20)
    agenda_config: AgendaConfig

    @field_validator("especialidades")
    @classmethod
    def _limpiar_especialidades(cls, value: list[str]) -> list[str]:
        limpias = [item.strip() for item in value if item.strip()]
        if len(set(limpias)) != len(limpias):
            raise ValueError("Las especialidades no pueden repetirse")
        return limpias


class ProfesionalCreate(ProfesionalBase):
    pass


class ProfesionalUpdate(ProfesionalBase):
    pass


class ProfesionalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    usuario_id: uuid.UUID | None
    matricula: str
    especialidades: list[str]
    agenda_config: AgendaConfig
    is_active: bool


class SillonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=60)


class SillonUpdate(SillonCreate):
    pass


class SillonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    nombre: str
    is_active: bool


class PrestacionBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=120)
    duracion_min: int = Field(gt=0, le=720)
    precio_base: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    especialidad: str | None = Field(default=None, max_length=60)
    requiere_sena: bool = False
    monto_sena: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )

    @model_validator(mode="after")
    def _validar_sena(self) -> "PrestacionBase":
        if self.requiere_sena:
            if self.monto_sena is None:
                raise ValueError(
                    "monto_sena es obligatorio cuando requiere_sena es true"
                )
            if self.monto_sena <= 0:
                raise ValueError("monto_sena debe ser mayor que cero")
        elif self.monto_sena is not None:
            raise ValueError(
                "monto_sena debe ser nulo cuando requiere_sena es false"
            )
        return self

    @field_validator("codigo")
    @classmethod
    def _codigo_normalizado(cls, value: str) -> str:
        return value.strip().upper()


class PrestacionCreate(PrestacionBase):
    pass


class PrestacionUpdate(PrestacionBase):
    pass


class PrestacionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    codigo: str
    nombre: str
    duracion_min: int
    precio_base: Decimal
    especialidad: str | None
    requiere_sena: bool
    monto_sena: Decimal | None
    is_active: bool


class BloqueoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID | None = None
    sillon_id: uuid.UUID | None = None
    desde: datetime
    hasta: datetime
    motivo: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _validar_recurso_y_rango(self) -> "BloqueoCreate":
        tiene_profesional = self.profesional_id is not None
        tiene_sillon = self.sillon_id is not None
        if tiene_profesional == tiene_sillon:
            raise ValueError(
                "El bloqueo debe indicar exactamente un profesional o un sillón"
            )
        if self.hasta <= self.desde:
            raise ValueError("hasta debe ser posterior a desde")
        return self


class BloqueoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    profesional_id: uuid.UUID | None
    sillon_id: uuid.UUID | None
    desde: datetime
    hasta: datetime
    motivo: str
    is_active: bool


class SlotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inicio: datetime
    fin: datetime


class DisponibilidadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fecha: date
    slots: list[SlotResponse]
