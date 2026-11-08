"""Cash register use cases: open, movements, arqueo and close (C-13, D1/D10).

Every amount is `Decimal`; the expected drawer only moves with cash (RN-AD-03),
while Mercado Pago income and debts are reported apart. Closing locks the row
with `FOR UPDATE` and insists on a zero difference, so a day is never rewritten
silently after the fact.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.application.clinica import auditar
from app.domain.caja import (
    TotalesArqueo,
    calcular_arqueo,
    diferencia_cierre,
    fecha_local,
)
from app.infrastructure.uow import UnitOfWork
from app.models.caja import CajaDiaria, Cobro, MovimientoCaja
from app.models.security import Usuario
from app.schemas.caja import MovimientoCajaCreate


def ahora_utc() -> datetime:
    """Clock seam: the 23:30 local test freezes this function."""
    return datetime.now(timezone.utc)


def _sqlstate(error: BaseException) -> str | None:
    original = getattr(error, "orig", error)
    return getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=detail
    )


def fecha_operativa(fecha: date | None = None) -> date:
    return fecha or fecha_local(ahora_utc())


async def abrir_caja(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    monto_apertura: Decimal,
    fecha: date | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> CajaDiaria:
    """One register per consultorio and local date (RN-AD-03)."""
    dia = fecha_operativa(fecha)
    existente = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, dia
    )
    if existente is not None:
        raise _conflict("La caja de esa fecha ya existe")

    caja = CajaDiaria(
        consultorio_id=consultorio_id,
        fecha=dia,
        estado="abierta",
        monto_apertura=monto_apertura,
    )
    try:
        await uow.cajas.add(caja)
    except IntegrityError as error:
        if _sqlstate(error) == "23505":
            raise _conflict("La caja de esa fecha ya existe") from error
        raise

    await auditar(
        uow,
        accion="caja.abrir",
        entidad="caja",
        entidad_id=caja.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return caja


async def obtener_caja(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    fecha: date | None = None,
) -> CajaDiaria:
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, fecha_operativa(fecha)
    )
    if caja is None:
        raise _not_found("Caja no encontrada para la fecha")
    return caja


async def listar_movimientos(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    fecha: date | None = None,
) -> tuple[CajaDiaria | None, list[MovimientoCaja]]:
    """A date without a register answers an empty list, not a 404."""
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, fecha_operativa(fecha)
    )
    if caja is None:
        return None, []
    return caja, await uow.movimientos_caja.list_by_caja(caja.id)


async def _resolver_cobro(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    cobro_id: uuid.UUID,
) -> Cobro:
    cobro = await uow.cobros.get(cobro_id)
    if (
        cobro is None
        or cobro.consultorio_id != consultorio_id
        or cobro.deleted_at is not None
    ):
        raise _not_found("Cobro no encontrado")
    return cobro


async def registrar_movimiento(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    datos: MovimientoCajaCreate,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> MovimientoCaja:
    """Manual income/expense/debt over the open register of the local day."""
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, fecha_operativa(), for_update=True
    )
    if caja is None or caja.estado != "abierta":
        raise _conflict("La caja de la fecha no existe o está cerrada")

    if datos.cobro_id is not None:
        if datos.tipo != "ingreso":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Solo un ingreso puede vincularse a un cobro",
            )
        cobro = await _resolver_cobro(
            uow, consultorio_id, datos.cobro_id
        )
        if cobro.monto != datos.monto or cobro.medio != datos.medio:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="El movimiento no coincide con el cobro vinculado",
            )
        if (
            await uow.movimientos_caja.get_by_cobro(cobro.id)
            is not None
        ):
            raise _conflict("El cobro ya tiene un movimiento de caja")

    movimiento = MovimientoCaja(
        caja_id=caja.id,
        tipo=datos.tipo,
        concepto=datos.concepto,
        monto=datos.monto,
        medio=datos.medio,
        cobro_id=datos.cobro_id,
        creado_por=usuario.id,
    )
    try:
        await uow.movimientos_caja.add(movimiento)
    except IntegrityError as error:
        if _sqlstate(error) == "23505":
            raise _conflict(
                "El cobro ya tiene un movimiento de caja"
            ) from error
        raise

    await auditar(
        uow,
        accion="caja.movimiento",
        entidad="caja",
        entidad_id=caja.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return movimiento


@dataclass(frozen=True)
class ArqueoDia:
    fecha: date
    caja: CajaDiaria | None
    totales: TotalesArqueo
    movimientos: list[MovimientoCaja]


async def calcular_arqueo_dia(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    fecha: date | None = None,
) -> ArqueoDia:
    """Totals of the day; an unopened date is a coherent all-zero answer."""
    dia = fecha_operativa(fecha)
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, dia
    )
    movimientos = (
        await uow.movimientos_caja.list_by_caja(caja.id)
        if caja is not None
        else []
    )
    totales = calcular_arqueo(
        caja.monto_apertura if caja is not None else Decimal("0.00"),
        movimientos,
    )
    if (
        caja is not None
        and caja.estado == "cerrada"
        and caja.monto_sistema_efectivo is not None
    ):
        # The closing snapshot is immutable: report exactly what was signed.
        totales = totales._replace(
            monto_sistema_efectivo=caja.monto_sistema_efectivo
        )
    return ArqueoDia(
        fecha=dia, caja=caja, totales=totales, movimientos=movimientos
    )


async def cerrar_caja(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    monto_contado: Decimal,
    observaciones: str | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> CajaDiaria:
    """Snapshot the expected cash and require a zero difference (D10)."""
    dia = fecha_operativa()
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, dia, for_update=True
    )
    if caja is None:
        raise _not_found("Caja no encontrada para la fecha")
    if caja.estado != "abierta":
        raise _conflict("La caja ya está cerrada")

    movimientos = await uow.movimientos_caja.list_by_caja(caja.id)
    totales = calcular_arqueo(caja.monto_apertura, movimientos)
    diferencia = diferencia_cierre(
        monto_contado, totales.monto_sistema_efectivo
    )
    if diferencia != Decimal("0.00"):
        raise _conflict(
            "La caja no cierra: la diferencia debe ser cero "
            f"(diferencia {diferencia})"
        )

    caja.estado = "cerrada"
    caja.monto_sistema_efectivo = totales.monto_sistema_efectivo
    caja.monto_contado = monto_contado
    caja.diferencia = diferencia
    caja.cerrada_por = usuario.id
    caja.cerrada_at = ahora_utc()
    caja.observaciones = observaciones
    await uow.session.flush()

    await auditar(
        uow,
        accion="caja.cerrar",
        entidad="caja",
        entidad_id=caja.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return caja
