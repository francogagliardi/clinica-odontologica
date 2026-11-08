"""C-13 Mercado Pago webhook signature: HMAC, tampering and clock tolerance."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.mercadopago import FirmaInvalida, validar_firma_webhook

SECRET = "test-only-webhook-secret"
AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _manifest(ts: int, data_id: str, request_id: str) -> str:
    """Official MP manifest, written independently of the implementation."""
    return f"id:{data_id};request-id:{request_id};ts:{ts};"


def _firma(ts: int, *, secret: str = SECRET, data_id: str = "12345",
           request_id: str = "req-001") -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        _manifest(ts, data_id, request_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"ts={ts},v1={digest}"


def test_firma_valida_se_acepta() -> None:
    ts = int(AHORA.timestamp())
    validar_firma_webhook(
        _firma(ts),
        SECRET,
        data_id="12345",
        request_id="req-001",
        now=AHORA,
    )


def test_firma_en_el_limite_de_la_tolerancia_se_acepta() -> None:
    ts = int((AHORA - timedelta(seconds=300)).timestamp())
    validar_firma_webhook(
        _firma(ts),
        SECRET,
        data_id="12345",
        request_id="req-001",
        now=AHORA,
    )


def test_firma_adulterada_se_rechaza() -> None:
    ts = int(AHORA.timestamp())
    header = _firma(ts)
    v1 = header.split("v1=")[1]
    adulterada = header.replace(v1, ("0" * 64) if v1[0] != "0" else "1" * 64)
    with pytest.raises(FirmaInvalida):
        validar_firma_webhook(
            adulterada,
            SECRET,
            data_id="12345",
            request_id="req-001",
            now=AHORA,
        )


def test_secreto_distinto_se_rechaza() -> None:
    ts = int(AHORA.timestamp())
    with pytest.raises(FirmaInvalida):
        validar_firma_webhook(
            _firma(ts, secret="otro-secreto"),
            SECRET,
            data_id="12345",
            request_id="req-001",
            now=AHORA,
        )


@pytest.mark.parametrize("header", [None, "", "v1=" + "a" * 64, "ts=123"])
def test_firma_ausente_o_mal_formada_se_rechaza(header) -> None:
    with pytest.raises(FirmaInvalida):
        validar_firma_webhook(
            header,
            SECRET,
            data_id="12345",
            request_id="req-001",
            now=AHORA,
        )


def test_timestamp_fuera_de_tolerancia_se_rechaza_aunque_el_hmac_sea_valido() -> (
    None
):
    ts = int((AHORA - timedelta(seconds=301)).timestamp())
    with pytest.raises(FirmaInvalida):
        validar_firma_webhook(
            _firma(ts),
            SECRET,
            data_id="12345",
            request_id="req-001",
            now=AHORA,
        )


def test_timestamp_futuro_fuera_de_tolerancia_se_rechaza() -> None:
    ts = int((AHORA + timedelta(seconds=301)).timestamp())
    with pytest.raises(FirmaInvalida):
        validar_firma_webhook(
            _firma(ts),
            SECRET,
            data_id="12345",
            request_id="req-001",
            now=AHORA,
        )
