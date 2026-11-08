"""Boundary and response schemas for the reports (C-15, design D8/D13).

Queries are strict (`extra='forbid'`) and share the same range rule: `desde` and
`hasta` are local UTC-3 dates, `hasta` cannot precede `desde`, the range may not
exceed 62 days and `limite` is 1..1000 with 500 as default.

Responses always include the metadata (`generado_en`, `desde`, `hasta`,
`zona_horaria='UTC-3'`, applied filters), the totals computed over the whole
range and a bounded detail with `total_detalle`/`detalle_truncado`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EstadoTurno = Literal[
    "reservado", "confirmado", "en_sala", "atendido", "cancelado", "ausente"
]
MedioCobro = Literal["efectivo", "mercadopago"]
EstadoCobro = Literal[
    "pendiente", "aprobado", "rechazado", "reembolsado", "perdido"
]
EstadoLiquidacion = Literal["borrador", "cerrada"]
ZonaHoraria = Literal["UTC-3"]


class ReporteRango(BaseModel):
    """Range/limit contract shared by the four reports."""

    model_config = ConfigDict(extra="forbid")

    desde: date
    hasta: date
    limite: int = Field(default=500, ge=1, le=1000)

    @model_validator(mode="after")
    def _rango_acotado(self) -> "ReporteRango":
        if self.hasta < self.desde:
            raise ValueError("hasta debe ser posterior o igual a desde")
        if (self.hasta - self.desde).days > 62:
            raise ValueError("El rango de consulta no puede superar 62 días")
        return self


class ReporteAgendaQuery(ReporteRango):
    profesional_id: uuid.UUID | None = None
    sillon_id: uuid.UUID | None = None
    estado: EstadoTurno | None = None


class ReporteAusentismoQuery(ReporteRango):
    profesional_id: uuid.UUID | None = None


class ReporteCajaQuery(ReporteRango):
    medio: MedioCobro | None = None
    estado: EstadoCobro | None = None


class ReporteLiquidacionesQuery(ReporteRango):
    obra_social_id: uuid.UUID | None = None
    estado: EstadoLiquidacion | None = None


class ReporteMetadata(BaseModel):
    """Common response metadata (D8/D13)."""

    model_config = ConfigDict(extra="forbid")

    generado_en: datetime
    desde: date
    hasta: date
    zona_horaria: ZonaHoraria = "UTC-3"
    filtros: dict[str, str | int | None] = Field(default_factory=dict)


class DetalleTurno(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turno_id: uuid.UUID
    paciente_id: uuid.UUID
    profesional_id: uuid.UUID
    sillon_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: EstadoTurno
    es_sobreturno: bool
    fecha_local: date


class AgendaProfesional(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    turnos: int
    minutos_disponibles: int
    minutos_ocupados: int
    minutos_sobreturno: int
    ocupacion_porcentaje: Decimal
    sin_agenda: bool


class AgendaSillon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sillon_id: uuid.UUID
    turnos: int


class ReporteAgendaResponse(ReporteMetadata):
    total_turnos: int
    por_estado: dict[str, int]
    cancelaciones: int
    por_profesional: list[AgendaProfesional]
    por_sillon: list[AgendaSillon]
    minutos_disponibles: int
    minutos_ocupados: int
    minutos_sobreturno: int
    ocupacion_porcentaje: Decimal
    sin_agenda: bool
    total_detalle: int
    detalle_truncado: bool
    detalle: list[DetalleTurno]


class AusentismoProfesional(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: uuid.UUID
    atendidos: int
    cancelados: int
    ausentes: int
    turnos_activos: int
    tasa_ausentismo: Decimal
    tasa_no_asistencia: Decimal
    sin_cierres: bool


class ReporteAusentismoResponse(ReporteMetadata):
    atendidos: int
    cancelados: int
    ausentes: int
    turnos_activos: int
    tasa_ausentismo: Decimal
    tasa_no_asistencia: Decimal
    sin_cierres: bool
    por_profesional: list[AusentismoProfesional]
    total_detalle: int
    detalle_truncado: bool
    detalle: list[DetalleTurno]


class MovimientoResumen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str
    medio: MedioCobro
    cantidad: int
    total: Decimal


class CajaReporte(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caja_id: uuid.UUID
    fecha: date
    estado: str
    monto_apertura: Decimal
    monto_sistema_efectivo: Decimal | None
    monto_contado: Decimal | None
    diferencia: Decimal | None


class DetalleCobro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cobro_id: uuid.UUID
    paciente_id: uuid.UUID
    turno_id: uuid.UUID | None
    presupuesto_id: uuid.UUID | None
    tipo: str
    medio: MedioCobro
    estado: EstadoCobro
    monto: Decimal
    fecha_operacion: date
    fecha_local: date


class ReporteCajaResponse(ReporteMetadata):
    total_aprobado: Decimal
    total_efectivo: Decimal
    total_mercadopago: Decimal
    total_gastos: Decimal
    total_deudas: Decimal
    por_estado: dict[str, int]
    movimientos: list[MovimientoResumen]
    cajas: list[CajaReporte]
    total_detalle: int
    detalle_truncado: bool
    detalle: list[DetalleCobro]


class LiquidacionEstado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_social_id: uuid.UUID
    obra_social_nombre: str
    estado: EstadoLiquidacion
    cantidad_liquidaciones: int
    total_cobertura: Decimal
    cantidad_practicas: int


class LiquidacionObraSocialResumen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obra_social_id: uuid.UUID
    obra_social_nombre: str
    cantidad_liquidaciones: int
    total_cobertura: Decimal
    cantidad_practicas: int


class PracticaPrestacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prestacion_codigo: str
    cantidad: int
    cobertura: Decimal


class DetalleLiquidacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    liquidacion_id: uuid.UUID
    obra_social_id: uuid.UUID
    estado: EstadoLiquidacion
    desde: date
    hasta: date
    total_cobertura: Decimal
    cantidad_practicas: int


class ReporteLiquidacionesResponse(ReporteMetadata):
    cantidad_liquidaciones: int
    total_cobertura: Decimal
    cantidad_practicas: int
    por_estado: list[LiquidacionEstado]
    por_obra_social: list[LiquidacionObraSocialResumen]
    por_prestacion: list[PracticaPrestacion]
    total_detalle: int
    detalle_truncado: bool
    detalle: list[DetalleLiquidacion]
