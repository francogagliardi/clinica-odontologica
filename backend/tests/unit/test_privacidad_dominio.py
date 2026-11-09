"""Unit tests for the versioned privacy policy (C-16, task 7.1).

No database, no network: the current version, the immutable canonical text,
the stable SHA-256, unknown versions and the absence of legal-compliance
claims.
"""

import hashlib
import re
from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.domain.privacidad import (
    POLITICAS,
    VERSION_ACTUAL,
    VIGENTE_DESDE,
    hash_politica,
    politica_actual,
    politica_por_version,
)


def test_version_vigente_y_fecha() -> None:
    assert re.fullmatch(r"v\d+-\d{4}-\d{2}", VERSION_ACTUAL)
    assert isinstance(VIGENTE_DESDE, date)
    actual = politica_actual()
    assert actual.version == VERSION_ACTUAL
    assert actual.vigente_desde == VIGENTE_DESDE
    assert VERSION_ACTUAL in POLITICAS


def test_texto_canonico_indica_version_y_vigencia() -> None:
    actual = politica_actual()
    assert VERSION_ACTUAL in actual.texto
    assert VIGENTE_DESDE.isoformat() in actual.texto
    assert "privacidad" in actual.texto.lower()
    assert "asesoramiento humano" in actual.texto.lower()
    assert len(actual.texto) > 200


def test_hash_sha256_estable_y_coincide_con_el_texto() -> None:
    actual = politica_actual()
    esperado = hashlib.sha256(actual.texto.encode("utf-8")).hexdigest()
    assert hash_politica(actual.texto) == esperado
    assert len(esperado) == 64
    assert all(caracter in "0123456789abcdef" for caracter in esperado)
    # Two reads of the same version produce exactly the same hash.
    assert hash_politica(politica_actual().texto) == esperado
    assert hash_politica(politica_por_version(VERSION_ACTUAL).texto) == esperado


def test_version_desconocida_no_existe() -> None:
    assert politica_por_version("v9999-01-01") is None
    assert politica_por_version("") is None
    assert politica_por_version("v1") is None


def test_politica_es_inmutable_por_version() -> None:
    actual = politica_actual()
    with pytest.raises(FrozenInstanceError):
        actual.version = "v2-2027-01"  # type: ignore[misc]


def test_texto_no_afirma_cumplimiento_normativo() -> None:
    texto = politica_actual().texto.lower()
    for afirmacion in (
        "cumplimos",
        "cumplimiento garantizado",
        "certificado de cumplimiento",
        "garantizamos el cumplimiento",
        "cumple con la ley",
    ):
        assert afirmacion not in texto, afirmacion
    # It names the laws only to say that human advice is required.
    assert "ley 25.326" in texto
    assert "ley 26.529" in texto
    assert "no constituye" in texto
