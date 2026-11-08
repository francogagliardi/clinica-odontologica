"""C-14 pure fiscal domain: QR, state machine, backoff and local dates (D7).

No database, no network: these tests pin the format a verifier would decode and
the transitions the worker is allowed to take (D3/D5/D7).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.fiscal import (
    calcular_proximo_intento,
    construir_qr_fiscal,
    construir_qr_interno,
    decodificar_qr,
    fecha_emision_local,
    puede_transicionar,
    tipo_comprobante,
)

UTC = timezone.utc
CAE = "12345678901234"


def _qr_fiscal(tipo: str = "B") -> str:
    return construir_qr_fiscal(
        cuit="20000000001",
        punto_venta=3,
        tipo=tipo,
        numero_fiscal=42,
        importe=Decimal("10000.00"),
        cae=CAE,
        fecha=date(2026, 11, 4),
        documento_receptor="42112001",
    )


def test_qr_fiscal_decodifica_cae_punto_venta_numero_e_importe() -> None:
    """Expected: an AFIP verifier can read every field from the URL."""
    url = _qr_fiscal()
    assert url.startswith("https://www.afip.gob.ar/fe/qr/?p=")

    datos = decodificar_qr(url)
    assert datos["ver"] == 1
    assert datos["fecha"] == "2026-11-04"
    assert datos["cuit"] == 20000000001
    assert datos["ptoVta"] == 3
    assert datos["tipoCmp"] == 6
    assert datos["nroCmp"] == 42
    assert Decimal(str(datos["importe"])) == Decimal("10000.00")
    assert datos["moneda"] == "PES"
    assert datos["ctz"] == 1
    assert datos["tipoDocRec"] == 96
    assert datos["nroDocRec"] == 42112001
    assert datos["tipoCodAut"] == "E"
    assert datos["codAut"] == CAE


def test_qr_fiscal_de_factura_c_usa_codigo_11() -> None:
    assert decodificar_qr(_qr_fiscal("C"))["tipoCmp"] == 11


def test_qr_interno_no_expone_cae_ni_dominio_afip() -> None:
    """Expected: the fallback receipt is verifiable but never looks fiscal."""
    comprobante_id = uuid4()
    url = construir_qr_interno(
        comprobante_id=comprobante_id,
        numero_interno=7,
        importe=Decimal("10000.00"),
        fecha=date(2026, 11, 4),
    )
    assert url.startswith("https://app.local/comprobantes/verificar?p=")
    assert "afip.gob.ar" not in url

    datos = decodificar_qr(url)
    assert datos["tipo"] == "INTERNO"
    assert datos["comprobante_id"] == str(comprobante_id)
    assert datos["numero_interno"] == 7
    assert Decimal(str(datos["importe"])) == Decimal("10000.00")
    assert datos["fecha"] == "2026-11-04"
    assert "codAut" not in datos
    assert "cae" not in " ".join(datos).lower()


def test_decodificar_qr_rechaza_url_sin_payload() -> None:
    with pytest.raises(ValueError, match="QR"):
        decodificar_qr("https://app.local/comprobantes/verificar")


def test_pendiente_transiciona_a_emitido_o_fallido() -> None:
    assert puede_transicionar("pendiente", "emitido") is True
    assert puede_transicionar("pendiente", "fallido") is True


def test_emitido_es_terminal() -> None:
    """Expected: an emitted receipt never goes back or is re-emitted."""
    assert puede_transicionar("emitido", "pendiente") is False
    assert puede_transicionar("emitido", "fallido") is False
    assert puede_transicionar("emitido", "emitido") is True


def test_fallido_vuelve_a_pendiente_solo_por_reintento_manual() -> None:
    assert puede_transicionar("fallido", "pendiente") is True
    assert puede_transicionar("fallido", "fallido") is True
    # Only `pendiente` is claimed for emission: no direct `fallido→emitido`.
    assert puede_transicionar("fallido", "emitido") is False


def test_estado_desconocido_no_transiciona() -> None:
    assert puede_transicionar("borrador", "emitido") is False
    assert puede_transicionar("pendiente", "desconocido") is False


def test_backoff_exponencial_crece_y_tiene_tope() -> None:
    ahora = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    primero = calcular_proximo_intento(1, ahora=ahora)
    segundo = calcular_proximo_intento(2, ahora=ahora)
    tercero = calcular_proximo_intento(3, ahora=ahora)

    assert primero == ahora + timedelta(seconds=60)
    assert segundo == ahora + timedelta(seconds=120)
    assert tercero == ahora + timedelta(seconds=240)
    assert tercero - ahora > segundo - ahora > primero - ahora

    # The delay is capped so a lost job does not wait for hours.
    tope = calcular_proximo_intento(50, ahora=ahora)
    assert tope == ahora + timedelta(seconds=3600)


def test_backoff_exige_intentos_positivos() -> None:
    with pytest.raises(ValueError, match="intentos"):
        calcular_proximo_intento(0)


def test_fecha_emision_usa_utc_menos_tres() -> None:
    assert fecha_emision_local(
        datetime(2026, 11, 5, 2, 30, tzinfo=UTC)
    ) == date(2026, 11, 4)
    assert fecha_emision_local(
        datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
    ) == date(2026, 11, 5)
    # A naive timestamp is the UTC instant PostgreSQL hands back.
    assert fecha_emision_local(
        datetime(2026, 11, 5, 15, 0)
    ) == date(2026, 11, 5)


def test_tipo_de_comprobante_segun_condicion_del_emisor() -> None:
    assert tipo_comprobante("responsable_inscripto") == "B"
    assert tipo_comprobante("monotributista") == "C"
    with pytest.raises(ValueError, match="condición"):
        tipo_comprobante("exento")
