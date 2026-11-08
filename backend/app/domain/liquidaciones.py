"""Pure insurance-settlement domain: totals, states and period rules (C-14).

No I/O. A settlement period is inclusive on both ends (the GiST constraint uses
`daterange(desde, hasta, '[]')`), so two periods that share a day overlap and
only truly contiguous dates are allowed. Closing freezes the totals and is
idempotent; a closed settlement is terminal (design D9).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

CENTAVO = Decimal("0.01")

ESTADOS = frozenset({"borrador", "cerrada"})

_TRANSICIONES: dict[str, frozenset[str]] = {
    "borrador": frozenset({"cerrada"}),
    "cerrada": frozenset(),
}


class TotalesLiquidacion(NamedTuple):
    """Frozen header totals derived from one coverage snapshot per line."""

    total_cobertura: Decimal
    cantidad_practicas: int


def _decimal(valor: Decimal | str | int) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def puede_transicionar(actual: str, nuevo: str) -> bool:
    """Same state is idempotent; anything else must be in the matrix."""
    if actual not in ESTADOS or nuevo not in ESTADOS:
        return False
    if actual == nuevo:
        return True
    return nuevo in _TRANSICIONES[actual]


def cerrar_estado(actual: str) -> str:
    """Move `borrador` to `cerrada`; repeating the close is a no-op (D9)."""
    if actual == "cerrada":
        return actual
    if actual != "borrador":
        raise ValueError("La liquidación debe estar en borrador para cerrarse")
    return "cerrada"


def validar_periodo(desde: date, hasta: date) -> tuple[date, date]:
    """A settlement always has a coherent, inclusive period."""
    if desde > hasta:
        raise ValueError("La fecha desde no puede ser posterior a la hasta")
    return desde, hasta


def se_solapan(
    desde_a: date, hasta_a: date, desde_b: date, hasta_b: date
) -> bool:
    """Inclusive overlap, matching the PostgreSQL exclusion constraint."""
    validar_periodo(desde_a, hasta_a)
    validar_periodo(desde_b, hasta_b)
    return desde_a <= hasta_b and desde_b <= hasta_a


def calcular_totales(
    coberturas: Iterable[Decimal | str | int],
) -> TotalesLiquidacion:
    """Sum covered amounts and count settled lines (D9 `SUM`/`COUNT`)."""
    total = Decimal("0.00")
    cantidad = 0
    for cobertura in coberturas:
        total += _decimal(cobertura)
        cantidad += 1
    return TotalesLiquidacion(
        total_cobertura=total.quantize(
            CENTAVO, rounding=ROUND_HALF_UP
        ),
        cantidad_practicas=cantidad,
    )
