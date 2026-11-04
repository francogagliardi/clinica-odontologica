"""Schemas for reminders, notifications and the WhatsApp webhook (C-09)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecordatorioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    turno_id: uuid.UUID
    ventana: str
    programado_para: datetime
    estado: str


class MensajeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    turno_id: uuid.UUID
    recordatorio_id: uuid.UUID | None
    plantilla: str
    estado_envio: str
    respuesta: str
    proveedor_mensaje_id: str | None
    intentos: int
    proximo_intento: datetime | None
    ultimo_error: str | None


class ReenvioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    estado_envio: str
    encolado: bool


class WebhookMensaje(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    telefono: str | None = None
    respuesta: str
    nueva_fecha: datetime | None = None


class WebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mensajes: list[WebhookMensaje] = Field(min_length=1)


class WebhookResultado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    aplicado: bool
    derivado: bool


class WebhookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resultados: list[WebhookResultado]
