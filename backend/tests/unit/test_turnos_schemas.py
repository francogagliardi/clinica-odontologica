"""Unit tests for turno request schemas (C-06)."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.turnos import (
    TurnoCreate,
    TurnoEstadoUpdate,
    TurnoListado,
    TurnoReprogramar,
)

TZ = timezone(timedelta(hours=-3))
INICIO = datetime(2026, 11, 9, 9, 0, tzinfo=TZ)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "paciente_id": uuid.uuid4(),
        "profesional_id": uuid.uuid4(),
        "sillon_id": uuid.uuid4(),
        "prestacion_id": uuid.uuid4(),
        "inicio": INICIO,
        "origen": "recepcion",
    }
    payload.update(overrides)
    return payload


def test_alta_acepta_el_payload_minimo() -> None:
    turno = TurnoCreate(**_payload())
    assert turno.es_sobreturno is False
    assert turno.origen == "recepcion"
    assert turno.inicio == INICIO


def test_alta_rechaza_fin_y_estado_del_cliente() -> None:
    with pytest.raises(ValidationError):
        TurnoCreate(**_payload(fin=INICIO + timedelta(hours=1)))
    with pytest.raises(ValidationError):
        TurnoCreate(**_payload(estado="confirmado"))


def test_alta_rechaza_origen_desconocido() -> None:
    with pytest.raises(ValidationError):
        TurnoCreate(**_payload(origen="telefono"))


def test_alta_rechaza_inicio_sin_zona_horaria() -> None:
    with pytest.raises(ValidationError, match="zona"):
        TurnoCreate(**_payload(inicio=datetime(2026, 11, 9, 9, 0)))


def test_sobreturno_exige_color_valido() -> None:
    with pytest.raises(ValidationError, match="color"):
        TurnoCreate(**_payload(es_sobreturno=True))

    valido = TurnoCreate(
        **_payload(es_sobreturno=True, color_sobreturno="#f97316")
    )
    assert valido.color_sobreturno == "#f97316"

    with pytest.raises(ValidationError, match="color"):
        TurnoCreate(**_payload(es_sobreturno=True, color_sobreturno="naranja"))


def test_turno_normal_no_admite_color() -> None:
    with pytest.raises(ValidationError, match="color"):
        TurnoCreate(**_payload(color_sobreturno="#F97316"))


def test_reprogramar_exige_al_menos_un_cambio() -> None:
    with pytest.raises(ValidationError, match="cambio"):
        TurnoReprogramar()

    reprogramar = TurnoReprogramar(inicio=INICIO + timedelta(days=1))
    assert reprogramar.inicio is not None


def test_cambio_de_estado_no_admite_volver_a_reservado() -> None:
    with pytest.raises(ValidationError):
        TurnoEstadoUpdate(estado="reservado")
    assert TurnoEstadoUpdate(estado="confirmado").estado == "confirmado"


def test_listado_exige_rango_coherente_y_acotado() -> None:
    with pytest.raises(ValidationError, match="posterior"):
        TurnoListado(desde=date(2026, 11, 10), hasta=date(2026, 11, 9))

    with pytest.raises(ValidationError, match="62"):
        TurnoListado(desde=date(2026, 11, 1), hasta=date(2027, 2, 1))

    listado = TurnoListado(desde=date(2026, 11, 9), hasta=date(2026, 11, 15))
    assert listado.estado is None
