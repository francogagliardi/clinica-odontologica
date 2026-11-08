"""Pure cash-register domain: local dates, arqueo and payment rules (C-13).

No I/O here. `fecha_local` is the single place that turns an instant into the
Argentine operating day (design D6); the arqueo only lets **cash** move the
expected drawer, while Mercado Pago income and debts are reported apart
(RN-AD-03). The state machine and validators mirror the CHECKs in
`app.models.caja` so the application can reject with a clear message before
PostgreSQL has to (design D9).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from app.domain.turnos import TZ_ARGENTINA

CENTAVO = Decimal("0.01")

TIPOS_COBRO = frozenset({"sena", "tratamiento", "otro"})
MEDIOS_PAGO = frozenset({"efectivo", "mercadopago"})
ESTADOS_COBRO = frozenset(
    {"pendiente", "aprobado", "rechazado", "reembolsado", "perdido"}
)
TIPOS_MOVIMIENTO = frozenset({"ingreso", "gasto", "deuda"})

# A rejected deposit is terminal: retrying means creating a new `Cobro`. A lost
# or refunded payment cannot go back either (design D4/D5/D7).
_TRANSICIONES: dict[str, frozenset[str]] = {
    "pendiente": frozenset({"aprobado", "rechazado", "perdido"}),
    "aprobado": frozenset({"reembolsado", "perdido"}),
    "rechazado": frozenset(),
    "reembolsado": frozenset(),
    "perdido": frozenset(),
}


class MovimientoResumen(NamedTuple):
    """Minimal movement shape needed to compute the arqueo (no ORM here)."""

    tipo: str
    medio: str
    monto: Decimal


class TotalesArqueo(NamedTuple):
    """Snapshot of the day; only `monto_sistema_efectivo` is the drawer."""

    monto_apertura: Decimal
    ingresos_efectivo: Decimal
    gastos_efectivo: Decimal
    monto_sistema_efectivo: Decimal
    ingresos_mercadopago: Decimal
    deudas: Decimal


def _decimal(valor: Decimal | str | int) -> Decimal:
    """Normalize an amount to cents without going through binary floats."""
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def fecha_local(
    momento: datetime, tz: timezone = TZ_ARGENTINA
) -> date:
    """Operating day in Argentina for an instant (design D6).

    Naive datetimes are treated as UTC, which is how PostgreSQL timestamptz
    values arrive when the tzinfo was dropped. 02:30Z becomes the previous
    local day; 03:00Z is local midnight of the next one.
    """
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(tz).date()


def calcular_arqueo(
    monto_apertura: Decimal | str | int,
    movimientos: Iterable[MovimientoResumen],
) -> TotalesArqueo:
    """Expected cash = opening + cash income - cash expenses (RN-AD-03).

    Mercado Pago income never enters the drawer, and debts are only reported:
    they explain a future obligation, not money that moved today.
    """
    apertura = _decimal(monto_apertura)
    ingresos_efectivo = Decimal("0.00")
    gastos_efectivo = Decimal("0.00")
    ingresos_mercadopago = Decimal("0.00")
    deudas = Decimal("0.00")

    for movimiento in movimientos:
        monto = _decimal(movimiento.monto)
        if movimiento.tipo == "deuda":
            deudas += monto
        elif movimiento.tipo == "ingreso" and movimiento.medio == "efectivo":
            ingresos_efectivo += monto
        elif movimiento.tipo == "ingreso" and movimiento.medio == "mercadopago":
            ingresos_mercadopago += monto
        elif movimiento.tipo == "gasto" and movimiento.medio == "efectivo":
            gastos_efectivo += monto

    return TotalesArqueo(
        monto_apertura=apertura,
        ingresos_efectivo=_decimal(ingresos_efectivo),
        gastos_efectivo=_decimal(gastos_efectivo),
        monto_sistema_efectivo=_decimal(
            apertura + ingresos_efectivo - gastos_efectivo
        ),
        ingresos_mercadopago=_decimal(ingresos_mercadopago),
        deudas=_decimal(deudas),
    )


def diferencia_cierre(
    monto_contado: Decimal | str | int,
    monto_sistema_efectivo: Decimal | str | int,
) -> Decimal:
    """Positive means surplus, negative means shortage (cierre con 0)."""
    return _decimal(_decimal(monto_contado) - _decimal(monto_sistema_efectivo))


def puede_transicionar(actual: str, nuevo: str) -> bool:
    """Same state is idempotent; anything else must be in the matrix."""
    if actual not in ESTADOS_COBRO or nuevo not in ESTADOS_COBRO:
        return False
    if actual == nuevo:
        return True
    return nuevo in _TRANSICIONES[actual]


def validar_monto(monto: Decimal | str | int) -> Decimal:
    """A payment or movement is always strictly positive (D9)."""
    valor = _decimal(monto)
    if valor <= 0:
        raise ValueError("El monto debe ser mayor que cero")
    return valor


def validar_tipo(tipo: str) -> str:
    if tipo not in TIPOS_COBRO:
        raise ValueError(
            "El tipo de cobro debe ser 'sena', 'tratamiento' u 'otro'"
        )
    return tipo


def validar_medio(medio: str) -> str:
    if medio not in MEDIOS_PAGO:
        raise ValueError("El medio debe ser 'efectivo' o 'mercadopago'")
    return medio


def validar_referencias(
    tipo: str,
    *,
    turno_id: object | None = None,
    presupuesto_id: object | None = None,
) -> None:
    """D9: each type accepts exactly its own reference and no other."""
    validar_tipo(tipo)
    if tipo == "sena":
        if turno_id is None or presupuesto_id is not None:
            raise ValueError(
                "Una seña exige un turno y no admite presupuesto"
            )
    elif tipo == "tratamiento":
        if presupuesto_id is None or turno_id is not None:
            raise ValueError(
                "Un cobro de tratamiento exige un presupuesto y no un turno"
            )
    else:
        if turno_id is not None or presupuesto_id is not None:
            raise ValueError("Un cobro 'otro' no admite turno ni presupuesto")
