"""Pure report definitions: occupation, absence rates, backoff and local dates.

No I/O here. The formulas are the single definition D8 promises, so the
application layer never recomputes a rate in Python with different rounding:

- `ocupacion_porcentaje = ROUND(ocupados * 100.0 / disponibles, 2)`, or `0.00`
  when there is no configured agenda (denominator zero);
- `tasa_ausentismo = (cancelados + ausentes) / (atendidos + cancelados +
  ausentes)` and `tasa_no_asistencia = ausentes / denominador`, both `0.00`
  when there are no closed appointments (`sin_cierres`), rounded half-up to two
  decimals;
- the retry backoff is `min(2 ** intentos, tope)` minutes;
- `desde`/`hasta` are Argentine local dates and become the half-open
  `[desde 00:00 -03, hasta+1 00:00 -03)` `timestamptz` window, exactly like
  `GET /turnos`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.domain.turnos import TZ_ARGENTINA

PORCENTAJE = Decimal("0.01")
CENTESIMA = Decimal("0.01")
TOPE_BACKOFF_MINUTOS = 60


def _decimal(valor: Decimal | str | int) -> Decimal:
    return Decimal(str(valor))


def _tasas(
    atendidos: int, cancelados: int, ausentes: int
) -> tuple[Decimal, Decimal]:
    cerrados = int(atendidos) + int(cancelados) + int(ausentes)
    if cerrados <= 0:
        return Decimal("0.00"), Decimal("0.00")
    ausentismo = _decimal(cancelados + ausentes) / _decimal(cerrados)
    no_asistencia = _decimal(ausentes) / _decimal(cerrados)
    return (
        ausentismo.quantize(CENTESIMA, rounding=ROUND_HALF_UP),
        no_asistencia.quantize(CENTESIMA, rounding=ROUND_HALF_UP),
    )


def ocupacion_porcentaje(
    minutos_ocupados: Decimal | str | int,
    minutos_disponibles: Decimal | str | int,
) -> Decimal:
    """Occupied percentage against the configured agenda (0.00 if no agenda)."""
    disponibles = _decimal(minutos_disponibles)
    if disponibles <= 0:
        return Decimal("0.00")
    porcentaje = _decimal(minutos_ocupados) * Decimal("100") / disponibles
    return porcentaje.quantize(PORCENTAJE, rounding=ROUND_HALF_UP)


def sin_agenda(minutos_disponibles: Decimal | str | int) -> bool:
    """True when the professional has no configured hours in the range."""
    return _decimal(minutos_disponibles) <= 0


def tasa_ausentismo(atendidos: int, cancelados: int, ausentes: int) -> Decimal:
    """Cancelled + absent over every closed appointment (D8)."""
    return _tasas(atendidos, cancelados, ausentes)[0]


def tasa_no_asistencia(
    atendidos: int, cancelados: int, ausentes: int
) -> Decimal:
    """Absent over every closed appointment (D8)."""
    return _tasas(atendidos, cancelados, ausentes)[1]


def sin_cierres(atendidos: int, cancelados: int, ausentes: int) -> bool:
    """True when the denominator is zero; the caller reports 0.00, never NaN."""
    return int(atendidos) + int(cancelados) + int(ausentes) <= 0


def proximo_intento_con_backoff(
    ahora: datetime,
    intentos: int,
    *,
    tope_minutos: int = TOPE_BACKOFF_MINUTOS,
) -> datetime:
    """`min(2 ** intentos, tope)` minutes from now (D3).

    `intentos` is the count already consumed, so the first failure (1) waits two
    minutes. A naive `ahora` is treated as UTC; the result keeps its tzinfo.
    """
    if intentos < 0:
        raise ValueError("Los intentos no pueden ser negativos")
    if tope_minutos <= 0:
        raise ValueError("El tope del backoff debe ser positivo")
    momento = ahora
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    minutos = min(2**intentos, tope_minutos)
    return momento + timedelta(minutes=minutos)


def rango_local_a_utc(
    desde: date,
    hasta: date,
    tz: timezone = TZ_ARGENTINA,
) -> tuple[datetime, datetime]:
    """Half-open UTC window for a local date range (inclusive `hasta`)."""
    if desde > hasta:
        raise ValueError("La fecha desde no puede ser posterior a la hasta")
    inicio = datetime.combine(desde, time.min, tzinfo=tz)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=tz)
    return inicio, fin


def fecha_local(
    momento: datetime, tz: timezone = TZ_ARGENTINA
) -> date:
    """Operating day in Argentina for an instant (UTC-3)."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(tz).date()


def formatear_local(
    momento: datetime, tz: timezone = TZ_ARGENTINA
) -> str:
    """ISO-8601 string in UTC-3, used in reports and the artifact."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(tz).isoformat()
