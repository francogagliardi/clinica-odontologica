"""Pure turno domain: duration, agenda window, overlap and state machine (C-06)."""

from collections.abc import Iterable
from datetime import datetime, time, timedelta, timezone

TZ_ARGENTINA = timezone(timedelta(hours=-3))

ESTADOS_ACTIVOS = frozenset(
    {"reservado", "confirmado", "en_sala", "atendido"}
)
ESTADOS_TERMINALES = frozenset({"atendido", "cancelado", "ausente"})

_TRANSICIONES: dict[str, frozenset[str]] = {
    "reservado": frozenset({"confirmado", "cancelado", "ausente"}),
    "confirmado": frozenset({"en_sala", "cancelado", "ausente"}),
    "en_sala": frozenset({"atendido"}),
    "atendido": frozenset(),
    "cancelado": frozenset(),
    "ausente": frozenset(),
}


def calcular_fin(inicio: datetime, duracion_min: int) -> datetime:
    """Derive the end from the service/professional duration (RN-TU-02)."""
    if duracion_min <= 0:
        raise ValueError("La duración del turno debe ser mayor que cero")
    return inicio + timedelta(minutes=duracion_min)


def validar_ventana(
    inicio: datetime,
    fin: datetime,
    *,
    dias_atencion: Iterable[int],
    hora_desde: time,
    hora_hasta: time,
    tz: timezone = TZ_ARGENTINA,
) -> None:
    """The appointment must fit in the professional's configured agenda."""
    local_inicio = inicio.astimezone(tz)
    local_fin = fin.astimezone(tz)

    if local_inicio.weekday() not in set(dias_atencion):
        raise ValueError(
            "El día del turno no está en los días de atención del profesional"
        )
    if local_fin.date() != local_inicio.date():
        raise ValueError("El turno no puede cruzar la medianoche")
    if local_inicio.time() < hora_desde:
        raise ValueError(
            "El turno empieza antes del horario de atención del profesional"
        )
    if local_fin.time() > hora_hasta:
        raise ValueError(
            "El turno termina después del horario de atención del profesional"
        )


def se_solapan(
    inicio_a: datetime,
    fin_a: datetime,
    inicio_b: datetime,
    fin_b: datetime,
) -> bool:
    """Half-open intervals: back-to-back appointments do not overlap."""
    return inicio_a < fin_b and inicio_b < fin_a


def puede_transicionar(actual: str, nuevo: str) -> bool:
    """Same state is idempotent; anything else must be in the matrix."""
    if actual == nuevo:
        return True
    return nuevo in _TRANSICIONES.get(actual, frozenset())
