"""Unit tests for patient identity normalization (C-05, design D3)."""

import pytest

from app.domain.pacientes import normalizar_dni, normalizar_telefono


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30111222", "30111222"),
        ("30.111.222", "30111222"),
        (" 30 111 222 ", "30111222"),
        ("3011122-2", "30111222"),
        ("1234567", "1234567"),
        ("00111222", "00111222"),
    ],
)
def test_normalizar_dni_acepta_7_u_8_digitos(raw: str, expected: str) -> None:
    assert normalizar_dni(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "123456", "123456789", "30.111.22A", "DNI", "30.111.222.3"],
)
def test_normalizar_dni_rechaza_formatos_invalidos(raw: str) -> None:
    with pytest.raises(ValueError, match="DNI"):
        normalizar_dni(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1155551234", "+5491155551234"),
        ("11 5555-1234", "+5491155551234"),
        ("(11) 5555 1234", "+5491155551234"),
        ("+54 9 11 5555-1234", "+5491155551234"),
        ("+5491155551234", "+5491155551234"),
        ("5491155551234", "+5491155551234"),
    ],
)
def test_normalizar_telefono_devuelve_formato_internacional(
    raw: str, expected: str
) -> None:
    assert normalizar_telefono(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "123",
        "115555123",  # 9 dígitos
        "11555512345",  # 11 dígitos sin código país
        "541155551234",  # fijo sin 9
        "549115555123",  # 549 con 9 dígitos
        "abc",
    ],
)
def test_normalizar_telefono_rechaza_formatos_invalidos(raw: str) -> None:
    with pytest.raises(ValueError, match="[Tt]eléfono"):
        normalizar_telefono(raw)
