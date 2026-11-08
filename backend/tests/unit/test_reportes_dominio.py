"""Pure report formulas: occupation, absence rates, backoff and UTC-3 dates.

No database and no network: these are the definitions D8 promises, verified
against values computed independently (the test file, not the implementation).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.reportes import (
    fecha_local,
    formatear_local,
    ocupacion_porcentaje,
    proximo_intento_con_backoff,
    rango_local_a_utc,
    sin_agenda,
    sin_cierres,
    tasa_ausentismo,
    tasa_no_asistencia,
)


@pytest.mark.parametrize(
    ("ocupados", "disponibles", "esperado"),
    (
        (240, 480, Decimal("50.00")),
        (0, 480, Decimal("0.00")),
        (480, 480, Decimal("100.00")),
        (100, 0, Decimal("0.00")),
        (1, 3, Decimal("33.33")),
        (2, 3, Decimal("66.67")),
    ),
)
def test_ocupacion_porcentaje(
    ocupados: int, disponibles: int, esperado: Decimal
) -> None:
    assert ocupacion_porcentaje(ocupados, disponibles) == esperado


def test_ocupacion_redondea_a_dos_decimales() -> None:
    resultado = ocupacion_porcentaje(Decimal("7.5"), 480)
    assert resultado == Decimal("1.56")
    assert resultado.as_tuple().exponent == -2


def test_sin_agenda_cuando_no_hay_minutos_disponibles() -> None:
    assert sin_agenda(0) is True
    assert sin_agenda(Decimal("0.00")) is True
    assert sin_agenda(240) is False


def test_tasas_de_ausentismo_sobre_turnos_cerrados() -> None:
    # 6 attended, 2 cancelled, 2 absent → 4/10 and 2/10.
    assert tasa_ausentismo(6, 2, 2) == Decimal("0.40")
    assert tasa_no_asistencia(6, 2, 2) == Decimal("0.20")
    assert sin_cierres(6, 2, 2) is False


def test_tasas_redondean_a_dos_decimales_con_medio_hacia_arriba() -> None:
    # 3/8 = 0.375 → 0.38 (half-up, not banker's rounding); 1/8 → 0.13.
    assert tasa_ausentismo(5, 2, 1) == Decimal("0.38")
    assert tasa_no_asistencia(5, 2, 1) == Decimal("0.13")
    assert tasa_ausentismo(1, 0, 0).as_tuple().exponent == -2


def test_denominador_cero_no_divide_y_marca_sin_cierres() -> None:
    assert tasa_ausentismo(0, 0, 0) == Decimal("0.00")
    assert tasa_no_asistencia(0, 0, 0) == Decimal("0.00")
    assert sin_cierres(0, 0, 0) is True


def test_backoff_exponencial_con_tope_de_sesenta_minutos() -> None:
    ahora = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
    assert proximo_intento_con_backoff(ahora, 0) == ahora + timedelta(
        minutes=1
    )
    assert proximo_intento_con_backoff(ahora, 1) == ahora + timedelta(
        minutes=2
    )
    assert proximo_intento_con_backoff(ahora, 2) == ahora + timedelta(
        minutes=4
    )
    assert proximo_intento_con_backoff(ahora, 5) == ahora + timedelta(
        minutes=32
    )
    assert proximo_intento_con_backoff(ahora, 6) == ahora + timedelta(
        minutes=60
    )
    assert proximo_intento_con_backoff(ahora, 20) == ahora + timedelta(
        minutes=60
    )
    assert proximo_intento_con_backoff(
        ahora, 3, tope_minutos=10
    ) == ahora + timedelta(minutes=8)
    assert proximo_intento_con_backoff(
        ahora, 10, tope_minutos=10
    ) == ahora + timedelta(minutes=10)


def test_rango_local_a_utc_es_semiabierto_y_usa_utc_menos_tres() -> None:
    desde, hasta = rango_local_a_utc(
        date(2026, 11, 4), date(2026, 11, 5)
    )
    assert desde == datetime(2026, 11, 4, 3, 0, tzinfo=timezone.utc)
    assert hasta == datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc)
    assert desde < hasta


def test_un_turno_de_las_23_30_utc3_cae_en_su_dia_local() -> None:
    # 2026-11-05T02:30:00Z is 2026-11-04 23:30 in Argentina.
    momento = datetime(2026, 11, 5, 2, 30, tzinfo=timezone.utc)
    assert fecha_local(momento) == date(2026, 11, 4)
    # 03:00Z is the next local midnight.
    assert fecha_local(
        datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)
    ) == date(2026, 11, 5)


def test_formatear_local_devuelve_iso_con_offset_menos_tres() -> None:
    momento = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
    assert formatear_local(momento) == "2026-11-04T09:00:00-03:00"
