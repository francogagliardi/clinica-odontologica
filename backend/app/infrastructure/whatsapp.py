"""WhatsApp provider abstraction (C-09, R-12: no real cost in v1)."""

import uuid
from typing import Protocol

from app.core.settings import Settings


class WhatsAppClient(Protocol):
    async def enviar(
        self,
        telefono: str,
        plantilla: str,
        variables: dict[str, object],
    ) -> str:
        """Send one template message and return the provider message id."""


class TestWhatsAppClient:
    """Trial-layer client: records the intent locally, never calls Meta."""

    __test__ = False

    def __init__(self) -> None:
        self.enviados: list[dict[str, object]] = []

    async def enviar(
        self,
        telefono: str,
        plantilla: str,
        variables: dict[str, object],
    ) -> str:
        self.enviados.append(
            {
                "telefono": telefono,
                "plantilla": plantilla,
                "variables": variables,
            }
        )
        return f"test-{uuid.uuid4()}"


def get_whatsapp_client(settings: Settings) -> WhatsAppClient:
    """Only the trial client exists in v1 (DD-03/SU-03)."""
    if settings.whatsapp_provider != "test":  # pragma: no cover - config guard
        raise RuntimeError(
            "WHATSAPP_PROVIDER distinto de 'test' no está soportado en v1"
        )
    return TestWhatsAppClient()
