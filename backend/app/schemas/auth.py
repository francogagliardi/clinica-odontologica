"""Pydantic schemas for authentication and tokens (C-03, R-01)."""

import uuid
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials payload for POST /usuarios/login."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UsuarioAuthResponse(BaseModel):
    """Public user identity and assigned role names."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    nombre: str
    email: str
    roles: list[str]


class TokenResponse(BaseModel):
    """Access token response schema (DD-07b)."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    usuario: UsuarioAuthResponse
