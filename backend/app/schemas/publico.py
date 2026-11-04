"""Public booking schemas (C-07).

The public payload never accepts a chair id or internal fields; the response
never exposes patient data or raw tokens beyond the one-time management URL.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.domain.pacientes import normalizar_dni, normalizar_telefono


class ProfesionalPublico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    matricula: str
    especialidades: list[str]


class PrestacionPublica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    codigo: str
    nombre: str
    duracion_min: int
    precio_base: Decimal
    especialidad: str | None
    requiere_sena: bool
    monto_sena: Decimal | None


class CatalogoPublico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    nombre: str
    profesionales: list[ProfesionalPublico]
    prestaciones: list[PrestacionPublica]
    plazo_cancelacion_horas: int
    politica_cancelacion: str
    politica_sena: str
    moneda: str = "ARS"


class SlotPublico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inicio: datetime
    fin: datetime


class ReservaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    apellido: str = Field(min_length=1, max_length=120)
    dni: str
    telefono: str
    email: str | None = Field(default=None, max_length=255)
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID | None = None
    inicio: datetime

    @field_validator("nombre", "apellido")
    @classmethod
    def _texto(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("El nombre y el apellido son obligatorios")
        return limpio

    @field_validator("dni")
    @classmethod
    def _dni(cls, value: str) -> str:
        return normalizar_dni(value)

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, value: str) -> str:
        return normalizar_telefono(value)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip().lower()
        if not limpio:
            return None
        if "@" not in limpio or "." not in limpio.split("@")[-1]:
            raise ValueError("El email no tiene un formato válido")
        return limpio

    @field_validator("inicio")
    @classmethod
    def _zona(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("El inicio debe incluir zona horaria")
        return value


class SenaPublica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requiere: bool
    monto: Decimal | None
    estado: str


class ReservaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turno_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str
    profesional: ProfesionalPublico
    prestacion: PrestacionPublica | None
    sena: SenaPublica
    gestion_url: str
    whatsapp_confirmacion: str
    plazo_cancelacion_horas: int
    politica_sena: str


class GestionTurnoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turno_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str
    profesional: ProfesionalPublico
    prestacion: PrestacionPublica | None
    sena: SenaPublica
    puede_confirmar: bool
    puede_cancelar: bool
    plazo_cancelacion_horas: int
    politica_sena: str


class AccionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: str
    sena_perdida: bool


class DisponibilidadQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fecha: date
    profesional_id: uuid.UUID
    prestacion_id: uuid.UUID | None = None
