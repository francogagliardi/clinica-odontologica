"""Unit tests for the patient/insurance request schemas (C-05, design D8/D11)."""

import pytest
from pydantic import ValidationError

from app.schemas.pacientes import (
    ObraSocialCreate,
    PacienteCreate,
    ReglasCobertura,
)

_BASE_PACIENTE = {
    "nombre": "Ana",
    "apellido": "Demo",
    "dni": "30.111.222",
    "telefono": "11 5555-1234",
}


def test_paciente_normaliza_dni_y_telefono_en_el_borde() -> None:
    paciente = PacienteCreate(**_BASE_PACIENTE)
    assert paciente.dni == "30111222"
    assert paciente.telefono == "+5491155551234"


def test_paciente_rechaza_campos_extra() -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**_BASE_PACIENTE, obra_social="OS Demo")


@pytest.mark.parametrize("telefono", ["", "   ", "123"])
def test_paciente_rechaza_telefono_ausente_o_invalido(telefono: str) -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**{**_BASE_PACIENTE, "telefono": telefono})


def test_paciente_rechaza_dni_invalido() -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**{**_BASE_PACIENTE, "dni": "3011122A"})


def test_paciente_rechaza_afiliado_sin_obra_social() -> None:
    with pytest.raises(ValidationError, match="obra social"):
        PacienteCreate(**_BASE_PACIENTE, nro_afiliado="AF-1")


def test_obra_social_exige_nombre_y_rechaza_validacion_externa() -> None:
    with pytest.raises(ValidationError):
        ObraSocialCreate(nombre="   ")
    with pytest.raises(ValidationError, match="validación externa"):
        ObraSocialCreate(nombre="OS Demo", validacion_externa=True)


def test_obra_social_sin_reglas_usa_objeto_vacio() -> None:
    obra_social = ObraSocialCreate(nombre="OS Demo")
    assert obra_social.reglas_cobertura == ReglasCobertura()


def test_reglas_rechazan_suma_mayor_a_cien() -> None:
    with pytest.raises(ValidationError, match="100"):
        ReglasCobertura(cobertura_porcentaje=70, copago_porcentaje=40)


@pytest.mark.parametrize(
    "campo", ["cobertura_porcentaje", "copago_porcentaje"]
)
@pytest.mark.parametrize("valor", [-1, 101])
def test_reglas_rechazan_porcentaje_fuera_de_rango(
    campo: str, valor: int
) -> None:
    with pytest.raises(ValidationError):
        ReglasCobertura(**{campo: valor})


def test_reglas_normalizan_codigos_y_rechazan_duplicados() -> None:
    reglas = ReglasCobertura(prestaciones_cubiertas=["cons", "LIM"])
    assert reglas.prestaciones_cubiertas == ["CONS", "LIM"]
    with pytest.raises(ValidationError, match="repet"):
        ReglasCobertura(prestaciones_cubiertas=["CONS", "cons"])


def test_reglas_rechazan_forma_que_no_es_objeto() -> None:
    with pytest.raises(ValidationError):
        ObraSocialCreate(nombre="OS Demo", reglas_cobertura=["CONS"])
