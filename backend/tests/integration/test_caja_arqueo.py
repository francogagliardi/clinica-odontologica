"""C-13 cash register: open, movements, arqueo and zero-difference close."""

from datetime import date, datetime, timezone

import app.application.caja as caja_app
from sqlalchemy import func, select

from app.models.caja import CajaDiaria
from tests.integration.cobros_helpers import (
    cobro_payload,
    setup_cobros,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer

_UA = "pytest-ua-c13-caja"


def _setup(session_factory, *, con_caja: bool = False) -> dict[str, object]:
    return run(setup_cobros(session_factory, con_caja=con_caja))


def _headers(data, actor: str = "recepcionista") -> dict[str, str]:
    return {**bearer(data["actores"][actor]), "User-Agent": _UA}


def _abrir(api_client, data, *, monto="10000.00", fecha=None, actor="recepcionista"):
    body: dict[str, object] = {"monto_apertura": monto}
    if fecha is not None:
        body["fecha"] = fecha.isoformat()
    return api_client.post(
        "/caja/abrir", json=body, headers=_headers(data, actor)
    )


def _movimiento(
    api_client,
    data,
    *,
    tipo="gasto",
    monto="3500.00",
    concepto="Insumos",
    medio="efectivo",
    cobro_id=None,
    actor="recepcionista",
):
    body = {
        "tipo": tipo,
        "concepto": concepto,
        "monto": monto,
        "medio": medio,
    }
    if cobro_id is not None:
        body["cobro_id"] = str(cobro_id)
    return api_client.post(
        "/caja/movimientos", json=body, headers=_headers(data, actor)
    )


def _arqueo(api_client, data, *, fecha=None):
    params = {"fecha": fecha.isoformat()} if fecha else {}
    return api_client.get(
        "/caja/arqueo", params=params, headers=_headers(data)
    )


def _cerrar(api_client, data, *, monto, observaciones=None, actor="recepcionista"):
    body: dict[str, object] = {"monto_contado": monto}
    if observaciones is not None:
        body["observaciones"] = observaciones
    return api_client.post(
        "/caja/cerrar", json=body, headers=_headers(data, actor)
    )


def _cobro_efectivo(api_client, data, monto="15000.00"):
    respuesta = api_client.post(
        "/cobros",
        json=cobro_payload(data, tipo="otro", medio="efectivo", monto=monto),
        headers=_headers(data),
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _contar_cajas(session_factory) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count()).select_from(CajaDiaria)
            )

    return run(contar())


def test_apertura_201_y_segunda_apertura_409(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    primera = _abrir(api_client, data, monto="10000.00")
    assert primera.status_code == 201, primera.text
    body = primera.json()
    assert body["estado"] == "abierta"
    assert body["monto_apertura"] == "10000.00"
    assert body["fecha"] == data["hoy"].isoformat()
    assert body["monto_sistema_efectivo"] is None

    segunda = _abrir(api_client, data, monto="500.00")
    assert segunda.status_code == 409, segunda.text
    assert _contar_cajas(session_factory) == 1

    ficha = api_client.get("/caja", headers=_headers(data))
    assert ficha.status_code == 200, ficha.text
    assert ficha.json()["id"] == body["id"]
    assert ficha.json()["monto_apertura"] == "10000.00"


def test_apertura_negativa_422_y_sin_caja(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    for monto in ("-1", "-0.01"):
        respuesta = _abrir(api_client, data, monto=monto)
        assert respuesta.status_code == 422, respuesta.text
    extra = api_client.post(
        "/caja/abrir",
        json={"monto_apertura": "0.00", "estado": "abierta"},
        headers=_headers(data),
    )
    assert extra.status_code == 422, extra.text
    assert _contar_cajas(session_factory) == 0


def test_movimiento_2300_local_cae_en_el_dia_correcto(
    api_client, session_factory, monkeypatch
) -> None:
    """Edge: 02:30Z is 23:30 of the previous Argentine day (design D6)."""
    data = _setup(session_factory)
    frozen = datetime(2026, 11, 5, 2, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(caja_app, "ahora_utc", lambda: frozen)

    apertura = _abrir(
        api_client, data, monto="0.00", fecha=date(2026, 11, 4)
    )
    assert apertura.status_code == 201, apertura.text
    movimiento = _movimiento(
        api_client, data, tipo="gasto", monto="1000.00"
    )
    assert movimiento.status_code == 201, movimiento.text

    dia_4 = api_client.get(
        "/caja/movimientos",
        params={"fecha": "2026-11-04"},
        headers=_headers(data),
    )
    dia_5 = api_client.get(
        "/caja/movimientos",
        params={"fecha": "2026-11-05"},
        headers=_headers(data),
    )
    assert [m["monto"] for m in dia_4.json()] == ["1000.00"]
    assert dia_5.json() == []


def test_arqueo_separa_efectivo_mp_y_deudas(
    api_client, session_factory
) -> None:
    """Expected: only cash moves the drawer; MP and debts are separate."""
    data = _setup(session_factory)
    assert _abrir(api_client, data, monto="10000.00").status_code == 201
    assert _cobro_efectivo(api_client, data)["monto"] == "15000.00"
    assert (
        _movimiento(api_client, data, tipo="gasto", monto="3500.00")
        .status_code
        == 201
    )
    assert (
        _movimiento(
            api_client,
            data,
            tipo="deuda",
            monto="12000.00",
            concepto="Proveedor",
        ).status_code
        == 201
    )
    assert (
        _movimiento(
            api_client,
            data,
            tipo="ingreso",
            monto="8000.00",
            concepto="Cobro MP",
            medio="mercadopago",
        ).status_code
        == 201
    )

    respuesta = _arqueo(api_client, data)
    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["monto_apertura"] == "10000.00"
    assert body["ingresos_efectivo"] == "15000.00"
    assert body["gastos_efectivo"] == "3500.00"
    assert body["monto_sistema_efectivo"] == "21500.00"
    assert body["ingresos_mercadopago"] == "8000.00"
    assert body["deudas"] == "12000.00"
    assert len(body["movimientos"]) == 4


def test_arqueo_sin_caja_devuelve_ceros(api_client, session_factory) -> None:
    """Expected: an unopened date answers 200 with zeros, never creates a row."""
    data = _setup(session_factory)
    respuesta = _arqueo(api_client, data, fecha=date(2026, 11, 4))
    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["caja_id"] is None
    assert body["estado"] is None
    assert body["monto_apertura"] == "0.00"
    assert body["ingresos_efectivo"] == "0.00"
    assert body["gastos_efectivo"] == "0.00"
    assert body["monto_sistema_efectivo"] == "0.00"
    assert body["ingresos_mercadopago"] == "0.00"
    assert body["deudas"] == "0.00"
    assert body["movimientos"] == []
    assert _contar_cajas(session_factory) == 0


def test_ingreso_de_cobro_duplicado_409(api_client, session_factory) -> None:
    """Business error: one payment can produce only one register movement."""
    data = _setup(session_factory)
    assert _abrir(api_client, data, monto="10000.00").status_code == 201
    cobro = _cobro_efectivo(api_client, data)
    duplicado = _movimiento(
        api_client,
        data,
        tipo="ingreso",
        monto="15000.00",
        concepto="Cobro repetido",
        cobro_id=cobro["id"],
    )
    assert duplicado.status_code == 409, duplicado.text


def test_movimiento_sin_caja_o_sobre_cerrada_409(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    sin_caja = _movimiento(api_client, data)
    assert sin_caja.status_code == 409, sin_caja.text

    assert _abrir(api_client, data, monto="0.00").status_code == 201
    assert _cerrar(api_client, data, monto="0.00").status_code == 200
    cerrada = _movimiento(api_client, data)
    assert cerrada.status_code == 409, cerrada.text


def test_cierre_cuadrado_y_repetido(api_client, session_factory) -> None:
    """Expected: 200 with snapshot and difference 0; repeating is 409."""
    data = _setup(session_factory)
    assert _abrir(api_client, data, monto="10000.00").status_code == 201
    assert _cobro_efectivo(api_client, data)["monto"] == "15000.00"
    assert (
        _movimiento(api_client, data, tipo="gasto", monto="3500.00")
        .status_code
        == 201
    )

    cierre = _cerrar(
        api_client,
        data,
        monto="21500.00",
        observaciones="Cierre cuadrado",
    )
    assert cierre.status_code == 200, cierre.text
    body = cierre.json()
    assert body["estado"] == "cerrada"
    assert body["monto_sistema_efectivo"] == "21500.00"
    assert body["monto_contado"] == "21500.00"
    assert body["diferencia"] == "0.00"
    assert body["cerrada_por"] == str(
        data["actores"]["recepcionista"].id
    )
    assert body["cerrada_at"] is not None

    arqueo = _arqueo(api_client, data)
    assert arqueo.status_code == 200
    assert arqueo.json()["estado"] == "cerrada"
    assert arqueo.json()["monto_sistema_efectivo"] == "21500.00"

    repetido = _cerrar(api_client, data, monto="21500.00")
    assert repetido.status_code == 409, repetido.text


def test_cierre_con_faltante_o_sobrante_409(
    api_client, session_factory
) -> None:
    """Business error: a difference keeps the register open."""
    data = _setup(session_factory)
    assert _abrir(api_client, data, monto="10000.00").status_code == 201
    assert _cobro_efectivo(api_client, data)["monto"] == "15000.00"
    assert (
        _movimiento(api_client, data, tipo="gasto", monto="3500.00")
        .status_code
        == 201
    )

    for contado in ("21000.00", "22000.00"):
        respuesta = _cerrar(api_client, data, monto=contado)
        assert respuesta.status_code == 409, respuesta.text
        ficha = api_client.get("/caja", headers=_headers(data))
        assert ficha.json()["estado"] == "abierta"


def test_cierre_monto_invalido_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    assert _abrir(api_client, data, monto="0.00").status_code == 201
    invalido = _cerrar(api_client, data, monto="-100.00")
    assert invalido.status_code == 422, invalido.text


def test_cierre_sin_caja_404(api_client, session_factory) -> None:
    data = _setup(session_factory)
    sin_caja = _cerrar(api_client, data, monto="0.00")
    assert sin_caja.status_code == 404, sin_caja.text


def test_movimiento_monto_cero_concepto_o_extra_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    assert _abrir(api_client, data, monto="0.00").status_code == 201
    assert (
        _movimiento(api_client, data, monto="0").status_code == 422
    )
    assert (
        _movimiento(api_client, data, concepto="   ").status_code == 422
    )
    extra = api_client.post(
        "/caja/movimientos",
        json={
            "tipo": "gasto",
            "concepto": "Insumos",
            "monto": "10.00",
            "estado": "aprobado",
        },
        headers=_headers(data),
    )
    assert extra.status_code == 422, extra.text


def test_fecha_invalida_o_query_no_declarada_422(
    api_client, session_factory
) -> None:
    """Business error: strict boundaries reject bad dates and extra filters."""
    data = _setup(session_factory)
    fecha_invalida = api_client.get(
        "/caja/arqueo",
        params={"fecha": "no-es-fecha"},
        headers=_headers(data),
    )
    assert fecha_invalida.status_code == 422, fecha_invalida.text

    query_extra = api_client.get(
        "/caja/arqueo",
        params={"desde": "2026-11-01"},
        headers=_headers(data),
    )
    assert query_extra.status_code == 422, query_extra.text

    apertura_invalida = api_client.post(
        "/caja/abrir",
        json={"monto_apertura": "0.00", "fecha": "no-es-fecha"},
        headers=_headers(data),
    )
    assert apertura_invalida.status_code == 422, apertura_invalida.text
