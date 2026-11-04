"""Public WhatsApp webhook: signature verification and idempotent processing."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import ValidationError

from app.api.deps import get_settings, get_uow
from app.application.webhooks import firma_valida, procesar_webhook
from app.core.settings import Settings
from app.infrastructure.uow import UnitOfWork
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

    resultados = await procesar_webhook(uow, payload.mensajes)
    return WebhookResponse(resultados=resultados)
