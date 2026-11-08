"""C-15 cash report (tasks 5.1/5.2, design D8/D9/D13).

The deterministic dataset has 2 approved cash payments (10000 + 5000), one
approved Mercado Pago payment (8000), one of each non-approved state, a 3500
expense and a 12000 debt. A closed register keeps its signed snapshot and an
open one keeps its closing fields null.
"""

from tests.integration.helpers import run
from tests.integration.reportes_helpers import setup_reportes
from tests.integration.recursos_helpers import bearer


def _get(api_client, data, actor: str = "administrador", **params):
    return api_client.get(
        "/reportes/caja",
        params={
            "desde": data["caja_desde"].isoformat(),
            "hasta": data["caja_hasta"].isoformat(),
            **params,
        },
        headers=bearer(data["actores"][actor]),
    )


def test_totales_por_medio_estado_y_movimientos(
    api_client, session_factory
) -> None:
    data = run(setup_reportes(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    assert cuerpo["total_aprobado"] == "23000.00"
    assert cuerpo["total_efectivo"] == "15000.00"
    assert cuerpo["total_mercadopago"] == "8000.00"
    assert cuerpo["por_estado"] == {
        "pendiente": 1,
        "aprobado": 3,
        "rechazado": 1,
        "reembolsado": 1,
        "perdido": 1,
    }
    assert cuerpo["total_gastos"] == "3500.00"
    assert cuerpo["total_deudas"] == "12000.00"
    assert cuerpo["total_detalle"] == 7

    movimientos = {
        (fila["tipo"], fila["medio"]): (
            fila["cantidad"],
            fila["total"],
        )
        for fila in cuerpo["movimientos"]
    }
    assert movimientos == {
        ("ingreso", "efectivo"): (1, "15000.00"),
        ("gasto", "efectivo"): (1, "3500.00"),
        ("deuda", "efectivo"): (1, "12000.00"),
        ("ingreso", "mercadopago"): (1, "8000.00"),
    }


def test_arqueo_cerrado_y_caja_abierta_sin_recalcular(
    api_client, session_factory
) -> None:
    data = run(setup_reportes(session_factory))
    respuesta = _get(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()

    cajas = {fila["fecha"]: fila for fila in cuerpo["cajas"]}
    cerrada = cajas["2026-11-04"]
    assert cerrada["caja_id"] == str(data["caja_cerrada"])
    assert cerrada["estado"] == "cerrada"
    assert cerrada["monto_sistema_efectivo"] == "10000.00"
    assert cerrada["monto_contado"] == "10000.00"
    assert cerrada["diferencia"] == "0.00"

    abierta = cajas["2026-11-05"]
    assert abierta["caja_id"] == str(data["caja_abierta"])
    assert abierta["estado"] == "abierta"
    assert abierta["monto_sistema_efectivo"] is None
    assert abierta["monto_contado"] is None
    assert abierta["diferencia"] is None


def test_filtro_por_medio_y_estado(api_client, session_factory) -> None:
    data = run(setup_reportes(session_factory))

    efectivo = _get(api_client, data, medio="efectivo")
    assert efectivo.status_code == 200, efectivo.text
    cuerpo_efectivo = efectivo.json()
    assert cuerpo_efectivo["total_aprobado"] == "15000.00"
    assert cuerpo_efectivo["total_efectivo"] == "15000.00"
    assert cuerpo_efectivo["total_mercadopago"] == "0.00"
    assert cuerpo_efectivo["por_estado"] == {
        "pendiente": 0,
        "aprobado": 2,
        "rechazado": 0,
        "reembolsado": 1,
        "perdido": 0,
    }
    assert cuerpo_efectivo["total_detalle"] == 3

    aprobados = _get(api_client, data, estado="aprobado")
    assert aprobados.status_code == 200, aprobados.text
    cuerpo_aprobados = aprobados.json()
    assert cuerpo_aprobados["total_aprobado"] == "23000.00"
    assert cuerpo_aprobados["por_estado"] == {
        "pendiente": 0,
        "aprobado": 3,
        "rechazado": 0,
        "reembolsado": 0,
        "perdido": 0,
    }
    assert cuerpo_aprobados["total_detalle"] == 3


def test_medio_invalido_y_parametro_extra_devuelven_422(
    api_client, session_factory
) -> None:
    data = run(setup_reportes(session_factory))

    invalido = _get(api_client, data, medio="tarjeta")
    assert invalido.status_code == 422, invalido.text

    extra = _get(api_client, data, profesional_id=str(data["profesional"].id))
    assert extra.status_code == 422, extra.text


def test_rango_sin_cajas_ni_cobros_devuelve_ceros(
    api_client, session_factory
) -> None:
    data = run(setup_reportes(session_factory))
    respuesta = _get(
        api_client,
        data,
        desde="2027-01-01",
        hasta="2027-01-02",
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["total_aprobado"] == "0.00"
    assert cuerpo["total_efectivo"] == "0.00"
    assert cuerpo["total_mercadopago"] == "0.00"
    assert cuerpo["total_gastos"] == "0.00"
    assert cuerpo["total_deudas"] == "0.00"
    assert cuerpo["movimientos"] == []
    assert cuerpo["cajas"] == []
    assert cuerpo["detalle"] == []
    assert cuerpo["total_detalle"] == 0
    assert set(cuerpo["por_estado"].values()) == {0}
