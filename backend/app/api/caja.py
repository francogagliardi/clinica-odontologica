"""Cash register endpoints (C-13, design D8/D10).

The matrix is explicit: admin and reception operate the register, the auditor
only reads, and the dentist/assistant have no access. There is deliberately no
DELETE route: a closed day is history, not something to erase.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    client_ip,
    dispositivo,
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.application.caja import (
    abrir_caja,
    calcular_arqueo_dia,
    cerrar_caja,
    listar_movimientos,
    obtener_caja,
    registrar_movimiento,
)
from app.infrastructure.uow import UnitOfWork
from app.models.caja import CajaDiaria, MovimientoCaja
from app.models.security import Usuario
from app.schemas.caja import (
    ArqueoResponse,
    CajaAbrir,
    CajaCerrar,
    CajaResponse,
    MovimientoCajaCreate,
    MovimientoCajaResponse,
)

router = APIRouter(prefix="/caja", tags=["caja"])

_lectura = require_role("administrador", "recepcionista", "auditor")
_escritura = require_role("administrador", "recepcionista")


def _to_caja(caja: CajaDiaria) -> CajaResponse:
    return CajaResponse(
        id=caja.id,
        consultorio_id=caja.consultorio_id,
        fecha=caja.fecha,
        estado=caja.estado,
        monto_apertura=caja.monto_apertura,
        monto_sistema_efectivo=caja.monto_sistema_efectivo,
        monto_contado=caja.monto_contado,
        diferencia=caja.diferencia,
        cerrada_por=caja.cerrada_por,
        cerrada_at=caja.cerrada_at,
        observaciones=caja.observaciones,
    )


def _to_movimiento(movimiento: MovimientoCaja) -> MovimientoCajaResponse:
    return MovimientoCajaResponse(
        id=movimiento.id,
        caja_id=movimiento.caja_id,
        tipo=movimiento.tipo,
        concepto=movimiento.concepto,
        monto=movimiento.monto,
        medio=movimiento.medio,
        cobro_id=movimiento.cobro_id,
        creado_por=movimiento.creado_por,
        created_at=movimiento.created_at,
    )


@router.post(
    "/abrir",
    response_model=CajaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir la caja de una fecha local (una sola por día)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def abrir(
    payload: CajaAbrir,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> CajaResponse:
    caja = await abrir_caja(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        monto_apertura=payload.monto_apertura,
        fecha=payload.fecha,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_caja(caja)


@router.get(
    "",
    response_model=CajaResponse,
    summary="Ficha de la caja de una fecha",
    dependencies=[Depends(reject_unexpected_query_except("fecha"))],
)
async def read_caja(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    fecha: date | None = None,
) -> CajaResponse:
    return _to_caja(
        await obtener_caja(
            uow, consultorio_id=consultorio_id, fecha=fecha
        )
    )


@router.post(
    "/movimientos",
    response_model=MovimientoCajaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un ingreso, gasto o deuda en la caja abierta",
    dependencies=[Depends(reject_unexpected_query)],
)
async def create_movimiento(
    payload: MovimientoCajaCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> MovimientoCajaResponse:
    movimiento = await registrar_movimiento(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        datos=payload,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_movimiento(movimiento)


@router.get(
    "/movimientos",
    response_model=list[MovimientoCajaResponse],
    summary="Listar los movimientos de una fecha (vacío si no hay caja)",
    dependencies=[Depends(reject_unexpected_query_except("fecha"))],
)
async def list_movimientos(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    fecha: date | None = None,
) -> list[MovimientoCajaResponse]:
    _caja, movimientos = await listar_movimientos(
        uow, consultorio_id=consultorio_id, fecha=fecha
    )
    return [_to_movimiento(movimiento) for movimiento in movimientos]


@router.get(
    "/arqueo",
    response_model=ArqueoResponse,
    summary="Arqueo del día con efectivo, Mercado Pago y deudas separados",
    dependencies=[Depends(reject_unexpected_query_except("fecha"))],
)
async def arqueo(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    fecha: date | None = None,
) -> ArqueoResponse:
    dia = await calcular_arqueo_dia(
        uow, consultorio_id=consultorio_id, fecha=fecha
    )
    return ArqueoResponse(
        fecha=dia.fecha,
        caja_id=dia.caja.id if dia.caja is not None else None,
        estado=dia.caja.estado if dia.caja is not None else None,
        monto_apertura=dia.totales.monto_apertura,
        ingresos_efectivo=dia.totales.ingresos_efectivo,
        gastos_efectivo=dia.totales.gastos_efectivo,
        monto_sistema_efectivo=dia.totales.monto_sistema_efectivo,
        ingresos_mercadopago=dia.totales.ingresos_mercadopago,
        deudas=dia.totales.deudas,
        monto_contado=(
            dia.caja.monto_contado if dia.caja is not None else None
        ),
        diferencia=dia.caja.diferencia if dia.caja is not None else None,
        movimientos=[
            _to_movimiento(movimiento) for movimiento in dia.movimientos
        ],
    )


@router.post(
    "/cerrar",
    response_model=CajaResponse,
    summary="Cerrar la caja solo si la diferencia es cero",
    dependencies=[Depends(reject_unexpected_query)],
)
async def cerrar(
    payload: CajaCerrar,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> CajaResponse:
    caja = await cerrar_caja(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        monto_contado=payload.monto_contado,
        observaciones=payload.observaciones,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_caja(caja)
