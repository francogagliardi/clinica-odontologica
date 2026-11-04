"""Worker entrypoint and webhook signature unit tests (C-09)."""

import hashlib
import hmac

import pytest

from app.application.webhooks import firma_valida
from app.workers.__main__ import main


def test_main_rechaza_modo_desconocido() -> None:
    with pytest.raises(SystemExit, match="recordatorios"):
        main(["otro"])


def test_firma_hmac_valida() -> None:
    body = b'{"mensajes":[]}'
    firma = hmac.new(b"secreto", body, hashlib.sha256).hexdigest()
    assert firma_valida(body, f"sha256={firma}", "secreto") is True
    assert firma_valida(body, "sha256=deadbeef", "secreto") is False
    assert firma_valida(body, None, "secreto") is False
