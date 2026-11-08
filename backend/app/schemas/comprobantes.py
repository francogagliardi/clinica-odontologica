"""Pydantic schemas for receipts, delivery and retry (C-14, design D13).

Every request body is strict (`extra='forbid'`). Responses deliberately omit
the raw provider payload and any certificate setting: only what the backoffice
needs to show the receipt is exposed.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

TipoComprobante = Literal["B", "C"]
EstadoFiscal = Literal["pendiente", "emitido", "fallido"]
CanalEnvio = Literal["whatsapp"]
EstadoEnvio = Literal["registrado", "fallido"]

_DESTINO_VALIDO = re.compile(r"^\+?[0-9]{7,15}$")


class ComprobanteEnvioCreate(BaseModel):
    """POST /comprobantes/{id}/enviar: channel and optional destination."""

    model_config = ConfigDict(extra="forbid")

    canal: CanalEnvio = "whatsapp"
    destino: str | None = None

    @field_validator("destino")
    @classmethod
    def _destino_valido(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        if not _DESTINO_VALIDO.match(limpio):
            raise ValueError("El destino no es un teléfono válido")
        return limpio


class ComprobanteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    cobro_id: uuid.UUID
    paciente_id: uuid.UUID
    tipo: TipoComprobante
    ambiente: str
    estado: EstadoFiscal
    numero_interno: int
    punto_venta: int
    numero_fiscal: int | None
    cae: str | None
    cae_vencimiento: date | None
    qr_interno: str
    qr_fiscal: str | None
    receptor_nombre: str
    receptor_documento: str
    receptor_tipo_documento: str
    condicion_fiscal_receptor: str
    condicion_fiscal_emisor: str
    importe_total: Decimal
    fecha_emision: date
    fecha_emision_fiscal: datetime | None
    intentos: int
    proximo_intento: datetime | None
    ultimo_error: str | None
    created_at: datetime


class ComprobanteEnvioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    comprobante_id: uuid.UUID
    canal: CanalEnvio
    destino: str
    estado: EstadoEnvio
    proveedor_mensaje_id: str | None
    error: str | None
    creado_por: uuid.UUID | None
    created_at: datetime
