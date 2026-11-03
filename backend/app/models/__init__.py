"""Model package: importing it registers every table on `Base.metadata`."""

from app.models.base import AuditMixin, Base
from app.models.security import (
    Consultorio,
    RegistroAuditoria,
    Rol,
    Usuario,
    UsuarioRol,
)
from app.models.token import TokenUnSoloUso

__all__ = [
    "AuditMixin",
    "Base",
    "Consultorio",
    "RegistroAuditoria",
    "Rol",
    "TokenUnSoloUso",
    "Usuario",
    "UsuarioRol",
]
