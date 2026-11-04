"""Pure budget domain: states, transitions and money arithmetic (C-12).

No I/O here. Amounts travel as `Decimal` end to end; coverage is quantized with
ROUND_HALF_UP (Argentine commercial rule) and the copayment is obtained by
subtraction, so `cobertura_item + copago_item = total_item` always holds and no
cent is lost between lines and the header (design D4).
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

CENTAVO = Decimal("0.01")
CIEN = Decimal("100")

ESTADOS = frozenset(
    {"borrador", "aceptado", "rechazado", "en_curso", "finalizado"}
)
ESTADOS_COBERTURA = frozenset({"calculada", "pendiente_verificacion"})

# Same shape as `app.domain.turnos`: repeating the current state is idempotent
# and there is no way back to `borrador` (design D6).
_TRANSICIONES: dict[str, frozenset[str]] = {
    "borrador": frozenset({"aceptado", "rechazado"}),
    "aceptado": frozenset({"en_curso"}),
    "en_curso": frozenset({"finalizado"}),
    "rechazado": frozenset(),
    "finalizado": frozenset(),
}


class TotalesPresupuesto(NamedTuple):
    """Header totals derived from already-quantized line amounts."""

    subtotal: Decimal
    cobertura_calculada: Decimal
    copago: Decimal


def puede_transicionar(actual: str, nuevo: str) -> bool:
    """Same state is idempotent; anything else must be in the matrix."""
    if actual not in ESTADOS or nuevo not in ESTADOS:
        return False
    if actual == nuevo:
        return True
    return nuevo in _TRANSICIONES[actual]


def _cantidad_valida(cantidad: int) -> int:
    if isinstance(cantidad, bool) or not isinstance(cantidad, int):
        raise ValueError("La cantidad debe ser un entero")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    return cantidad


def _porcentaje_valido(porcentaje: Decimal) -> Decimal:
    valor = Decimal(porcentaje)
    if valor < 0 or valor > CIEN:
        raise ValueError("El porcentaje de cobertura debe estar entre 0 y 100")
    return valor


def total_item(precio_unitario: Decimal, cantidad: int) -> Decimal:
    """Exact line total: price is Numeric(12,2) and quantity is an integer."""
    precio = Decimal(precio_unitario)
    if precio < 0:
        raise ValueError("El precio unitario no puede ser negativo")
    _cantidad_valida(cantidad)
    return (precio * cantidad).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_item(
    precio_unitario: Decimal,
    cantidad: int,
    cobertura_porcentaje: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return `(cobertura_item, copago_item)` for one line (RN-OS-02).

    The copayment is the remainder, never a second percentage: a convention
    whose rules do not add up to 100 % still yields a coherent line.
    """
    porcentaje = _porcentaje_valido(cobertura_porcentaje)
    total = total_item(precio_unitario, cantidad)
    cobertura = (
        (total * porcentaje / CIEN).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    )
    if cobertura > total:
        cobertura = total
    return cobertura, total - cobertura


def calcular_presupuesto(
    items: Iterable[tuple[Decimal, Decimal]],
) -> TotalesPresupuesto:
    """Sum quantized lines; `subtotal = cobertura + copago` by construction."""
    subtotal = Decimal("0.00")
    cobertura = Decimal("0.00")
    copago = Decimal("0.00")
    for cobertura_item, copago_item in items:
        cobertura += cobertura_item
        copago += copago_item
        subtotal += cobertura_item + copago_item
    return TotalesPresupuesto(
        subtotal=subtotal.quantize(CENTAVO, rounding=ROUND_HALF_UP),
        cobertura_calculada=cobertura.quantize(
            CENTAVO, rounding=ROUND_HALF_UP
        ),
        copago=copago.quantize(CENTAVO, rounding=ROUND_HALF_UP),
    )
