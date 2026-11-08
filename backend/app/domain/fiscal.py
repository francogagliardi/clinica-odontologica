"""Pure fiscal domain: QR payloads, state machine and retry schedule (C-14).

No I/O. The fiscal QR follows the AFIP verifier format (design D7) so a real
scanner would decode it; the internal QR is a local, clearly non-fiscal proof
that survives an ARCA outage. Dates are Argentine (UTC-3, no DST) because the
clinic operates on local days, while fiscal timestamps are stored in UTC.

The state machine mirrors the CHECK in `app.models.fiscal` (design D5):

- `pendiente` → `emitido|fallido`
- `fallido` → `pendiente` only through a manual retry
- `emitido` is terminal
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import parse_qs, urlparse

from app.domain.turnos import TZ_ARGENTINA

CENTAVO = Decimal("0.01")

ESTADOS_FISCALES = frozenset({"pendiente", "emitido", "fallido"})
TIPOS_COMPROBANTE = frozenset({"B", "C"})
AMBIENTE_HOMOLOGACION = "homologacion"

# AFIP QR `tipoCmp`: 6 = Factura B, 11 = Factura C.
_TIPO_CMP_ARCA = {"B": 6, "C": 11}
_CONDICION_A_TIPO = {
    "responsable_inscripto": "B",
    "monotributista": "C",
}

QR_FISCAL_BASE = "https://www.afip.gob.ar/fe/qr/?p="
QR_INTERNO_BASE = "https://app.local/comprobantes/verificar?p="

BACKOFF_BASE_SEGUNDOS = 60
BACKOFF_MAXIMO_SEGUNDOS = 3600

_TRANSICIONES: dict[str, frozenset[str]] = {
    "pendiente": frozenset({"emitido", "fallido"}),
    "fallido": frozenset({"pendiente"}),
    "emitido": frozenset(),
}


def fecha_emision_local(momento: datetime) -> date:
    """Operating day in Argentina for an instant (UTC-3, design D7)."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(TZ_ARGENTINA).date()


def tipo_comprobante(condicion_emisor: str) -> str:
    """Factura B for a registered taxpayer, C for a monotributista (D6)."""
    tipo = _CONDICION_A_TIPO.get(condicion_emisor)
    if tipo is None:
        raise ValueError(
            "La condición del emisor debe ser 'responsable_inscripto' "
            "o 'monotributista'"
        )
    return tipo


def puede_transicionar(actual: str, nuevo: str) -> bool:
    """Same state is idempotent; anything else must be in the matrix."""
    if actual not in ESTADOS_FISCALES or nuevo not in ESTADOS_FISCALES:
        return False
    if actual == nuevo:
        return True
    return nuevo in _TRANSICIONES[actual]


def calcular_proximo_intento(
    intentos: int,
    *,
    ahora: datetime | None = None,
    base_segundos: int = BACKOFF_BASE_SEGUNDOS,
    maximo_segundos: int = BACKOFF_MAXIMO_SEGUNDOS,
) -> datetime:
    """Exponential backoff after the `intentos`-th failure (D4).

    The first failure waits one base interval, the second twice as much, and so
    on, capped so a lost job is retried within the hour.
    """
    if isinstance(intentos, bool) or not isinstance(intentos, int):
        raise ValueError("La cantidad de intentos debe ser un entero")
    if intentos < 1:
        raise ValueError("La cantidad de intentos debe ser mayor que cero")
    if base_segundos <= 0 or maximo_segundos <= 0:
        raise ValueError("El backoff debe ser positivo")

    espera = min(base_segundos * (2 ** (intentos - 1)), maximo_segundos)
    momento = ahora if ahora is not None else datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento + timedelta(seconds=espera)


def _importe_json(importe: Decimal | str | int) -> float:
    """JSON has no Decimal: quantize to cents before turning it into a number."""
    return float(
        Decimal(str(importe)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    )


def _codificar(datos: dict[str, object]) -> str:
    crudo = json.dumps(
        datos, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return base64.urlsafe_b64encode(crudo).decode("ascii").rstrip("=")


def _decodificar_payload(url: str) -> dict[str, object]:
    parametros = parse_qs(urlparse(url).query)
    payload = parametros.get("p", [None])[0]
    if not payload:
        raise ValueError("El QR no tiene payload verificable")
    relleno = "=" * (-len(payload) % 4)
    try:
        crudo = base64.urlsafe_b64decode(payload + relleno)
        datos = json.loads(crudo)
    except (ValueError, TypeError) as exc:
        raise ValueError("El payload del QR no es decodificable") from exc
    if not isinstance(datos, dict):
        raise ValueError("El payload del QR no es un objeto JSON")
    return datos


def construir_qr_fiscal(
    *,
    cuit: str,
    punto_venta: int,
    tipo: str,
    numero_fiscal: int,
    importe: Decimal | str | int,
    cae: str,
    fecha: date,
    documento_receptor: str,
    tipo_documento_receptor: str = "96",
) -> str:
    """Build the AFIP verifier URL with the fields a scanner expects (D7)."""
    if tipo not in TIPOS_COMPROBANTE:
        raise ValueError("El tipo de comprobante debe ser 'B' o 'C'")
    if len(cae) != 14 or not cae.isdigit():
        raise ValueError("El CAE debe tener 14 dígitos")
    if punto_venta <= 0 or numero_fiscal <= 0:
        raise ValueError("El punto de venta y el número deben ser positivos")

    datos: dict[str, object] = {
        "ver": 1,
        "fecha": fecha.isoformat(),
        "cuit": int(cuit),
        "ptoVta": int(punto_venta),
        "tipoCmp": _TIPO_CMP_ARCA[tipo],
        "nroCmp": int(numero_fiscal),
        "importe": _importe_json(importe),
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": int(tipo_documento_receptor),
        "nroDocRec": int(documento_receptor),
        "tipoCodAut": "E",
        "codAut": cae,
    }
    return QR_FISCAL_BASE + _codificar(datos)


def construir_qr_interno(
    *,
    comprobante_id: uuid.UUID | str,
    numero_interno: int,
    importe: Decimal | str | int,
    fecha: date,
) -> str:
    """Build the local verification URL; it never looks like a fiscal receipt."""
    if numero_interno <= 0:
        raise ValueError("El número interno debe ser positivo")
    datos: dict[str, object] = {
        "tipo": "INTERNO",
        "comprobante_id": str(comprobante_id),
        "numero_interno": int(numero_interno),
        "importe": _importe_json(importe),
        "fecha": fecha.isoformat(),
    }
    return QR_INTERNO_BASE + _codificar(datos)


def decodificar_qr(url: str) -> dict[str, object]:
    """Decode either QR (fiscal or internal) back to its JSON payload."""
    return _decodificar_payload(url)
