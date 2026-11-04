"""Pydantic schemas for the clinical record (C-11).

Every request forbids extra fields so a typo cannot silently change clinical
data (R-01/R-02). The server computes consent hashes and attachment metadata;
the client only sends the declared inputs.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import clinica as dominio_clinica
from app.domain import consentimientos


class HistoriaClinicaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: uuid.UUID


class HistoriaClinicaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    paciente_id: uuid.UUID
    abierta_por: uuid.UUID
    fecha_apertura: datetime
    is_active: bool


def _texto_clinico(value: str) -> str:
    limpio = value.strip()
    if not limpio:
        raise ValueError("El texto de la evolución no puede estar vacío")
    return limpio


class EvolucionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1)
    rectifica_a: uuid.UUID | None = None

    @field_validator("texto")
    @classmethod
    def _texto_obligatorio(cls, value: str) -> str:
        return _texto_clinico(value)


class EvolucionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1)

    @field_validator("texto")
    @classmethod
    def _texto_obligatorio(cls, value: str) -> str:
        return _texto_clinico(value)


class FirmaRequest(BaseModel):
    """Empty body on purpose: signing cannot smuggle a content change."""

    model_config = ConfigDict(extra="forbid")


class EvolucionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    historia_id: uuid.UUID
    profesional_id: uuid.UUID
    creado_por: uuid.UUID
    fecha: datetime
    texto: str
    firmada: bool
    firmada_por: uuid.UUID | None
    fecha_firma: datetime | None
    rectifica_a: uuid.UUID | None
    rectificada_por: uuid.UUID | None
    is_active: bool


class AdjuntoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    historia_id: uuid.UUID
    nombre: str
    mime: str
    tamano: int
    subido_por: uuid.UUID
    created_at: datetime
    is_active: bool


class ConsentimientoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str
    texto_version: str

    @field_validator("tipo")
    @classmethod
    def _tipo_valido(cls, value: str) -> str:
        if not consentimientos.tipo_valido(value):
            raise ValueError("Tipo de consentimiento no válido")
        return value

    @field_validator("texto_version")
    @classmethod
    def _version_valida(cls, value: str) -> str:
        if not consentimientos.version_conocida(value):
            raise ValueError("Versión de texto de consentimiento desconocida")
        return value


class ConsentimientoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    paciente_id: uuid.UUID
    tipo: str
    texto_version: str
    texto_hash: str
    firma_ref: str
    fecha: datetime
    registrado_por: uuid.UUID
    is_active: bool


class HallazgoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pieza: int
    cara: str
    estado: str
    diagnostico: str | None = None
    cie10: str | None = None
    fecha: date | None = None

    @field_validator("pieza")
    @classmethod
    def _pieza_fdi(cls, value: int) -> int:
        if not dominio_clinica.pieza_fdi_valida(value):
            raise ValueError("La pieza no es una pieza FDI válida")
        return value

    @field_validator("cara")
    @classmethod
    def _cara_valida(cls, value: str) -> str:
        if not dominio_clinica.cara_valida(value):
            raise ValueError("La cara no es una cara dental válida")
        return value

    @field_validator("estado")
    @classmethod
    def _estado_valido(cls, value: str) -> str:
        if not dominio_clinica.estado_valido(value):
            raise ValueError("El estado clínico no es válido")
        return value

    @field_validator("cie10")
    @classmethod
    def _cie10_valido(cls, value: str | None) -> str | None:
        if not dominio_clinica.cie10_valido(value):
            raise ValueError("El código CIE-10 no tiene un formato válido")
        return value

    @field_validator("diagnostico")
    @classmethod
    def _diagnostico_opcional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        return limpio or None


class HallazgoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    pieza: int
    cara: str
    estado: str
    diagnostico: str | None
    cie10: str | None
    fecha: date


class OdontogramaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None
    hallazgos: list[HallazgoResponse]
