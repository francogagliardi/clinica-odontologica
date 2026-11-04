"""Unit tests for turno duration, agenda window and state machine (C-06)."""

from datetime import datetime, time, timedelta, timezone

import pytest

from app.domain.turnos import (
    ESTADOS_ACTIVOS,
    ESTADOS_TERMINALES,
    calcular_fin,
    puede_transicionar,
    se_solapan,
    validar_ventana,
)

TZ = timezone(timedelta(hours=-3))
LUNES = datetime(2026, 11, 9, 9, 0, tzinfo=TZ)  # 2026-11-09 is a Monday.


def test_calcular_fin_usa_la_duracion_de_la_prestacion() -> None:
    fin = calcular_fin(LUNES, 90)
    assert fin == datetime(2026, 11, 9, 10, 30, tzinfo=TZ)
    assert fin.tzinfo == TZ


@pytest.mark.parametrize("duracion", [0, -1, -90])
def test_calcular_fin_rechaza_duracion_no_positiva(duracion: int) -> None:
    with pytest.raises(ValueError, match="duración"):
        calcular_fin(LUNES, duracion)


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        (LUNES, LUNES + timedelta(minutes=60)),  # 09:00–10:00
        (LUNES + timedelta(hours=2), LUNES + timedelta(hours=3)),  # 11:00–12:00
    ],
)
def test_ventana_acepta_turnos_dentro_de_la_agenda(
    inicio: datetime, fin: datetime
) -> None:
    validar_ventana(
        inicio,
        fin,
        dias_atencion=[0, 1, 2, 3, 4],
        hora_desde=time(9, 0),
        hora_hasta=time(12, 0),
    )


def test_ventana_acepta_los_bordes_exactos() -> None:
    validar_ventana(
        LUNES,
        datetime(2026, 11, 9, 12, 0, tzinfo=TZ),
        dias_atencion=[0],
        hora_desde=time(9, 0),
        hora_hasta=time(12, 0),
    )


def test_ventana_rechaza_dia_no_habilitado() -> None:
    with pytest.raises(ValueError, match="día"):
        validar_ventana(
            LUNES,
            LUNES + timedelta(minutes=60),
            dias_atencion=[5, 6],
            hora_desde=time(9, 0),
            hora_hasta=time(12, 0),
        )


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        (
            LUNES - timedelta(minutes=1),
            LUNES + timedelta(minutes=59),
        ),
        (
            datetime(2026, 11, 9, 11, 30, tzinfo=TZ),
            datetime(2026, 11, 9, 12, 30, tzinfo=TZ),
        ),
        (
            datetime(2026, 11, 9, 23, 30, tzinfo=TZ),
            datetime(2026, 11, 10, 0, 30, tzinfo=TZ),
        ),
    ],
)
def test_ventana_rechaza_turnos_fuera_de_horario(
    inicio: datetime, fin: datetime
) -> None:
    with pytest.raises(ValueError, match="medianoche|horario"):
        validar_ventana(
            inicio,
            fin,
            dias_atencion=[0, 1, 2, 3, 4],
            hora_desde=time(9, 0),
            hora_hasta=time(12, 0),
        )


def test_solapamiento_usa_intervalos_semiabiertos() -> None:
    base = LUNES
    assert se_solapan(base, base + timedelta(hours=1), base + timedelta(hours=1), base + timedelta(hours=2)) is False
    assert se_solapan(base, base + timedelta(hours=1), base + timedelta(minutes=30), base + timedelta(hours=2)) is True
    assert se_solapan(base, base + timedelta(hours=2), base + timedelta(minutes=30), base + timedelta(hours=1)) is True
    assert se_solapan(base, base + timedelta(hours=1), base + timedelta(hours=2), base + timedelta(hours=3)) is False


def test_transiciones_validas_de_la_maquina() -> None:
    assert puede_transicionar("reservado", "confirmado") is True
    assert puede_transicionar("confirmado", "en_sala") is True
    assert puede_transicionar("en_sala", "atendido") is True
    assert puede_transicionar("reservado", "cancelado") is True
    assert puede_transicionar("confirmado", "ausente") is True


def test_transiciones_invalidas_y_terminales() -> None:
    assert puede_transicionar("reservado", "atendido") is False
    assert puede_transicionar("cancelado", "confirmado") is False
    assert puede_transicionar("atendido", "en_sala") is False
    assert puede_transicionar("ausente", "cancelado") is False
    assert ESTADOS_TERMINALES == {"atendido", "cancelado", "ausente"}


def test_repetir_el_estado_es_idempotente() -> None:
    for estado in ESTADOS_ACTIVOS | ESTADOS_TERMINALES:
        assert puede_transicionar(estado, estado) is True
