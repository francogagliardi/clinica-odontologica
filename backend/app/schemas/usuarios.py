"""Pydantic boundaries for access management (C-16, R-01/R-02, design D12).

Every body forbids extra fields; email is normalized/validated in the domain
and the role list is checked against the fixed catalogue, so an unknown name or
an empty list never reaches the database (422 at the edge).
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.acceso import es_email_valido, normalizar_email, validar_roles

_PASSWORD_MIN = 8
_PASSWORD_MAX = 128


def _email_canonico(valor: str) -> str:
    normalizado = normalizar_email(valor)
    if not es_email_valido(normalizado):
        raise ValueError("Email inválido")
    return normalizado


class RolResponse(BaseModel):
    """Read-only catalogue entry: the API never creates or edits roles."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str


class UsuarioResponse(BaseModel):
    """Public user representation: never includes the password hash (R-03)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    email: str
    is_active: bool
    roles: list[str]


class UsuarioCreate(BaseModel):
    """Backoffice account creation with a write-only password."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=_PASSWORD_MIN, max_length=_PASSWORD_MAX)
    roles: list[str] = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, valor: str) -> str:
        return _email_canonico(valor)

    @field_validator("roles")
    @classmethod
    def _validar_roles(cls, valor: list[str]) -> list[str]:
        return list(validar_roles(valor))


class UsuarioUpdate(BaseModel):
    """Partial edit: only the fields sent are touched; `activo` toggles access."""

    model_config = ConfigDict(extra="forbid")

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    activo: bool | None = None

    @field_validator("email")
    @classmethod
    def _normalizar_email(cls, valor: str | None) -> str | None:
        return None if valor is None else _email_canonico(valor)


class RolesUpdate(BaseModel):
    """Atomic replacement of the role set (no role CRUD, design D3)."""

    model_config = ConfigDict(extra="forbid")

    roles: list[str] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def _validar_roles(cls, valor: list[str]) -> list[str]:
        return list(validar_roles(valor))


class PasswordUpdate(BaseModel):
    """Write-only password rotation; the response never echoes it."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=_PASSWORD_MIN, max_length=_PASSWORD_MAX)
