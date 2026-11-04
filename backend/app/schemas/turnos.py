"""Pydantic schemas for appointments (C-06).

The client never sends `fin`, `estado` on creation or internal fields: they are
derived/enforced by the API and the database (design D4/D6).
"""

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

_ESTADO = Literal[
    "reservado", "confirmado", "en_sala", "atendido", "cancelado", "ausente"
]
_ESTADO_DESTINO = Literal[
    "confirmado", "en_sala", "atendido", "cancelado", "ausente"
]
_ORIGEN = Literal["recepcion", "online", "whatsapp"]
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _exigir_zona(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("El inicio debe incluir zona horaria")
    return value


class TurnoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    sillon_id: uuid.UUID
    prestacion_id: uuid.UUID | None = None
    inicio: datetime
    origen: _ORIGEN = "recepcion"
    es_sobreturno: bool = False
    color_sobreturno: str | None = Field(default=None, max_length=7)

    @field_validator("inicio")
    @classmethod
    def _inicio_con_zona(cls, value: datetime) -> datetime:
        return _exigir_zona(value)

    @model_validator(mode="after")
    def _sobreturno_coherente(self) -> "TurnoCreate":
        if self.es_sobreturno:
            if self.color_sobreturno is None:
                raise ValueError(
                    "El sobreturno requiere un color_sobreturno"
                )
            if not _COLOR.fullmatch(self.color_sobreturno):
                raise ValueError(
                    "El color_sobreturno debe tener formato #RRGGBB"
                )
        elif self.color_sobreturno is not None:
            raise ValueError(
                "El color_sobreturno solo aplica a los sobreturnos"
            )
        return self


class TurnoReprogramar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inicio: datetime | None = None
    profesional_id: uuid.UUID | None = None
    sillon_id: uuid.UUID | None = None
    prestacion_id: uuid.UUID | None = None

    @field_validator("inicio")
    @classmethod
    def _inicio_con_zona(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _exigir_zona(value)

    @model_validator(mode="after")
    def _exigir_cambio(self) -> "TurnoReprogramar":
        if not self.model_fields_set:
            raise ValueError(
                "Indicá al menos un cambio: inicio, profesional, sillón "
                "o prestación"
            )
        return self


class TurnoEstadoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: _ESTADO_DESTINO


class TurnoListado(BaseModel):
    """Bounded agenda query: at most 62 days, filters are optional."""

    model_config = ConfigDict(extra="forbid")

    desde: date
    hasta: date
    profesional_id: uuid.UUID | None = None
    sillon_id: uuid.UUID | None = None
    estado: _ESTADO | None = None

    @model_validator(mode="after")
    def _rango_acotado(self) -> "TurnoListado":
        if self.hasta < self.desde:
            raise ValueError("hasta debe ser posterior o igual a desde")
        if (self.hasta - self.desde).days > 62:
            raise ValueError("El rango de consulta no puede superar 62 días")
        return self


class TurnoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    sillon_id: uuid.UUID
    prestacion_id: uuid.UUID | None
    inicio: datetime
    fin: datetime
    estado: _ESTADO
    origen: _ORIGEN
    es_sobreturno: bool
    color_sobreturno: str | None
    token_publico: str | None
    is_active: bool
