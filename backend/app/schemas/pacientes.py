"""Pydantic schemas for the patient registry and insurance agreements (C-05).

Requests forbid extra fields (R-01/R-02) and normalize DNI/phone at the edge.
Business coherence (affiliate requires an agreement, coverage percentages) is
validated here and backed by PostgreSQL CHECKs (design D6/D8/D11).
"""

import uuid
from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.domain.pacientes import normalizar_dni, normalizar_telefono


class PacienteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    apellido: str = Field(min_length=1, max_length=120)
    dni: str
    fecha_nacimiento: date | None = None
    telefono: str
    email: str | None = Field(default=None, max_length=255)
    obra_social_id: uuid.UUID | None = None
    nro_afiliado: str | None = Field(default=None, max_length=40)
    notas: str | None = Field(default=None, max_length=2000)

    @field_validator("nombre", "apellido")
    @classmethod
    def _texto_obligatorio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("El nombre y el apellido no pueden estar vacíos")
        return limpio

    @field_validator("dni")
    @classmethod
    def _dni_normalizado(cls, value: str) -> str:
        return normalizar_dni(value)

    @field_validator("telefono")
    @classmethod
    def _telefono_normalizado(cls, value: str) -> str:
        return normalizar_telefono(value)

    @field_validator("email")
    @classmethod
    def _email_opcional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip().lower()
        if not limpio:
            return None
        if "@" not in limpio or "." not in limpio.split("@")[-1]:
            raise ValueError("El email no tiene un formato válido")
        return limpio

    @field_validator("nro_afiliado")
    @classmethod
    def _afiliado_opcional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        return limpio or None

    @field_validator("notas")
    @classmethod
    def _notas_opcionales(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        return limpio or None

    @model_validator(mode="after")
    def _cobertura_coherente(self) -> "PacienteBase":
        if self.obra_social_id is None and self.nro_afiliado is not None:
            raise ValueError(
                "El número de afiliado requiere una obra social asociada"
            )
        return self


class PacienteCreate(PacienteBase):
    pass


class PacienteUpdate(PacienteBase):
    pass


class PacienteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    nombre: str
    apellido: str
    dni: str
    fecha_nacimiento: date | None
    telefono: str
    email: str | None
    obra_social_id: uuid.UUID | None
    nro_afiliado: str | None
    notas: str | None
    is_active: bool


class BusquedaPaciente(BaseModel):
    """At least one criterion is required to avoid dumping every patient."""

    model_config = ConfigDict(extra="forbid")

    dni: str | None = None
    telefono: str | None = None
    apellido: str | None = Field(default=None, max_length=120)

    @field_validator("dni")
    @classmethod
    def _dni_busqueda(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalizar_dni(value)

    @field_validator("telefono")
    @classmethod
    def _telefono_busqueda(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalizar_telefono(value)

    @field_validator("apellido")
    @classmethod
    def _apellido_busqueda(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        return limpio or None

    @model_validator(mode="after")
    def _exigir_criterio(self) -> "BusquedaPaciente":
        if not any((self.dni, self.telefono, self.apellido)):
            raise ValueError(
                "Indicá al menos un criterio: dni, telefono o apellido"
            )
        return self


class ReglasCobertura(BaseModel):
    """Local coverage rules for v1 (DD-11); C-12 computes the actual values."""

    model_config = ConfigDict(extra="forbid")

    cobertura_porcentaje: int | None = Field(default=None, ge=0, le=100)
    copago_porcentaje: int | None = Field(default=None, ge=0, le=100)
    prestaciones_cubiertas: list[str] = Field(
        default_factory=list, max_length=200
    )
    requiere_autorizacion: bool = False

    @field_validator("prestaciones_cubiertas")
    @classmethod
    def _codigos_normalizados(cls, value: list[str]) -> list[str]:
        codigos = [codigo.strip().upper() for codigo in value if codigo.strip()]
        if len(set(codigos)) != len(codigos):
            raise ValueError("Los códigos de prestación no pueden repetirse")
        return codigos

    @model_validator(mode="after")
    def _suma_coherente(self) -> "ReglasCobertura":
        if (
            self.cobertura_porcentaje is not None
            and self.copago_porcentaje is not None
            and self.cobertura_porcentaje + self.copago_porcentaje > 100
        ):
            raise ValueError(
                "La suma de cobertura y copago no puede superar 100"
            )
        return self


class ObraSocialBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    nomenclador_ref: str | None = Field(default=None, max_length=60)
    reglas_cobertura: ReglasCobertura = Field(default_factory=ReglasCobertura)
    validacion_externa: bool = False

    @field_validator("nombre")
    @classmethod
    def _nombre_obligatorio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("El nombre de la obra social no puede estar vacío")
        return limpio

    @field_validator("nomenclador_ref")
    @classmethod
    def _nomenclador_opcional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        return limpio or None

    @model_validator(mode="after")
    def _validacion_externa_v1(self) -> "ObraSocialBase":
        if self.validacion_externa:
            raise ValueError(
                "La validación externa no está disponible en v1: "
                "usar reglas locales"
            )
        return self


class ObraSocialCreate(ObraSocialBase):
    pass


class ObraSocialUpdate(ObraSocialBase):
    pass


class ObraSocialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    consultorio_id: uuid.UUID
    nombre: str
    nomenclador_ref: str | None
    reglas_cobertura: ReglasCobertura
    validacion_externa: bool
    is_active: bool
