"""Receipt endpoints: consult, simulated delivery and manual retry (C-14).

The matrix follows D11: admin/reception/dentist/auditor read; only admin and
reception write (retry/send). Creation belongs to the payment hook, so there is
no POST /comprobantes endpoint.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    client_ip,
    dispositivo,
    get_consultorio_demo_id,
    get_redis,
    get_uow,
    get_whatsapp_client,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.application.comprobantes import (
    enviar_comprobante,
    listar_comprobantes,
    obtener_comprobante,
    reintentar_comprobante,
)
from app.infrastructure.uow import UnitOfWork
from app.infrastructure.whatsapp import WhatsAppClient
from app.models.fiscal import Comprobante, ComprobanteEnvio
from app.models.security import Usuario
from app.schemas.comprobantes import (
    ComprobanteEnvioCreate,
    ComprobanteEnvioResponse,
    ComprobanteResponse,
    EstadoFiscal,
    TipoComprobante,
)

router = APIRouter(prefix="/comprobantes", tags=["comprobantes"])

_lectura = require_role(
    "administrador", "recepcionista", "odontologo", "auditor"
)
_escritura = require_role("administrador", "recepcionista")


def _to_response(comprobante: Comprobante) -> ComprobanteResponse:
    return ComprobanteResponse(
        id=comprobante.id,
        consultorio_id=comprobante.consultorio_id,
        cobro_id=comprobante.cobro_id,
        paciente_id=comprobante.paciente_id,
        tipo=comprobante.tipo,  # type: ignore[arg-type]
        ambiente=comprobante.ambiente,
        estado=comprobante.estado,  # type: ignore[arg-type]
        numero_interno=comprobante.numero_interno,
        punto_venta=comprobante.punto_venta,
        numero_fiscal=comprobante.numero_fiscal,
        cae=comprobante.cae,
        cae_vencimiento=comprobante.cae_vencimiento,
        qr_interno=comprobante.qr_interno,
        qr_fiscal=comprobante.qr_fiscal,
        receptor_nombre=comprobante.receptor_nombre,
        receptor_documento=comprobante.receptor_documento,
        receptor_tipo_documento=comprobante.receptor_tipo_documento,
        condicion_fiscal_receptor=comprobante.condicion_fiscal_receptor,
        condicion_fiscal_emisor=comprobante.condicion_fiscal_emisor,
        importe_total=comprobante.importe_total,
        fecha_emision=comprobante.fecha_emision,
        fecha_emision_fiscal=comprobante.fecha_emision_fiscal,
        intentos=comprobante.intentos,
        proximo_intento=comprobante.proximo_intento,
        ultimo_error=comprobante.ultimo_error,
        created_at=comprobante.created_at,
    )


def _to_envio(envio: ComprobanteEnvio) -> ComprobanteEnvioResponse:
    return ComprobanteEnvioResponse(
        id=envio.id,
        comprobante_id=envio.comprobante_id,
        canal=envio.canal,  # type: ignore[arg-type]
        destino=envio.destino,
        estado=envio.estado,  # type: ignore[arg-type]
        proveedor_mensaje_id=envio.proveedor_mensaje_id,
        error=envio.error,
        creado_por=envio.creado_por,
        created_at=envio.created_at,
    )


@router.get(
    "",
    response_model=list[ComprobanteResponse],
    summary="Listar comprobantes con filtros declarados",
    dependencies=[
        Depends(
            reject_unexpected_query_except(
                "cobro_id",
                "paciente_id",
                "estado",
                "desde",
                "hasta",
                "tipo",
            )
        )
    ],
)
async def list_comprobantes(
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    cobro_id: uuid.UUID | None = None,
    paciente_id: uuid.UUID | None = None,
    estado: EstadoFiscal | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    tipo: TipoComprobante | None = None,
) -> list[ComprobanteResponse]:
    comprobantes = await listar_comprobantes(
        uow,
        consultorio_id=consultorio_id,
        cobro_id=cobro_id,
        paciente_id=paciente_id,
        estado=estado,
        desde=desde,
        hasta=hasta,
        tipo=tipo,
    )
    return [_to_response(comprobante) for comprobante in comprobantes]


@router.get(
    "/{comprobante_id}",
    response_model=ComprobanteResponse,
    summary="Ficha de un comprobante (CAE y QR cuando está emitido)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_comprobante(
    comprobante_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ComprobanteResponse:
    comprobante = await obtener_comprobante(
        uow,
        consultorio_id=consultorio_id,
        comprobante_id=comprobante_id,
    )
    return _to_response(comprobante)


@router.post(
    "/{comprobante_id}/enviar",
    response_model=ComprobanteEnvioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar la factura por WhatsApp simulado",
    dependencies=[Depends(reject_unexpected_query)],
)
async def enviar(
    comprobante_id: uuid.UUID,
    payload: ComprobanteEnvioCreate,
    request: Request,
    response: Response,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    cliente: Annotated[
        WhatsAppClient, Depends(get_whatsapp_client)
    ],
) -> ComprobanteEnvioResponse:
    envio, creado = await enviar_comprobante(
        uow,
        cliente,
        consultorio_id=consultorio_id,
        comprobante_id=comprobante_id,
        canal=payload.canal,
        destino=payload.destino,
        usuario=current_user,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    response.status_code = (
        status.HTTP_201_CREATED if creado else status.HTTP_200_OK
    )
    return _to_envio(envio)


@router.post(
    "/{comprobante_id}/reintentar",
    response_model=ComprobanteResponse,
    summary="Reintentar la emisión fiscal (emitido es no-op)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def reintentar(
    comprobante_id: uuid.UUID,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    redis_client: Annotated[object | None, Depends(get_redis)],
) -> ComprobanteResponse:
    comprobante = await reintentar_comprobante(
        uow,
        consultorio_id=consultorio_id,
        comprobante_id=comprobante_id,
        usuario=current_user,
        redis_client=redis_client,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(comprobante)
