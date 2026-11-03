"""Pure availability calculation: schedule, duration and blocks (C-04)."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.domain.agenda import (
    ARGENTINA_OFFSET,
    AgendaConfig,
    RangoBloqueo,
    calcular_disponibilidad,
)

# 2026-11-02 is a Monday (ISO 0).
LUNES = date(2026, 11, 2)
AGENDA = AgendaConfig(
    duracion_base_min=60,
    dias_atencion=(0, 1, 2, 3, 4),
    hora_desde=time(9, 0),
    hora_hasta=time(12, 0),
)


def _bloqueo(hora_desde: int, hora_hasta: int) -> RangoBloqueo:
    return RangoBloqueo(
        desde=datetime.combine(
            LUNES, time(hora_desde, 0), tzinfo=ARGENTINA_OFFSET
        ),
        hasta=datetime.combine(
            LUNES, time(hora_hasta, 0), tzinfo=ARGENTINA_OFFSET
        ),
    )


def test_dia_fuera_de_atencion_devuelve_lista_vacia() -> None:
    agenda = AgendaConfig(
        duracion_base_min=60,
        dias_atencion=(2,),
        hora_desde=time(9, 0),
        hora_hasta=time(12, 0),
    )
    assert calcular_disponibilidad(fecha=LUNES, agenda=agenda) == []


def test_slots_consecutivos_con_duracion_de_prestacion() -> None:
    slots = calcular_disponibilidad(
        fecha=LUNES, agenda=AGENDA, duracion_min=45
    )
    assert len(slots) == 4
    assert slots[0].inicio == datetime(
        2026, 11, 2, 9, 0, tzinfo=ARGENTINA_OFFSET
    )
    assert slots[-1].fin == datetime(
        2026, 11, 2, 12, 0, tzinfo=ARGENTINA_OFFSET
    )
    for anterior, siguiente in zip(slots, slots[1:]):
        assert anterior.fin == siguiente.inicio


def test_sin_prestacion_usa_duracion_base() -> None:
    slots = calcular_disponibilidad(fecha=LUNES, agenda=AGENDA)
    assert len(slots) == 3
    assert all(
        slot.fin - slot.inicio == timedelta(minutes=60) for slot in slots
    )


def test_ultimo_slot_incompleto_se_descarta() -> None:
    agenda = AgendaConfig(
        duracion_base_min=60,
        dias_atencion=(0,),
        hora_desde=time(9, 0),
        hora_hasta=time(11, 30),
    )
    slots = calcular_disponibilidad(fecha=LUNES, agenda=agenda)
    assert len(slots) == 2
    assert slots[-1].fin == datetime(
        2026, 11, 2, 11, 0, tzinfo=ARGENTINA_OFFSET
    )


def test_bloqueo_dentro_del_horario_quita_slots() -> None:
    bloqueo = RangoBloqueo(
        desde=datetime(2026, 11, 2, 10, 0, tzinfo=ARGENTINA_OFFSET),
        hasta=datetime(2026, 11, 2, 10, 30, tzinfo=ARGENTINA_OFFSET),
    )
    slots = calcular_disponibilidad(
        fecha=LUNES, agenda=AGENDA, bloqueos=[bloqueo]
    )
    assert [slot.inicio.hour for slot in slots] == [9, 11]


def test_bloqueo_fuera_del_horario_no_cambia_nada() -> None:
    slots = calcular_disponibilidad(
        fecha=LUNES, agenda=AGENDA, bloqueos=[_bloqueo(7, 8)]
    )
    assert len(slots) == 3


def test_sin_bloqueos_del_profesional_consultado() -> None:
    """Only the blocks passed by the caller (the queried resource) apply."""
    slots = calcular_disponibilidad(fecha=LUNES, agenda=AGENDA, bloqueos=())
    assert len(slots) == 3


def test_bloqueo_parcial_recorta_varios_slots() -> None:
    bloqueo = RangoBloqueo(
        desde=datetime(2026, 11, 2, 9, 30, tzinfo=ARGENTINA_OFFSET),
        hasta=datetime(2026, 11, 2, 10, 30, tzinfo=ARGENTINA_OFFSET),
    )
    slots = calcular_disponibilidad(
        fecha=LUNES, agenda=AGENDA, bloqueos=[bloqueo]
    )
    assert [slot.inicio.hour for slot in slots] == [11]


def test_slots_en_offset_argentina() -> None:
    slots = calcular_disponibilidad(fecha=LUNES, agenda=AGENDA)
    assert all(
        slot.inicio.utcoffset() == timedelta(hours=-3) for slot in slots
    )
    assert slots[0].inicio.tzinfo == ARGENTINA_OFFSET


def test_duracion_no_positiva_es_error_de_programacion() -> None:
    with pytest.raises(ValueError):
        calcular_disponibilidad(fecha=LUNES, agenda=AGENDA, duracion_min=0)
