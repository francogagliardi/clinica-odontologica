"""Pure availability calculation (C-04/C-06, RN-TU-01/02/07).

No I/O: C-06 reuses this function to discount existing appointments and blocks.
Time zone is the fixed Argentina offset (UTC-3, no DST) for v1.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

ARGENTINA_OFFSET = timezone(timedelta(hours=-3))


@dataclass(frozen=True)
class AgendaConfig:
    """Validated base schedule of a professional."""

    duracion_base_min: int
    dias_atencion: tuple[int, ...]
    hora_desde: time
    hora_hasta: time


@dataclass(frozen=True)
class RangoBloqueo:
    """A block interval that removes overlapping slots (RN-TU-07)."""

    desde: datetime
    hasta: datetime


@dataclass(frozen=True)
class Slot:
    """A bookable interval in Argentina local time."""

    inicio: datetime
    fin: datetime


def _aware(value: datetime) -> datetime:
    """Treat naive datetimes as Argentina local time (defensive)."""
    return value if value.tzinfo is not None else value.replace(
        tzinfo=ARGENTINA_OFFSET
    )


def _se_solapa(
    inicio: datetime, fin: datetime, bloqueo: RangoBloqueo
) -> bool:
    return inicio < _aware(bloqueo.hasta) and fin > _aware(bloqueo.desde)


def calcular_disponibilidad(
    *,
    fecha: date,
    agenda: AgendaConfig,
    duracion_min: int | None = None,
    bloqueos: tuple[RangoBloqueo, ...] | list[RangoBloqueo] = (),
    turnos: tuple[RangoBloqueo, ...] | list[RangoBloqueo] = (),
    retenciones: tuple[RangoBloqueo, ...] | list[RangoBloqueo] = (),
) -> list[Slot]:
    """Return consecutive free slots for `fecha`, excluding occupied ranges.

    - A weekday outside `dias_atencion` yields no slots.
    - The slot duration is the service duration or the professional base one
      (RN-TU-02).
    - The last slot is discarded when it does not fit before `hora_hasta`.
    - Slots overlapping a block (RN-TU-07), an active turn (RN-TU-01) or a live
      waiting-list offer (RN-TU-05) are excluded.
    """
    if fecha.weekday() not in agenda.dias_atencion:
        return []

    duracion = (
        duracion_min
        if duracion_min is not None
        else agenda.duracion_base_min
    )
    if duracion <= 0:
        raise ValueError("La duración del slot debe ser positiva")

    cursor = datetime.combine(
        fecha, agenda.hora_desde, tzinfo=ARGENTINA_OFFSET
    )
    limite = datetime.combine(
        fecha, agenda.hora_hasta, tzinfo=ARGENTINA_OFFSET
    )
    paso = timedelta(minutes=duracion)
    ocupados = tuple(bloqueos) + tuple(turnos) + tuple(retenciones)

    slots: list[Slot] = []
    while cursor + paso <= limite:
        fin = cursor + paso
        if not any(_se_solapa(cursor, fin, rango) for rango in ocupados):
            slots.append(Slot(inicio=cursor, fin=fin))
        cursor = fin
    return slots
