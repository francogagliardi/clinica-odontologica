"""Mercado Pago provider abstraction and webhook signature (C-13, D2/D3).

Only the simulated provider exists in v1: it never opens a socket, never needs
real credentials and never generates a cost (R-12). The webhook signature is a
plain HMAC-SHA256 over the official manifest
`id:<data.id>;request-id:<x-request-id>;ts:<ts>;`, checked against
`MP_WEBHOOK_SECRET` with a clock tolerance so a replayed header eventually
expires. The provider is the only source of payment truth: the webhook body
contributes the id, never the amount or the state.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import NamedTuple, Protocol

from app.core.settings import Settings

TOLERANCIA_FIRMA_SEGUNDOS = 300
_ESTADOS_PAGO = frozenset({"aprobado", "rechazado", "pendiente"})


class FirmaInvalida(ValueError):
    """The `x-signature` header is absent, malformed, expired or forged."""


class PreferenciaPago(NamedTuple):
    """Checkout preference created by the provider."""

    preferencia_id: str
    link_pago: str


class PagoNormalizado(NamedTuple):
    """Provider-independent payment, the only truth the webhook reconciles."""

    proveedor_pago_id: str
    cobro_id: uuid.UUID
    estado: str
    monto: Decimal
    moneda: str
    fecha: datetime


class MercadoPagoClient(Protocol):
    """Minimal payment gateway contract (design D3)."""

    async def crear_preferencia(
        self,
        cobro_id: uuid.UUID,
        monto: Decimal,
        descripcion: str,
    ) -> PreferenciaPago:
        """Create a checkout preference and return its id and payment link."""

    async def consultar_pago(
        self, pago_id: str
    ) -> PagoNormalizado | None:
        """Return the normalized payment or None when the id is unknown."""


class TestMercadoPagoClient:
    """Trial-layer client: records intent locally, never calls Mercado Pago."""

    __test__ = False

    def __init__(self) -> None:
        self.preferencias: dict[uuid.UUID, PreferenciaPago] = {}
        self._pagos: dict[str, PagoNormalizado] = {}

    async def crear_preferencia(
        self,
        cobro_id: uuid.UUID,
        monto: Decimal,
        descripcion: str,
    ) -> PreferenciaPago:
        preferencia_id = f"test-pref-{uuid.uuid4()}"
        link_pago = (
            "https://sandbox.mercadopago.test/checkout/"
            f"{preferencia_id}"
        )
        preferencia = PreferenciaPago(
            preferencia_id=preferencia_id, link_pago=link_pago
        )
        self.preferencias[cobro_id] = preferencia
        return preferencia

    def simular_pago(self, pago: PagoNormalizado) -> None:
        """Register what the provider "answered" for the webhook tests."""
        if pago.estado not in _ESTADOS_PAGO:
            raise ValueError(
                "El estado simulado debe ser 'aprobado', 'rechazado' "
                "o 'pendiente'"
            )
        self._pagos[pago.proveedor_pago_id] = pago

    async def consultar_pago(
        self, pago_id: str
    ) -> PagoNormalizado | None:
        return self._pagos.get(pago_id)


def get_mercadopago_client(settings: Settings) -> MercadoPagoClient:
    """Only the trial client exists in v1 (R-12); anything else fails loudly."""
    if settings.mp_provider != "test":  # pragma: no cover - config guard
        raise RuntimeError(
            "MP_PROVIDER distinto de 'test' no está soportado en v1: "
            "no se cobran credenciales reales"
        )
    return TestMercadoPagoClient()


def construir_manifest(
    *,
    data_id: str | None,
    request_id: str | None,
    ts: str,
) -> str:
    """Official Mercado Pago manifest used as the HMAC message."""
    partes: list[str] = []
    if data_id:
        partes.append(f"id:{data_id}")
    if request_id:
        partes.append(f"request-id:{request_id}")
    partes.append(f"ts:{ts}")
    return ";".join(partes) + ";"


def _parsear_firma(x_signature: str) -> tuple[int, str]:
    partes: dict[str, str] = {}
    for trozo in x_signature.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if "=" not in trozo:
            raise FirmaInvalida("Encabezado x-signature mal formado")
        clave, _, valor = trozo.partition("=")
        partes[clave.strip()] = valor.strip()

    ts_raw = partes.get("ts")
    v1 = partes.get("v1")
    if not ts_raw or not v1:
        raise FirmaInvalida("Encabezado x-signature incompleto")
    try:
        ts = int(ts_raw)
    except ValueError as error:
        raise FirmaInvalida("El ts de la firma no es un entero") from error
    return ts, v1


def validar_firma_webhook(
    x_signature: str | None,
    secret: str,
    *,
    data_id: str | None = None,
    request_id: str | None = None,
    now: datetime | None = None,
    tolerancia_segundos: int = TOLERANCIA_FIRMA_SEGUNDOS,
) -> None:
    """Raise `FirmaInvalida` unless the header is authentic and fresh.

    Returns `None` on success so the webhook can simply proceed (design D2).
    A missing secret is a configuration error but is treated as an invalid
    signature, never as an open door.
    """
    if not secret:
        raise FirmaInvalida("MP_WEBHOOK_SECRET no está configurado")
    if not x_signature:
        raise FirmaInvalida("Falta el encabezado x-signature")

    ts, v1 = _parsear_firma(x_signature)
    instante = now or datetime.now(timezone.utc)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    if abs(int(instante.timestamp()) - ts) > tolerancia_segundos:
        raise FirmaInvalida("El timestamp de la firma está fuera de tolerancia")

    manifest = construir_manifest(
        data_id=data_id, request_id=request_id, ts=str(ts)
    )
    esperado = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(esperado, v1.lower()):
        raise FirmaInvalida("La firma del webhook no coincide")
