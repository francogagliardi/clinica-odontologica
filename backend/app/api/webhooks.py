"""Public WhatsApp webhook: signature verification and idempotent processing."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError

from app.api.deps import (
    client_ip,
    dispositivo,
    get_configuracion_fiscal,
    get_mercadopago_client,
    get_redis,
    get_settings,
    get_uow,
)
from app.application.cobros import conciliar_pago
from app.application.comprobantes import ConfiguracionFiscal
from app.application.webhooks import firma_valida, procesar_webhook
from app.core.settings import Settings
from app.infrastructure.mercadopago import (
    FirmaInvalida,
    MercadoPagoClient,
    validar_firma_webhook,
)
from app.infrastructure.uow import UnitOfWork
from app.schemas.caja import (
    WebhookMercadoPagoRequest,
    WebhookMercadoPagoResponse,
)
from app.schemas.comunicaciones import WebhookRequest, WebhookResponse

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/whatsapp",
    response_model=WebhookResponse,
    summary="Recibir respuestas de WhatsApp (firma HMAC obligatoria)",
)
async def whatsapp_webhook(
    request: Request,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
    redis_client: Annotated[object | None, Depends(get_redis)],
    x_hub_signature_256: Annotated[
        str | None, Header(alias="X-Hub-Signature-256")
    ] = None,
) -> WebhookResponse:
    raw_body = await request.body()
    if not firma_valida(
        raw_body, x_hub_signature_256, settings.whatsapp_app_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma del webhook inválida",
        )
    try:
        payload = WebhookRequest.model_validate_json(raw_body)
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.errors()[0]["msg"],
        ) from error

    resultados = await procesar_webhook(
        uow,
        payload.mensajes,
        base_url=settings.app_base_url,
        ttl_minutos=settings.lista_espera_oferta_ttl_minutos,
        redis_client=redis_client,
    )
    return WebhookResponse(resultados=resultados)


@router.post(
    "/mercadopago",
    response_model=WebhookMercadoPagoResponse,
    summary="Recibir pagos de Mercado Pago (firma HMAC obligatoria)",
)
async def mercadopago_webhook(
    request: Request,
    payload: WebhookMercadoPagoRequest,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
    mp_client: Annotated[
        MercadoPagoClient, Depends(get_mercadopago_client)
    ],
    fiscal: Annotated[
        ConfiguracionFiscal, Depends(get_configuracion_fiscal)
    ],
    redis_client: Annotated[object | None, Depends(get_redis)],
    x_signature: Annotated[
        str | None, Header(alias="x-signature")
    ] = None,
    x_request_id: Annotated[
        str | None, Header(alias="x-request-id")
    ] = None,
) -> WebhookMercadoPagoResponse:
    """Public endpoint: only the signature authorizes (design D2/D8).

    The body contributes the payment id; the amount and state always come from
    `consultar_pago`, so a tampered body cannot invent money.
    """
    if not x_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta la firma del webhook",
        )
    data_id = payload.data.id
    if not data_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El webhook no incluye data.id",
        )
    try:
        validar_firma_webhook(
            x_signature,
            settings.mp_webhook_secret,
            data_id=data_id,
            request_id=x_request_id,
        )
    except FirmaInvalida as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma del webhook inválida",
        ) from error

    pago = await mp_client.consultar_pago(data_id)
    if pago is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago desconocido",
        )

    await conciliar_pago(
        uow,
        pago,
        fiscal=fiscal,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
        redis_client=redis_client,
    )
    return WebhookMercadoPagoResponse(recibido=True)
