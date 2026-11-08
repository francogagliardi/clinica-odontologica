"""C-14 pure settlement domain: totals, transitions and period coherence (D9)."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.liquidaciones import (
    TotalesLiquidacion,
    calcular_totales,
    cerrar_estado,
    puede_transicionar,
    se_solapan,
    validar_periodo,
)


def test_totales_suman_coberturas_y_cuentan_practicas() -> None:
    totales = calcular_totales(
        [Decimal("6000.00"), Decimal("2500.50"), Decimal("0.00")]
    )
    assert isinstance(totales, TotalesLiquidacion)
    assert totales.total_cobertura == Decimal("8500.50")
    assert totales.cantidad_practicas == 3


def test_totales_sin_practicas_son_cero() -> None:
    totales = calcular_totales([])
    assert totales.total_cobertura == Decimal("0.00")
    assert totales.cantidad_practicas == 0


def test_totales_cuantizan_centavos() -> None:
    totales = calcular_totales([Decimal("0.005")])
    assert totales.total_cobertura == Decimal("0.01")


def test_borrador_pasa_a_cerrada_y_cerrada_es_terminal() -> None:
    assert puede_transicionar("borrador", "cerrada") is True
    assert puede_transicionar("borrador", "borrador") is True
    assert puede_transicionar("cerrada", "borrador") is False
    assert puede_transicionar("otra", "cerrada") is False


def test_cierre_es_idempotente() -> None:
    assert cerrar_estado("borrador") == "cerrada"
    assert cerrar_estado("cerrada") == "cerrada"
    with pytest.raises(ValueError, match="liquidación"):
        cerrar_estado("anulada")


def test_periodo_de_un_solo_dia_es_valido() -> None:
    dia = date(2026, 11, 4)
    assert validar_periodo(dia, dia) == (dia, dia)


def test_periodo_invertido_falla() -> None:
    with pytest.raises(ValueError, match="desde"):
        validar_periodo(date(2026, 11, 5), date(2026, 11, 4))


def test_periodos_contiguos_no_se_solapan() -> None:
    assert not se_solapan(
        date(2026, 1, 1),
        date(2026, 1, 31),
        date(2026, 2, 1),
        date(2026, 2, 28),
    )
    assert not se_solapan(
        date(2026, 2, 1),
        date(2026, 2, 28),
        date(2026, 1, 1),
        date(2026, 1, 31),
    )


def test_periodos_que_se_cruzan_o_comparten_un_dia_se_solapan() -> None:
    """The period is inclusive on both ends (daterange '[]', D9)."""
    assert se_solapan(
        date(2026, 1, 1),
        date(2026, 1, 31),
        date(2026, 1, 15),
        date(2026, 2, 5),
    )
    assert se_solapan(
        date(2026, 1, 1),
        date(2026, 1, 31),
        date(2026, 1, 31),
        date(2026, 1, 31),
    )
    assert se_solapan(
        date(2026, 1, 1),
        date(2026, 1, 31),
        date(2025, 12, 1),
        date(2026, 1, 1),
    )
