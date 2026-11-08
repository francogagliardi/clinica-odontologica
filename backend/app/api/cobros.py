"""Payment endpoints (C-13, design D8/D10).

Only the administrator and the receptionist create payments. Reads follow the
matrix: admin/reception/auditor all, dentist only their own rows. The public
Mercado Pago webhook lives in `api/webhooks.py`, not here.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    client_ip,
    dispositivo,
    get_configuracion_fiscal,
    get_consultorio_demo_id,
    get_mercadopago_client,
    get_redis,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.application.comprobantes import ConfiguracionFiscal
from app.application.cobros import (
    ComandoCobro,
    crear_cobro,
    listar_cobros,
    obtener_cobro,
    reembolsar_cobro,
)
from app.infrastructure.mercadopago import MercadoPagoClient
from app.infrastructure.uow import UnitOfWork
from app.models.caja import Cobro
from app.models.security import Usuario
from app.schemas.caja import CobroCreate, CobroResponse

router = APIRouter(prefix="/cobros", tags=["cobros"])

_lectura = require_role(
    "administrador", "odontologo", "recepcionista", "auditor"
)
_escritura = require_role("administrador", "recepcionista")


def _to_response(
    cobro: Cobro, saldo_pendiente: Decimal | None = None
) -> CobroResponse:
    return CobroResponse(
        id=cobro.id,
        consultorio_id=cobro.consultorio_id,
        paciente_id=cobro.paciente_id,
        turno_id=cobro.turno_id,
        presupuesto_id=cobro.presupuesto_id,
        tipo=cobro.tipo,
        medio=cobro.medio,
        estado=cobro.estado,
        monto=cobro.monto,
        proveedor_preferencia_id=cobro.proveedor_preferencia_id,
        link_pago=cobro.link_pago,
        fecha_operacion=cobro.fecha_operacion,
        fecha_conciliacion=cobro.fecha_conciliacion,
        saldo_pendiente=saldo_pendiente,
    )


@router.post(
    "",
    response_model=CobroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un cobro en efectivo o iniciar un pago Mercado Pago",
    dependencies=[Depends(reject_unexpected_query)],
)
async def create_cobro(
    payload: CobroCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    mp_client: Annotated[
        MercadoPagoClient, Depends(get_mercadopago_client)
    ],
    fiscal: Annotated[
        ConfiguracionFiscal, Depends(get_configuracion_fiscal)
    ],
    redis_client: Annotated[object | None, Depends(get_redis)],
) -> CobroResponse:
    cobro, saldo = await crear_cobro(
        uow,
        mp_client,
        consultorio_id=consultorio_id,
        usuario=current_user,
        comando=ComandoCobro(
            paciente_id=payload.paciente_id,
            tipo=payload.tipo,
            medio=payload.medio,
            monto=payload.monto,
            turno_id=payload.turno_id,
            presupuesto_id=payload.presupuesto_id,
        ),
        fiscal=fiscal,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
        redis_client=redis_client,
    )
    return _to_response(cobro, saldo)


@router.get(
    "",
    response_model=list[CobroResponse],
    summary="Listar cobros con filtros declarados",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "paciente_id",
                "turno_id",
                "presupuesto_id",
                "estado",
                "medio",
                "fecha_desde",
                "fecha_hasta",
                "profesional_id",
            )
        )
    ],
)
async def list_cobros(
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    paciente_id: uuid.UUID | None = None,
    turno_id: uuid.UUID | None = None,
    presupuesto_id: uuid.UUID | None = None,
    estado: str | None = None,
    medio: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    profesional_id: uuid.UUID | None = None,
) -> list[CobroResponse]:
    cobros = await listar_cobros(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        paciente_id=paciente_id,
        turno_id=turno_id,
        presupuesto_id=presupuesto_id,
        estado=estado,
        medio=medio,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        profesional_id=profesional_id,
    )
    return [_to_response(cobro) for cobro in cobros]


@router.get(
    "/{cobro_id}",
    response_model=CobroResponse,
    summary="Ficha de un cobro",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_cobro(
    cobro_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> CobroResponse:
    cobro, saldo = await obtener_cobro(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        cobro_id=cobro_id,
    )
    return _to_response(cobro, saldo)


@router.post(
    "/{cobro_id}/reembolsar",
    response_model=CobroResponse,
    summary="Reembolsar un cobro aprobado (solo estado y auditoría)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def reembolsar(
    cobro_id: uuid.UUID,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> CobroResponse:
    cobro = await reembolsar_cobro(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        cobro_id=cobro_id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(cobro)
