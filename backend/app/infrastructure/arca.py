"""ARCA (ex-AFIP) issuance provider boundary (C-14, design D3, R-12).

v1 has no certificates, no sockets and no real authorization: `TestArcaClient`
derives a deterministic 14-digit CAE from the idempotency key, so a retry after
a persistence failure gets the same CAE and PostgreSQL's unique index remains
the last line of defence. `get_arca_client` rejects any other provider instead
of silently emitting with real credentials.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Protocol

from app.core.settings import Settings
from app.domain.fiscal import fecha_emision_local

CAE_DIGITOS = 14
VENCIMIENTO_DIAS = 10


class ArcaError(RuntimeError):
    """The provider could not complete the emission."""


@dataclass(frozen=True)
class DatosReceptor:
    """Minimal receiver snapshot: consumer with DNI in v1 (design D6)."""

    nombre: str
    documento: str
    tipo_documento: str = "DNI"
    condicion_fiscal: str = "consumidor_final"


@dataclass(frozen=True)
class ResultadoEmision:
    """What a successful authorization returns: CAE and its expiry."""

    cae: str
    cae_vencimiento: date


class ArcaClient(Protocol):
    """Same contract the future certified adapter must implement."""

    async def emitir(
        self,
        *,
        clave_idempotencia: str,
        tipo: str,
        punto_venta: int,
        importe: Decimal,
        receptor: DatosReceptor,
    ) -> ResultadoEmision:
        """Authorize one receipt and return its CAE."""


def _cae_para(clave_idempotencia: str) -> str:
    """Stable 14-digit CAE: same key, same authorization (D5)."""
    digest = hashlib.sha256(clave_idempotencia.encode("utf-8")).hexdigest()
    return f"{int(digest, 16) % (10**CAE_DIGITOS):0{CAE_DIGITOS}d}"


class TestArcaClient:
    """Trial-layer client: deterministic, in-memory, never touches the network."""

    __test__ = False

    def __init__(
        self,
        *,
        vencimiento_dias: int = VENCIMIENTO_DIAS,
        disponible: bool = True,
    ) -> None:
        self._vencimiento_dias = vencimiento_dias
        self._disponible = disponible
        self._fallos_restantes = 0
        self.llamadas: list[dict[str, object]] = []

    @property
    def disponible(self) -> bool:
        return self._disponible

    @disponible.setter
    def disponible(self, valor: bool) -> None:
        self._disponible = valor

    def simular_fallo(self, veces: int = 1) -> None:
        """Make the next `veces` emissions fail explicitly (injectable fault)."""
        if isinstance(veces, bool) or not isinstance(veces, int):
            raise ValueError("La cantidad de fallos debe ser un entero")
        if veces < 0:
            raise ValueError("La cantidad de fallos no puede ser negativa")
        self._fallos_restantes = veces

    async def emitir(
        self,
        *,
        clave_idempotencia: str,
        tipo: str,
        punto_venta: int,
        importe: Decimal,
        receptor: DatosReceptor,
    ) -> ResultadoEmision:
        self.llamadas.append(
            {
                "clave_idempotencia": clave_idempotencia,
                "tipo": tipo,
                "punto_venta": punto_venta,
                "importe": importe,
                "receptor": receptor,
            }
        )
        if self._fallos_restantes > 0:
            self._fallos_restantes -= 1
            raise ArcaError("Fallo simulado de ARCA")
        if not self._disponible:
            raise ArcaError("ARCA no disponible")

        hoy = fecha_emision_local(datetime.now(timezone.utc))
        return ResultadoEmision(
            cae=_cae_para(clave_idempotencia),
            cae_vencimiento=hoy + timedelta(days=self._vencimiento_dias),
        )


def get_arca_client(settings: Settings) -> ArcaClient:
    """Only the trial client exists in v1 (R-12); anything else fails loudly."""
    if settings.arca_provider != "test":
        raise RuntimeError(
            "ARCA_PROVIDER distinto de 'test' no está soportado en v1"
        )
    return TestArcaClient()
