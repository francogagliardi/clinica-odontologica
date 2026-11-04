"""Pure budget domain: state machine and money arithmetic (C-12, D4/D6).

No database here: the same arithmetic is exercised by the HTTP integration
tests, but this file is the contract for the `Decimal` + ROUND_HALF_UP rules
and for the transition matrix that the API reuses.
"""

from decimal import Decimal

import pytest

from app.domain.presupuestos import (
    ESTADOS,
    ESTADOS_COBERTURA,
    calcular_item,
    calcular_presupuesto,
    puede_transicionar,
)
from app.domain.presupuestos import _TRANSICIONES


def test_catalogo_de_estados() -> None:
    """The two vocabularies are explicit and complete (design D3/D6)."""
    assert ESTADOS == {
        "borrador",
        "aceptado",
        "rechazado",
        "en_curso",
        "finalizado",
    }
    assert ESTADOS_COBERTURA == {"calculada", "pendiente_verificacion"}
    assert set(_TRANSICIONES) == ESTADOS


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        ("borrador", "aceptado"),
        ("borrador", "rechazado"),
        ("aceptado", "en_curso"),
        ("en_curso", "finalizado"),
    ],
)
def test_transiciones_validas(actual: str, nuevo: str) -> None:
    assert puede_transicionar(actual, nuevo) is True


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        ("borrador", "en_curso"),
        ("borrador", "finalizado"),
        ("aceptado", "rechazado"),
        ("aceptado", "borrador"),
        ("en_curso", "aceptado"),
        ("rechazado", "aceptado"),
        ("finalizado", "en_curso"),
        ("rechazado", "borrador"),
        ("finalizado", "borrador"),
        ("inexistente", "aceptado"),
    ],
)
def test_transiciones_invalidas(actual: str, nuevo: str) -> None:
    assert puede_transicionar(actual, nuevo) is False


@pytest.mark.parametrize("estado", sorted(ESTADOS))
def test_repetir_el_estado_actual_es_idempotente(estado: str) -> None:
    assert puede_transicionar(estado, estado) is True


def test_cobertura_parcial_de_60_sobre_dos_items() -> None:
    """2 × 10.000,00 al 60 %: cobertura 12.000,00 y copago 8.000,00."""
    cobertura, copago = calcular_item(
        Decimal("10000.00"), 2, Decimal("60")
    )
    assert cobertura == Decimal("12000.00")
    assert copago == Decimal("8000.00")
    assert cobertura + copago == Decimal("20000.00")


def test_cobertura_cero_y_cien() -> None:
    cero = calcular_item(Decimal("25000.00"), 1, Decimal("0"))
    assert cero == (Decimal("0.00"), Decimal("25000.00"))

    total = calcular_item(Decimal("25000.00"), 1, Decimal("100"))
    assert total == (Decimal("25000.00"), Decimal("0.00"))


def test_sin_convenio_la_cobertura_es_cero() -> None:
    """No agreement is a known 0 %, not an unverifiable coverage."""
    cobertura, copago = calcular_item(
        Decimal("18000.00"), 1, Decimal("0")
    )
    assert cobertura == Decimal("0.00")
    assert copago == Decimal("18000.00")


def test_redondeo_half_up_sin_centavos_perdidos() -> None:
    """33,33 × 60 % = 19,998 exacto → 20,00 y copago 13,33."""
    cobertura, copago = calcular_item(
        Decimal("33.33"), 1, Decimal("60")
    )
    assert cobertura == Decimal("20.00")
    assert copago == Decimal("13.33")
    assert cobertura + copago == Decimal("33.33")


def test_totales_son_la_suma_de_los_items() -> None:
    """Amounts are quantized per line, so the header never drifts a cent."""
    precios = [
        (Decimal("33.33"), 1, Decimal("60")),
        (Decimal("10000.00"), 2, Decimal("60")),
        (Decimal("25000.00"), 1, Decimal("0")),
        (Decimal("7.77"), 3, Decimal("100")),
    ]
    items = [
        calcular_item(precio, cantidad, porcentaje)
        for precio, cantidad, porcentaje in precios
    ]

    for (precio, cantidad, _porcentaje), (cobertura, copago) in zip(
        precios, items
    ):
        total_item = (precio * cantidad).quantize(Decimal("0.01"))
        assert cobertura + copago == total_item

    totales = calcular_presupuesto(items)
    assert totales.subtotal == sum(
        precio * cantidad for precio, cantidad, _ in precios
    ).quantize(Decimal("0.01"))
    assert totales.cobertura_calculada == sum(
        cobertura for cobertura, _ in items
    )
    assert totales.copago == sum(copago for _, copago in items)
    assert totales.subtotal == (
        totales.cobertura_calculada + totales.copago
    )


def test_presupuesto_vacio_suma_cero() -> None:
    totales = calcular_presupuesto([])
    assert totales == (
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )


@pytest.mark.parametrize("cantidad", [0, -1])
def test_cantidad_no_positiva_es_invalida(cantidad: int) -> None:
    with pytest.raises(ValueError):
        calcular_item(Decimal("100.00"), cantidad, Decimal("60"))


def test_porcentaje_fuera_de_rango_es_invalido() -> None:
    for porcentaje in (Decimal("-1"), Decimal("101")):
        with pytest.raises(ValueError):
            calcular_item(Decimal("100.00"), 1, porcentaje)


def test_precio_negativo_es_invalido() -> None:
    with pytest.raises(ValueError):
        calcular_item(Decimal("-0.01"), 1, Decimal("60"))
