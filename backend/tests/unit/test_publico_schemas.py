"""Unit tests for public booking schemas (C-07)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.publico import ReservaCreate

TZ = timezone(timedelta(hours=-3))


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "nombre": "Publico",
        "apellido": "Demo",
        "dni": "43.000.111",
        "telefono": "11 8888-9999",
        "profesional_id": uuid.uuid4(),
        "inicio": datetime(2026, 11, 9, 9, 0, tzinfo=TZ),
    }
    payload.update(overrides)
    return payload


def test_reserva_normaliza_dni_y_telefono() -> None:
    reserva = ReservaCreate(**_payload())
    assert reserva.dni == "43000111"
    assert reserva.telefono == "+5491188889999"


def test_reserva_rechaza_sillon_y_campos_extra() -> None:
    with pytest.raises(ValidationError):
        ReservaCreate(**_payload(sillon_id=str(uuid.uuid4())))
    with pytest.raises(ValidationError):
        ReservaCreate(**_payload(estado="confirmado"))


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("telefono", ""),
        ("telefono", "123"),
        ("telefono", "541188889999"),
        ("dni", "123456"),
        ("dni", "4300011A"),
    ],
)
def test_reserva_rechaza_identidad_invalida(campo: str, valor: str) -> None:
    with pytest.raises(ValidationError):
        ReservaCreate(**_payload(**{campo: valor}))


def test_reserva_rechaza_inicio_sin_zona_horaria() -> None:
    with pytest.raises(ValidationError, match="zona"):
        ReservaCreate(**_payload(inicio=datetime(2026, 11, 9, 9, 0)))


def test_reserva_rechaza_nombre_vacio_y_email_invalido() -> None:
    with pytest.raises(ValidationError):
        ReservaCreate(**_payload(nombre="   "))
    with pytest.raises(ValidationError, match="email"):
        ReservaCreate(**_payload(email="no-es-email"))
