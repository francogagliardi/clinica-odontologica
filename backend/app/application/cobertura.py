"""Preventive coverage validation (C-14, design D8).

Read-only and consultative: it reuses the same provider and arithmetic as the
budget (`LocalCoberturaProvider` + `calcular_item`) so coverage has one
definition. v1 only knows local agreement rules; caps, frequencies and an
external nomenclature are explicitly out of scope and never invented.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException, status

from app.application.presupuestos import (
    CoberturaNoDisponible,
    CoberturaProvider,
    calcular_item,
)
from app.infrastructure.uow import UnitOfWork
from app.models.comercial import Prestacion
from app.models.pacientes import Paciente

CUBIERTA = "cubierta"
NO_CUBIERTA = "no_cubierta"
PENDIENTE = "pendiente_verificacion"

CERO = Decimal("0.00")
CERO_PORCENTAJE = Decimal("0")


@dataclass(frozen=True)
class ResultadoCobertura:
    """What the backoffice may show before booking or quoting a service."""

    estado: str
    cobertura_porcentaje: Decimal | None
    cobertura_monto: Decimal | None
    copago_monto: Decimal | None


def _pendiente() -> ResultadoCobertura:
    return ResultadoCobertura(PENDIENTE, None, None, None)


async def _resolver_paciente(
    uow: UnitOfWork, consultorio_id: uuid.UUID, paciente_id: uuid.UUID
) -> Paciente:
    paciente = await uow.pacientes.get(paciente_id)
    if (
        paciente is None
        or paciente.consultorio_id != consultorio_id
        or not paciente.is_active
        or paciente.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado",
        )
    return paciente


async def _resolver_prestacion(
    uow: UnitOfWork, consultorio_id: uuid.UUID, prestacion_id: uuid.UUID
) -> Prestacion:
    prestacion = await uow.prestaciones.get(prestacion_id)
    if (
        prestacion is None
        or not prestacion.is_active
        or prestacion.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestación no encontrada",
        )
    return prestacion


async def validar_cobertura(
    uow: UnitOfWork,
    provider: CoberturaProvider,
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    prestacion_id: uuid.UUID,
) -> tuple[Paciente, Prestacion, ResultadoCobertura]:
    """Classify coverage without writing or blocking (RN-OS-01/02).

    An agreement without a membership number cannot be considered covered
    (RN-OS-01), so it is pending even if the local rules exist.
    """
    paciente = await _resolver_paciente(uow, consultorio_id, paciente_id)
    prestacion = await _resolver_prestacion(
        uow, consultorio_id, prestacion_id
    )

    if paciente.obra_social_id is not None and not paciente.nro_afiliado:
        return paciente, prestacion, _pendiente()

    try:
        cobertura = await provider.resolver(uow, paciente)
    except CoberturaNoDisponible:
        cobertura = None
    if cobertura is None:
        return paciente, prestacion, _pendiente()

    if not cobertura.cubre(prestacion.codigo):
        monto, copago = calcular_item(prestacion.precio_base, 1, CERO)
        return (
            paciente,
            prestacion,
            ResultadoCobertura(NO_CUBIERTA, CERO_PORCENTAJE, monto, copago),
        )

    monto, copago = calcular_item(
        prestacion.precio_base, 1, cobertura.cobertura_porcentaje
    )
    return (
        paciente,
        prestacion,
        ResultadoCobertura(
            CUBIERTA,
            cobertura.cobertura_porcentaje,
            monto,
            copago,
        ),
    )
