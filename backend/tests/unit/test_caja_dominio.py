"""C-13 pure cash domain: local date, arqueo totals and payment rules (D6/D9)."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.domain.caja import (
    MovimientoResumen,
    TotalesArqueo,
    calcular_arqueo,
    diferencia_cierre,
    fecha_local,
    puede_transicionar,
    validar_medio,
    validar_monto,
    validar_referencias,
    validar_tipo,
)

UTC = timezone.utc


def test_fecha_local_usa_utc_menos_tres() -> None:
    """The day is Argentine, so 02:30Z belongs to the previous local date."""
    assert fecha_local(datetime(2026, 11, 5, 2, 30, tzinfo=UTC)) == date(
        2026, 11, 4
    )
    # Exactly 03:00Z is local midnight of the next day (boundary).
    assert fecha_local(datetime(2026, 11, 5, 3, 0, tzinfo=UTC)) == date(
        2026, 11, 5
    )
    # Inside the same local day.
    assert fecha_local(datetime(2026, 11, 5, 15, 0, tzinfo=UTC)) == date(
        2026, 11, 5
    )


def test_arqueo_separa_efectivo_mercadopago_y_deudas() -> None:
    """Only cash changes the expected drawer; MP and debts are reported apart."""
    totales = calcular_arqueo(
        Decimal("10000.00"),
        [
            MovimientoResumen("ingreso", "efectivo", Decimal("15000.00")),
            MovimientoResumen("gasto", "efectivo", Decimal("3500.00")),
            MovimientoResumen("ingreso", "mercadopago", Decimal("8000.00")),
            MovimientoResumen("deuda", "efectivo", Decimal("12000.00")),
        ],
    )
    assert isinstance(totales, TotalesArqueo)
    assert totales.monto_apertura == Decimal("10000.00")
    assert totales.ingresos_efectivo == Decimal("15000.00")
    assert totales.gastos_efectivo == Decimal("3500.00")
    assert totales.monto_sistema_efectivo == Decimal("21500.00")
    assert totales.ingresos_mercadopago == Decimal("8000.00")
    assert totales.deudas == Decimal("12000.00")


def test_arqueo_sin_movimientos_es_la_apertura() -> None:
    totales = calcular_arqueo(Decimal("10000.00"), [])
    assert totales.ingresos_efectivo == Decimal("0.00")
    assert totales.gastos_efectivo == Decimal("0.00")
    assert totales.ingresos_mercadopago == Decimal("0.00")
    assert totales.deudas == Decimal("0.00")
    assert totales.monto_sistema_efectivo == Decimal("10000.00")


def test_arqueo_no_confunde_gasto_mp_con_efectivo() -> None:
    """An expense paid by Mercado Pago never reduces the physical drawer."""
    totales = calcular_arqueo(
        Decimal("0.00"),
        [
            MovimientoResumen("ingreso", "mercadopago", Decimal("8000.00")),
            MovimientoResumen("gasto", "mercadopago", Decimal("1000.00")),
        ],
    )
    assert totales.monto_sistema_efectivo == Decimal("0.00")
    assert totales.ingresos_mercadopago == Decimal("8000.00")
    assert totales.gastos_efectivo == Decimal("0.00")


def test_diferencia_de_cierre_es_contado_menos_sistema() -> None:
    assert diferencia_cierre(
        Decimal("21500.00"), Decimal("21500.00")
    ) == Decimal("0.00")
    assert diferencia_cierre(
        Decimal("21000.00"), Decimal("21500.00")
    ) == Decimal("-500.00")
    assert diferencia_cierre(
        Decimal("22000.00"), Decimal("21500.00")
    ) == Decimal("500.00")


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        ("pendiente", "aprobado"),
        ("pendiente", "rechazado"),
        ("pendiente", "perdido"),
        ("aprobado", "reembolsado"),
        ("aprobado", "perdido"),
        # Repeating a state is idempotent.
        ("aprobado", "aprobado"),
        ("perdido", "perdido"),
    ],
)
def test_transiciones_validas_de_cobro(actual: str, nuevo: str) -> None:
    assert puede_transicionar(actual, nuevo) is True


@pytest.mark.parametrize(
    ("actual", "nuevo"),
    [
        ("aprobado", "pendiente"),
        ("rechazado", "aprobado"),
        ("pendiente", "reembolsado"),
        ("reembolsado", "aprobado"),
        ("perdido", "aprobado"),
        ("desconocido", "aprobado"),
    ],
)
def test_transiciones_invalidas_de_cobro(actual: str, nuevo: str) -> None:
    assert puede_transicionar(actual, nuevo) is False


@pytest.mark.parametrize("monto", [Decimal("0"), Decimal("-1.00")])
def test_monto_debe_ser_positivo(monto: Decimal) -> None:
    with pytest.raises(ValueError):
        validar_monto(monto)


def test_monto_positivo_es_valido() -> None:
    assert validar_monto(Decimal("0.01")) == Decimal("0.01")


def test_tipo_y_medio_pertenecen_al_catalogo() -> None:
    for tipo in ("sena", "tratamiento", "otro"):
        assert validar_tipo(tipo) == tipo
    with pytest.raises(ValueError):
        validar_tipo("cuota")

    for medio in ("efectivo", "mercadopago"):
        assert validar_medio(medio) == medio
    with pytest.raises(ValueError):
        validar_medio("transferencia")


def test_sena_exige_turno_y_prohibe_presupuesto() -> None:
    assert validar_referencias("sena", turno_id="turno-1") is None
    with pytest.raises(ValueError):
        validar_referencias("sena", turno_id=None)
    with pytest.raises(ValueError):
        validar_referencias(
            "sena", turno_id="turno-1", presupuesto_id="presupuesto-1"
        )


def test_tratamiento_exige_presupuesto_y_prohibe_turno() -> None:
    assert (
        validar_referencias("tratamiento", presupuesto_id="presupuesto-1")
        is None
    )
    with pytest.raises(ValueError):
        validar_referencias("tratamiento", presupuesto_id=None)
    with pytest.raises(ValueError):
        validar_referencias(
            "tratamiento",
            turno_id="turno-1",
            presupuesto_id="presupuesto-1",
        )


def test_otro_no_admite_referencias() -> None:
    assert validar_referencias("otro") is None
    with pytest.raises(ValueError):
        validar_referencias("otro", turno_id="turno-1")
    with pytest.raises(ValueError):
        validar_referencias("otro", presupuesto_id="presupuesto-1")
