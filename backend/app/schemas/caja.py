"""Pydantic schemas for payments and Mercado Pago webhooks (C-13, D11).

The client sends references and amounts only: state, provider ids and links are
server-owned. Every body is strict (`extra='forbid'`) except the provider
webhook, which is documented as `extra='ignore'` because Mercado Pago adds
fields and the real trust boundary is the signature plus `consultar_pago`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TipoCobro = Literal["sena", "tratamiento", "otro"]
MedioCobro = Literal["efectivo", "mercadopago"]
EstadoCobro = Literal[
    "pendiente", "aprobado", "rechazado", "reembolsado", "perdido"
]
TipoMovimiento = Literal["ingreso", "gasto", "deuda"]
EstadoCaja = Literal["abierta", "cerrada"]


class CobroCreate(BaseModel):
    """POST /cobros: amount and references, never a client-chosen state."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: uuid.UUID
    tipo: TipoCobro
    medio: MedioCobro = "efectivo"
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    turno_id: uuid.UUID | None = None
    presupuesto_id: uuid.UUID | None = None


class CobroResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    paciente_id: uuid.UUID
    turno_id: uuid.UUID | None
    presupuesto_id: uuid.UUID | None
    tipo: TipoCobro
    medio: MedioCobro
    estado: EstadoCobro
    monto: Decimal
    proveedor_preferencia_id: str | None
    link_pago: str | None
    fecha_operacion: date
    fecha_conciliacion: datetime | None
    saldo_pendiente: Decimal | None = None


class WebhookData(BaseModel):
    """`data.id` is the only body field the reconciliation trusts."""

    model_config = ConfigDict(extra="ignore")

    id: str | None = None


class WebhookMercadoPagoRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str | None = None
    action: str | None = None
    data: WebhookData = Field(default_factory=WebhookData)


class WebhookMercadoPagoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recibido: bool = True


class CajaAbrir(BaseModel):
    """Opening amount may be zero but never negative (RN-AD-03)."""

    model_config = ConfigDict(extra="forbid")

    monto_apertura: Decimal = Field(
        ge=0, max_digits=12, decimal_places=2
    )
    fecha: date | None = None


class MovimientoCajaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: TipoMovimiento
    concepto: str = Field(min_length=1, max_length=200)
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    medio: MedioCobro = "efectivo"
    cobro_id: uuid.UUID | None = None

    @field_validator("concepto")
    @classmethod
    def _concepto_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("El concepto no puede estar vacío")
        return limpio


class CajaCerrar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monto_contado: Decimal = Field(
        ge=0, max_digits=12, decimal_places=2
    )
    observaciones: str | None = Field(default=None, max_length=500)


class CajaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    fecha: date
    estado: EstadoCaja
    monto_apertura: Decimal
    monto_sistema_efectivo: Decimal | None
    monto_contado: Decimal | None
    diferencia: Decimal | None
    cerrada_por: uuid.UUID | None
    cerrada_at: datetime | None
    observaciones: str | None


class MovimientoCajaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    caja_id: uuid.UUID
    tipo: TipoMovimiento
    concepto: str
    monto: Decimal
    medio: MedioCobro
    cobro_id: uuid.UUID | None
    creado_por: uuid.UUID | None
    created_at: datetime


class ArqueoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fecha: date
    caja_id: uuid.UUID | None
    estado: EstadoCaja | None
    monto_apertura: Decimal
    ingresos_efectivo: Decimal
    gastos_efectivo: Decimal
    monto_sistema_efectivo: Decimal
    ingresos_mercadopago: Decimal
    deudas: Decimal
    monto_contado: Decimal | None
    diferencia: Decimal | None
    movimientos: list[MovimientoCajaResponse]
