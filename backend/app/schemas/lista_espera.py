"""Schemas for the waiting list and its public offer (C-10, D12).

The client never sends `orden`, `estado` or the retention fields: they are
derived by the service and the database (RORO, `extra="forbid"`).
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.publico import SenaPublica

EstadoListaEspera = Literal["pendiente", "ofrecido", "convertido", "vencido"]


class EntradaListaEsperaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: uuid.UUID
    prestacion_id: uuid.UUID
    profesional_id: uuid.UUID | None = None


class EntradaListaEsperaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    paciente_id: uuid.UUID
    prestacion_id: uuid.UUID
    profesional_id: uuid.UUID | None
    orden: int
    estado: EstadoListaEspera
    oferta_profesional_id: uuid.UUID | None
    oferta_sillon_id: uuid.UUID | None
    oferta_inicio: datetime | None
    oferta_fin: datetime | None
    oferta_expira_en: datetime | None
    turno_id: uuid.UUID | None
    is_active: bool


class EntradaListaEsperaListado(BaseModel):
    """Bounded filters of the queue listing (D12)."""

    model_config = ConfigDict(extra="forbid")

    estado: EstadoListaEspera | None = None
    prestacion_id: uuid.UUID | None = None
    profesional_id: uuid.UUID | None = None


class PrestacionOfertaPublica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    codigo: str
    nombre: str
    duracion_min: int


class ProfesionalOfertaPublico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    matricula: str
    especialidades: list[str]


class OfertaPublicaResponse(BaseModel):
    """What the patient sees: no phone, DNI or internal identifiers (D8)."""

    model_config = ConfigDict(extra="forbid")

    prestacion: PrestacionOfertaPublica
    profesional: ProfesionalOfertaPublico
    inicio: datetime
    fin: datetime
    vence_en: datetime


class OfertaAceptadaResponse(BaseModel):
    """The offer became an appointment in the retained resources."""

    model_config = ConfigDict(extra="forbid")

    turno_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str
    sena: SenaPublica


class OfertaRechazoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: Literal["vencido"]
